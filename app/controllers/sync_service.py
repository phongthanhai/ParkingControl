import os
import time
import threading
import cv2
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer, QMutex
from app.utils.db_manager import DBManager
from app.controllers.api_client import ApiClient
from config import LOT_ID, API_BASE_URL
from app.utils.image_storage import ImageStorage

class SyncStatus:
    """Enum-like class for sync status values"""
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    RUNNING = "running"

class SyncWorker(QThread):
    """Worker thread for synchronization operations when explicitly triggered"""
    sync_progress = pyqtSignal(str, int, int)  # entity_type, completed, total
    sync_complete = pyqtSignal(str, bool, str)  # entity_type, success, message
    
    def __init__(self, sync_service):
        super().__init__()
        self.sync_service = sync_service
        self.db_manager = DBManager()
        self.api_client = ApiClient(base_url=API_BASE_URL)
        self._running = True
        self._paused = False
        self.mutex = QMutex()
        self._current_operation = None
        self._sync_requested = False  # New flag to trigger sync operations
        self._sync_type = None  # Type of sync to perform
        
    def run(self):
        """Main worker thread loop - now only processes explicit sync requests"""
        print("SyncWorker started - waiting for sync requests")
        while self._running:
            # Check if sync was requested and we're not paused
            if self._sync_requested and not self._paused and self.sync_service.api_available:
                self.mutex.lock()
                self._sync_requested = False
                sync_type = self._sync_type
                self._sync_type = None
                self.mutex.unlock()
                
                try:
                    print(f"SyncWorker processing sync request: {sync_type}")
                    # Only proceed if token refresh is successful
                    if self.sync_service._ensure_fresh_token():
                        # Check if we have anything to sync
                        counts = self.sync_service.get_pending_sync_counts()
                        if counts["total"] > 0:
                            print(f"SyncWorker found {counts['total']} items to sync")
                            
                            # Sync blacklist first if requested
                            if sync_type == "all" or sync_type == "blacklist":
                                self._sync_blacklist()
                                
                            # Then sync logs
                            if sync_type == "all" or sync_type == "logs":
                                sync_count = self._sync_logs()
                                
                                # Signal completion with count
                                sync_count = sync_count if sync_count is not None else 0
                                self.sync_service.last_sync_count = sync_count
                                self.sync_service.sync_all_complete.emit(sync_count)
                        else:
                            print("SyncWorker: No items to sync")
                            self.sync_service.last_sync_count = 0
                            self.sync_service.sync_all_complete.emit(0)
                    else:
                        print("SyncWorker: Token refresh failed, aborting sync")
                except Exception as e:
                    print(f"SyncWorker sync error: {str(e)}")
                    self.sync_service.last_sync_count = 0
                    self.sync_service.sync_all_complete.emit(0)
            
            # Sleep a bit to avoid CPU spinning
            time.sleep(0.5)
    
    def request_sync(self, sync_type="all"):
        """Request a sync operation to be performed"""
        if not self._running:
            print("Cannot request sync: worker is not running")
            return False
            
        self.mutex.lock()
        self._sync_requested = True
        self._sync_type = sync_type
        self.mutex.unlock()
        print(f"Sync requested: {sync_type}")
        return True
    
    def stop(self):
        """Signal the thread to stop"""
        print("Stopping sync worker")
        self._running = False
    
    def pause(self):
        """Pause sync operations"""
        print("Pausing sync worker")
        self.mutex.lock()
        self._paused = True
        self.mutex.unlock()
    
    def resume(self):
        """Resume sync operations"""
        print("Resuming sync worker")
        self.mutex.lock()
        self._paused = False
        self.mutex.unlock()
    
    def _sync_blacklist(self):
        """Sync blacklist data from server to local"""
        if not self.sync_service.can_sync():
            return
            
        self.mutex.lock()
        self._current_operation = "blacklist"
        self.mutex.unlock()
        
        try:
            # Get blacklisted vehicles from API
            success, response = self.api_client.get(
                'vehicles/blacklisted/',
                params={'skip': 0, 'limit': 1000},
                timeout=(3.0, 10.0)
            )
            
            if success and response:
                # Update local database
                self.db_manager.update_blacklist(response)
                self.sync_complete.emit("blacklist", True, f"Updated {len(response)} blacklist records")
            else:
                self.sync_complete.emit("blacklist", False, "Failed to retrieve blacklist data")
        
        except Exception as e:
            self.sync_complete.emit("blacklist", False, f"Blacklist sync error: {str(e)}")
        
        self.mutex.lock()
        self._current_operation = None
        self.mutex.unlock()
    
    def _sync_logs(self):
        """Sync log entries from local to server using the comprehensive guard-control endpoint"""
        if not self.sync_service.can_sync():
            print("Cannot sync logs: sync not allowed at this time")
            return 0
        
        self.mutex.lock()
        self._current_operation = "logs"
        self.mutex.unlock()
            
        try:
            print("\n=== SYNC WORKER: STARTING LOG SYNC ===")
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=20)
            
            if not unsynced_logs:
                print("SYNC WORKER: No logs to sync")
                self.sync_complete.emit("logs", True, "No logs to sync")
                self.mutex.lock()
                self._current_operation = None
                self.mutex.unlock()
                return 0
            
            print(f"SYNC WORKER: Found {len(unsynced_logs)} unsynced logs")    
            
            # Only sync auto and manual entries, not denied-blacklist or skipped
            filtered_logs = [log for log in unsynced_logs 
                            if log['type'] in ('auto', 'manual')]
            
            print(f"SYNC WORKER: After filtering - {len(filtered_logs)} logs to sync")
            
            # If no valid logs after filtering, exit
            if not filtered_logs:
                print("SYNC WORKER: No valid logs to sync after filtering")
                self.sync_complete.emit("logs", True, "No valid logs to sync")
                self.mutex.lock()
                self._current_operation = None
                self.mutex.unlock()
                return 0
                
            total_logs = len(filtered_logs)
            self.sync_progress.emit("logs", 0, total_logs)
            print(f"SYNC WORKER: Starting to sync {total_logs} logs to server...")
            
            # Process each log
            synced_count = 0
            failed_count = 0
            for i, log in enumerate(filtered_logs):
                if not self._running or self._paused:
                    print("SYNC WORKER: Sync operation interrupted - stopping")
                    break
                
                try:
                    # Check if this log is already marked as synced
                    if log.get('synced', 0) == 1:
                        print(f"SYNC WORKER: Skipping log {log['id']} as it's already marked as synced")
                        continue
                        
                    # Extra validation
                    if not log.get('plate_id'):
                        print(f"SYNC WORKER: Skipping log {log['id']} - missing plate_id")
                        continue
                        
                    # Prepare form data
                    form_data = {
                        'plate_id': log['plate_id'],
                        'lot_id': LOT_ID,
                        'lane': log['lane'],
                        'type': log['type'],
                        'timestamp': log['timestamp']
                    }
                    
                    print(f"SYNC WORKER: Syncing log {log['id']}: {log['plate_id']} - {log['lane']} - {log['type']}") 
                    
                    # Handle image if available
                    files = None
                    if log.get('image_path') and os.path.exists(log.get('image_path')):
                        try:
                            print(f"SYNC WORKER: Processing image for log {log['id']}: {log['image_path']}")
                            # Read image and convert to bytes
                            img = cv2.imread(log['image_path'])
                            if img is not None:
                                _, img_encoded = cv2.imencode('.png', img)
                                img_bytes = img_encoded.tobytes()
                                files = {
                                    'image': ('frame.png', img_bytes, 'image/png')
                                }
                                print(f"SYNC WORKER: Successfully prepared image for log {log['id']}")
                            else:
                                print(f"SYNC WORKER: Image for log {log['id']} couldn't be read, sending without image")
                        except Exception as img_err:
                            print(f"SYNC WORKER: Error processing image for log {log['id']}: {str(img_err)}")
                            # Continue without the image rather than failing the sync
                    
                    # Send to API - guard-control endpoint handles everything
                    print(f"SYNC WORKER: Sending log {log['id']} to API endpoint services/guard-control/...")
                    
                    # Create a separate API client instance to avoid thread safety issues
                    api_client = ApiClient(base_url=API_BASE_URL)
                    
                    success, response = api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 15.0)
                    )
                    
                    if success:
                        print(f"SYNC WORKER: Successfully synced log {log['id']}")
                        # Mark as synced in the database
                        self.db_manager.mark_log_synced(log['id'])
                        synced_count += 1
                    else:
                        failed_count += 1
                        print(f"SYNC WORKER: Failed to sync log {log['id']}: {response}")
                        
                        # Check if it's an authentication failure
                        if isinstance(response, str) and "Authentication failed" in response:
                            print("SYNC WORKER: Authentication failed during sync, stopping batch")
                            break
                    
                    progress = i + 1
                    self.sync_progress.emit("logs", progress, total_logs)
                    
                    # Small delay to prevent UI freezing and avoid overwhelming the server
                    time.sleep(0.2)
                    
                except Exception as e:
                    failed_count += 1
                    print(f"SYNC WORKER: Error syncing log {log['id']}: {str(e)}")
                    # Don't mark as synced on error, it will be retried next time
            
            # Always emit final progress with the actual count
            self.sync_progress.emit("logs", synced_count + failed_count, total_logs)
                
            # Show detailed summary
            result_message = f"Synced {synced_count}/{total_logs} log entries"
            if failed_count > 0:
                result_message += f" ({failed_count} failed)"
            
            success = synced_count > 0
            print(f"SYNC WORKER: Completed log sync - {result_message} - Success: {success}")
            
            # Only report success if we actually synced something
            self.sync_complete.emit("logs", success, result_message)
                                   
        except Exception as e:
            print(f"SYNC WORKER: Log sync error: {str(e)}")
            self.sync_complete.emit("logs", False, f"Log sync error: {str(e)}")
            synced_count = 0
        
        self.mutex.lock()
        self._current_operation = None
        self.mutex.unlock()
        
        print(f"=== SYNC WORKER: LOG SYNC COMPLETE - Synced {synced_count} logs ===\n")
        return synced_count

class SyncService(QObject):
    """
    Service to manage synchronization between local SQLite and backend API.
    Simplified to sync only at three key moments:
    1. Application startup
    2. When connection is restored after being lost
    3. Before application shutdown (if possible)
    """
    sync_status_changed = pyqtSignal(str, str)  # type, status
    sync_progress = pyqtSignal(str, int, int)   # entity_type, completed, total
    api_status_changed = pyqtSignal(bool)       # is_available
    sync_all_complete = pyqtSignal(int)         # count of synced items
    
    def __init__(self):
        super().__init__()
        self.db_manager = DBManager()
        self.api_client = ApiClient(base_url=API_BASE_URL)
        
        # API connectivity state
        self.api_available = True
        self.api_retry_count = 0
        self.max_api_retries = 5 
        self.consecutive_failures = 0
        
        # Track last successful sync and auth refreshes
        self.last_sync_time = time.time()
        self.last_token_refresh_time = 0
        self.min_token_refresh_interval = 5  # Minimum seconds between token refreshes
        
        # Track when we were offline
        self.previously_offline = False
        
        # The last count of items synced in a cycle
        self.last_sync_count = 0
        
        # Create a signal for thread-safe sync triggering
        self.sync_requested_signal = pyqtSignal(str)
        self.sync_requested_signal.connect(self._handle_sync_request)
        
        # Create and start the worker thread (now only acts on explicit requests)
        self.sync_worker = SyncWorker(self)
        self.sync_worker.sync_progress.connect(self._handle_sync_progress)
        self.sync_worker.sync_complete.connect(self._handle_sync_complete)
        
        # Start with worker paused if API not available
        if not self.check_api_connection():
            self.sync_worker.pause()
        
        # Start the worker thread
        self.sync_worker.start()
        
        # Start periodic API connection check timer
        self.api_check_timer = QTimer(self)
        self.api_check_timer.timeout.connect(self.check_api_connection)
        self.api_check_timer.start(30000)  # Check every 30 seconds
        
        # Schedule an initial sync check after startup
        QTimer.singleShot(5000, self._check_initial_sync)
    
    def _check_initial_sync(self):
        """Check if there are any unsynced logs at application startup and sync if needed"""
        if self.api_available:
            # Get counts of unsynced items
            counts = self.get_pending_sync_counts()
            if counts["total"] > 0:
                print(f"Found {counts['total']} unsynced items at startup, triggering sync")
                self.sync_now()
            else:
                print("No unsynced items at startup, skipping initial sync")
    
    def check_api_connection(self):
        """Check if the API server is available"""
        try:
            # Call the asynchronous health check method
            self.api_client.check_health_async(
                callback=self._handle_api_check_result,
                timeout=(1.0, 2.0)  # Short timeout
            )
            
            return self.api_available
        except Exception as e:
            print(f"API connection check error: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)
            return False
    
    def _handle_api_check_result(self, success):
        """Handle API health check result with transition detection"""
        previously_offline = not self.api_available
        
        if success:
            # Reset failure counters
            self.consecutive_failures = 0
            self.api_retry_count = 0
            
            # Check if we've transitioned from offline to online
            if previously_offline:
                print("SyncService detected transition from OFFLINE to ONLINE")
                self.previously_offline = True
                # Mark as available immediately to allow other operations
                self.api_available = True
                self.api_status_changed.emit(True)
                # Validate the authentication to make sure our token is still valid
                self._validate_token_after_reconnect()
            elif not self.api_available:
                # We were unavailable but not in a full offline state
                self.api_available = True
                self.api_status_changed.emit(True)
                # Resume background sync
                self.sync_worker.resume()
        else:
            # If we get consecutive failures, mark as unavailable
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_api_retries:
                self.api_available = False
                self.api_status_changed.emit(False)
                # Pause worker when API is unavailable
                self.sync_worker.pause()
    
    def _validate_token_after_reconnect(self):
        """Validate authentication token after reconnecting from offline to online"""
        if not self.previously_offline:
            return
            
        # Clear the flag immediately to prevent duplicate operations
        self.previously_offline = False
        
        print("SyncService validating authentication after offline->online transition")
        
        # Just check if our current token looks valid by checking lastUpdated time
        from app.utils.auth_manager import AuthManager
        auth_manager = AuthManager()
        
        # Get token age in seconds
        current_time = time.time()
        token_age = current_time - auth_manager.last_updated if auth_manager.last_updated > 0 else float('inf')
        
        # If token was updated in the last 5 minutes, assume it's valid
        if auth_manager.is_authenticated() and token_age < 300:
            print(f"Token appears valid (updated {token_age:.1f}s ago), checking for unsynced items")
            # Resume sync operations
            self.sync_worker.resume()
            
            # Check if we have unsynced logs to sync
            counts = self.get_pending_sync_counts()
            if counts["total"] > 0:
                print(f"Found {counts['total']} unsynced items after reconnection, requesting sync")
                # Use thread-safe method instead of direct call
                self.request_sync_from_thread()
            else:
                print("No unsynced items after reconnection, skipping sync")
            return
        
        # Otherwise do an API check
        try:
            # First try to refresh the token
            if self._ensure_fresh_token():
                print("Token refreshed successfully after reconnect")
                # Resume sync operations
                self.sync_worker.resume()
                
                # Check if we have unsynced logs to sync
                counts = self.get_pending_sync_counts()
                if counts["total"] > 0:
                    print(f"Found {counts['total']} unsynced items after reconnection, requesting sync")
                    # Use thread-safe method instead of direct call
                    self.request_sync_from_thread()
                else:
                    print("No unsynced items after reconnection, skipping sync")
                return
                
            # If token refresh failed, try an API call to check token validity
            auth_result = self.api_client.get(
                'services/lot-occupancy/1', 
                timeout=(2.0, 3.0),
                retry_on_auth_fail=False  # Don't auto-retry
            )
            
            if auth_result[0]:
                print("Authentication is still valid after reconnect")
                # Resume sync operations
                self.sync_worker.resume()
                
                # Check if we have unsynced logs to sync
                counts = self.get_pending_sync_counts()
                if counts["total"] > 0:
                    print(f"Found {counts['total']} unsynced items after reconnection, requesting sync")
                    # Use thread-safe method instead of direct call
                    self.request_sync_from_thread()
                else:
                    print("No unsynced items after reconnection, skipping sync")
            else:
                print("Authentication is invalid after reconnect, refreshing token")
                # Refresh token before resuming operations
                self._attempt_token_refresh()
        except Exception as e:
            print(f"Error validating token after reconnect: {str(e)}")
            # Try to refresh token on error
            self._attempt_token_refresh()
    
    def sync_now(self, entity_type=None):
        """
        Manually trigger a synchronization through the worker.
        If entity_type is None, sync everything.
        
        Returns:
            dict: A result dictionary with success, count, and message
        """
        # Initialize result dictionary
        result = {
            "success": False,
            "count": 0,
            "message": ""
        }
        
        print("\n==== REQUESTING SYNC OPERATION ====")
        
        if not self.api_available:
            print("Cannot sync: API is not available")
            result["message"] = "API not available"
            return result
        
        # Check if we have anything to sync first
        counts = self.get_pending_sync_counts()
        if counts["total"] == 0:
            print("No items to sync, skipping operation")
            result["success"] = True
            result["message"] = "No items needed syncing"
            return result
            
        # Verify connection
        print("Verifying API connection...")
        connection_ok = self.check_api_connection()
        if not connection_ok or not self.api_available:
            print("API is not available, skipping sync")
            result["message"] = "API not available"
            return result
            
        # Ensure we have a valid token
        if not self._ensure_fresh_token():
            print("Failed to refresh authentication token, skipping sync")
            result["message"] = "Authentication failed"
            return result
            
        # Request the sync operation through the worker
        print(f"Requesting sync for {entity_type or 'all'} from worker thread")
        if self.sync_worker.request_sync(entity_type or "all"):
            # The sync will happen asynchronously, so we can't return actual results
            # But we can indicate that the request was successful
            result["success"] = True
            result["message"] = "Sync requested successfully"
        else:
            result["message"] = "Failed to request sync"
            
        return result
    
    def stop(self):
        """Stop the sync service cleanly"""
        print("Stopping sync service...")
        try:
            # First check if there are unsynced items and sync them if possible
            if self.api_available:
                counts = self.get_pending_sync_counts()
                if counts["total"] > 0:
                    print(f"Found {counts['total']} unsynced items before shutdown, attempting final sync")
                    # Use synchronous sync here to ensure it completes before shutdown
                    self._perform_shutdown_sync()
            
            # Stop the API check timer
            if hasattr(self, 'api_check_timer') and self.api_check_timer.isActive():
                self.api_check_timer.stop()
                print("API check timer stopped")
            
            # Signal the worker to stop and wait for it to finish
            if self.sync_worker and self.sync_worker.isRunning():
                print("Stopping sync worker thread...")
                self.sync_worker.stop()
                
                # Wait for the thread to finish with a timeout
                if not self.sync_worker.wait(5000):  # Wait up to 5 seconds
                    print("WARNING: Sync worker thread did not stop gracefully, forcing termination")
                    self.sync_worker.terminate()
                    self.sync_worker.wait(500)  # Give it 500ms to terminate
                
                print("Sync worker thread stopped")
                
            # Clear the worker reference
            self.sync_worker = None
            
        except Exception as e:
            print(f"Error during sync service shutdown: {str(e)}")
    
    def _perform_shutdown_sync(self):
        """Perform a synchronous sync operation during shutdown"""
        print("Performing final sync before shutdown...")
        try:
            # This method directly syncs logs during shutdown
            import os
            import cv2
            from config import LOT_ID
            
            # Ensure token is valid
            if not self._ensure_fresh_token():
                print("Failed to refresh token for shutdown sync")
                return
                
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=50)
            filtered_logs = [log for log in unsynced_logs if log['type'] in ('auto', 'manual')]
            
            if not filtered_logs:
                print("No logs to sync before shutdown")
                return
                
            print(f"Syncing {len(filtered_logs)} logs before shutdown")
            synced_count = 0
            
            # Process each log
            for log in filtered_logs:
                try:
                    # Check if already synced
                    if log.get('synced', 0) == 1:
                        continue
                        
                    # Prepare form data
                    form_data = {
                        'plate_id': log['plate_id'],
                        'lot_id': LOT_ID,
                        'lane': log['lane'],
                        'type': log['type'],
                        'timestamp': log['timestamp']
                    }
                    
                    # Handle image if available
                    files = None
                    if log.get('image_path') and os.path.exists(log.get('image_path')):
                        try:
                            img = cv2.imread(log['image_path'])
                            if img is not None:
                                _, img_encoded = cv2.imencode('.png', img)
                                img_bytes = img_encoded.tobytes()
                                files = {
                                    'image': ('frame.png', img_bytes, 'image/png')
                                }
                        except Exception as img_err:
                            print(f"Error processing image for shutdown sync: {str(img_err)}")
                    
                    # Sync to API
                    success, response = self.api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 15.0)
                    )
                    
                    if success:
                        self.db_manager.mark_log_synced(log['id'])
                        synced_count += 1
                        print(f"Successfully synced log {log['id']} during shutdown")
                    else:
                        print(f"Failed to sync log {log['id']} during shutdown: {response}")
                        
                except Exception as e:
                    print(f"Error syncing log during shutdown: {str(e)}")
            
            print(f"Shutdown sync complete: {synced_count}/{len(filtered_logs)} logs synced")
            
        except Exception as e:
            print(f"Error during shutdown sync: {str(e)}")
    
    def _handle_sync_progress(self, entity_type, completed, total):
        """Handle progress updates from the sync worker."""
        self.sync_progress.emit(entity_type, completed, total)
    
    def _handle_sync_complete(self, entity_type, success, message):
        """Handle completion notification from the sync worker."""
        status = SyncStatus.SUCCESS if success else SyncStatus.FAILED
        self.sync_status_changed.emit(entity_type, status)
        print(f"Sync {entity_type}: {status} - {message}")
    
    def can_sync(self):
        """Check if synchronization is possible."""
        if not self.api_available:
            print("Can't sync: API not available")
            return False
        
        # Remove the time-based throttling that was preventing immediate sync after reconnection
        # Now we'll just update the timestamp for metrics but allow the sync to proceed
        current_time = time.time()
        time_since_last = current_time - self.last_sync_time
        
        # Still log the timing for debugging purposes
        print(f"Time since last sync: {time_since_last:.1f}s")
        
        # Always update timestamp to prevent rapid consecutive syncs
        self.last_sync_time = current_time
        return True
    
    def _ensure_fresh_token(self):
        """Ensure we have a fresh authentication token by using refresh token"""
        from app.utils.auth_manager import AuthManager
        auth_manager = AuthManager()
        
        # Rate limit token refreshes
        current_time = time.time()
        if current_time - self.last_token_refresh_time < self.min_token_refresh_interval:
            print(f"Skipping token refresh - last refresh was {current_time - self.last_token_refresh_time:.1f}s ago")
            return True
            
        print("Pre-sync token refresh check")
        
        token_refreshed = False
        
        # First try to use refresh token if available
        if auth_manager.has_refresh_token():
            print("Using refresh token for pre-sync token refresh")
            token_refreshed = self.api_client._refresh_token()
            if token_refreshed:
                print("Token refreshed successfully using refresh token before sync")
                self.last_token_refresh_time = current_time
                return True
            print("Refresh token failed, falling back to credentials")
        
        # Fall back to credentials if refresh token not available or failed
        if not token_refreshed and (auth_manager.username and auth_manager.password):
            print(f"Using credentials for pre-sync token refresh ({auth_manager.username})")
            
            # Attempt login to get fresh token
            success, message, _ = self.api_client.login(
                auth_manager.username,
                auth_manager.password,
                timeout=(3.0, 5.0)
            )
            
            if success:
                print("Token refreshed successfully before sync using credentials")
                self.last_token_refresh_time = current_time
                return True
            else:
                print(f"Failed to refresh token before sync: {message}")
                return False
        
        return token_refreshed
    
    def get_pending_sync_counts(self):
        """Get counts of pending items for each sync category."""
        # Filter to count only auto and manual entries (not blacklist or skipped)
        try:
            # Get raw DB counts first for debugging
            raw_count = self.db_manager.get_log_entry_count()
            unsynced_count = self.db_manager.get_log_entry_count(only_unsynced=True)
            print(f"Database stats - Total logs: {raw_count}, Unsynced logs: {unsynced_count}")
            
            # Get detailed logs for filtering
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=1000)
            if unsynced_logs:
                print(f"Found {len(unsynced_logs)} unsynced logs in the database")
                for idx, log in enumerate(unsynced_logs[:5]):  # Just print first 5 for diagnostics
                    print(f"  Log {idx+1}: ID={log.get('id')}, Type={log.get('type')}, Plate={log.get('plate_id')}")
                if len(unsynced_logs) > 5:
                    print(f"  ... and {len(unsynced_logs)-5} more")
            else:
                print("No unsynced logs found in the database")
                
            filtered_logs = [log for log in unsynced_logs 
                           if log['type'] in ('auto', 'manual')]
            total = len(filtered_logs)
            
            print(f"After filtering for auto/manual entries: {total} logs need to be synced")
            
            return {
                "logs": total,
                "total": total
            }
        except Exception as e:
            print(f"Error getting pending sync counts: {str(e)}")
            return {
                "logs": 0,
                "total": 0
            }
    
    def __del__(self):
        """Clean up resources."""
        try:
            self.stop()
        except Exception as e:
            print(f"Error during sync service cleanup: {str(e)}")
    
    def _handle_sync_request(self, entity_type=None):
        """Thread-safe handler for sync requests from other threads"""
        # This method runs on the main thread because it's connected to a signal
        print(f"Handling sync request on main thread: {entity_type}")
        self.sync_now(entity_type)
        
    def request_sync_from_thread(self, entity_type=None):
        """Thread-safe method to request sync from any thread"""
        print(f"Requesting sync from thread: {entity_type or 'all'}")
        # Use the signal to safely trigger sync on the main thread
        self.sync_requested_signal.emit(entity_type or "all")

    def _handle_refresh_thread_result(self, success):
        """Handle the result from the token refresh thread"""
        try:
            if success:
                print("Token refresh thread completed successfully")
                self.api_available = True
                self.api_status_changed.emit(True)
                if hasattr(self, 'sync_worker'):
                    self.sync_worker.resume()
                    
                    # If we were previously offline, check for unsynced items
                    print("Checking for unsynced items after token refresh")
                    
                    # Check counts on this thread (background) first
                    counts = self.get_pending_sync_counts()
                    if counts["total"] > 0:
                        print(f"Found {counts['total']} unsynced items after token refresh")
                        # Request sync safely through signal
                        self.request_sync_from_thread()
                    else:
                        print("No unsynced items after token refresh")
            else:
                print("Token refresh thread failed")
                self.api_available = False
                self.api_status_changed.emit(False)
        except Exception as e:
            print(f"Error handling refresh thread result: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False) 