import os
import time
import cv2
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer, QMutex, QMetaObject, Qt, Q_ARG
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
        self.context = None  # Track the context of the current sync (startup, shutdown, etc.)
        
    def run(self):
        """Main worker thread loop"""
        print("SyncWorker thread started")
        
        while self._running:
            # Check if sync was requested
            self.mutex.lock()
            sync_requested = self._sync_requested
            sync_type = self._sync_type
            self.mutex.unlock()
            
            if sync_requested:
                try:
                    print(f"SyncWorker processing sync request: {sync_type} (context: {self.context})")
                    
                    # Check API connection
                    if not self.sync_service.api_available:
                        print("SyncWorker: API is not available")
                        self.sync_service.last_sync_count = 0
                        self.sync_service.sync_all_complete.emit(0, self.context)
                        
                        # Reset sync flags
                        self.mutex.lock()
                        self._sync_requested = False
                        self._sync_type = None
                        self.mutex.unlock()
                        continue
                    
                    # Make sure we have valid auth before proceeding
                    token_valid = self.sync_service._ensure_fresh_token()
                    if not token_valid:
                        print("SyncWorker: Token refresh failed, aborting sync")
                        
                        # Reset sync flags
                        self.mutex.lock()
                        self._sync_requested = False
                        self._sync_type = None
                        self.mutex.unlock()
                        
                        # Signal completion with error
                        self.sync_service.last_sync_count = 0
                        self.sync_service.sync_all_complete.emit(0, self.context)
                        continue
                    
                    # Perform the actual sync
                    sync_count = None
                    
                    if sync_type == "logs" or sync_type == "all":
                        sync_count = self._sync_logs()
                        
                    # Mark sync as complete
                    self.mutex.lock()
                    self._sync_requested = False
                    self._sync_type = None
                    self.mutex.unlock()
    
                    # Signal completion with the context
                    sync_count = sync_count if sync_count is not None else 0
                    self.sync_service.last_sync_count = sync_count
                    self.sync_service.sync_all_complete.emit(sync_count, self.context)
                except Exception as e:
                    print(f"SyncWorker sync error: {str(e)}")
                    self.sync_service.last_sync_count = 0
                    self.sync_service.sync_all_complete.emit(0, self.context)
                    
                    # Reset sync flags even on error
                    self.mutex.lock()
                    self._sync_requested = False
                    self._sync_type = None
                    self.mutex.unlock()
    
            # Sleep a bit to avoid CPU spinning
            time.sleep(0.1)
            
    def request_sync(self, sync_type="all"):
        """Request a sync operation to be performed"""
        print(f"Sync requested: {sync_type}")
        
        # Set the request flag with mutex protection
        self.mutex.lock()
        self._sync_requested = True
        self._sync_type = sync_type
        self.mutex.unlock()
        
        return True
        
    def stop(self):
        """Stop the worker thread"""
        self._running = False
        print("SyncWorker stopping...")
        
    def pause(self):
        """Pause the worker thread"""
        self.mutex.lock()
        self._paused = True
        self.mutex.unlock()
        print("SyncWorker paused")
        
    def resume(self):
        """Resume the worker thread"""
        self.mutex.lock()
        self._paused = False
        self.mutex.unlock()
        print("SyncWorker resumed")
    
    def _sync_logs(self):
        """Sync log entries from local to server using the comprehensive guard-control endpoint"""
        if not self.sync_service.can_sync():
            print("Cannot sync logs: sync not allowed at this time")
            return 0
        
        self.mutex.lock()
        self._current_operation = "logs"
        self.mutex.unlock()
            
        try:
            # Print context-aware message
            if self.context == "startup":
                print("\n=== SYNC WORKER: STARTING INITIAL LOG SYNC ===")
            elif self.context == "shutdown":
                print("\n=== SYNC WORKER: STARTING FINAL LOG SYNC ===")
            else:
                print("\n=== SYNC WORKER: STARTING LOG SYNC ===")
                
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=20)
            
            if not unsynced_logs:
                print("SYNC WORKER: No logs to sync")
                self.sync_complete.emit("logs", True, "No logs to sync")
                return 0
                
            print(f"SYNC WORKER: Found {len(unsynced_logs)} unsynced logs")
            
            # Filter only auto and manual entries (not blacklist or skipped)
            filtered_logs = [log for log in unsynced_logs if log['type'] in ('auto', 'manual')]
            
            if not filtered_logs:
                print("SYNC WORKER: No valid logs to sync after filtering")
                self.sync_complete.emit("logs", True, "No valid logs to sync")
                return 0
                
            print(f"SYNC WORKER: Syncing {len(filtered_logs)} valid logs")
            
            # Import here to avoid circular imports
            import os
            import cv2
            from config import LOT_ID
            
            synced_count = 0
            total_count = len(filtered_logs)
            
            # Report initial progress
            self.sync_progress.emit("logs", 0, total_count)
            
            for idx, log in enumerate(filtered_logs):
                try:
                    # Skip if paused
                    self.mutex.lock()
                    paused = self._paused
                    self.mutex.unlock()
                    
                    if paused:
                        print("SYNC WORKER: Sync paused, stopping")
                        break
                        
                    # Report progress
                    completed = idx
                    self.sync_progress.emit("logs", completed, total_count)
                    
                    # Get log details
                    log_id = log['id']
                    lane = log['lane']
                    plate_id = log['plate_id']
                    entry_type = log['type']
                    timestamp = log['timestamp']
                    formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')
                    
                    # Get image if available
                    image_path = log.get('image_path')
                    image_data = None
                    
                    if image_path and os.path.exists(image_path):
                        try:
                            image_data = cv2.imread(image_path)
                        except Exception as img_err:
                            print(f"Error reading image {image_path}: {str(img_err)}")
                    
                    # Prepare form data for API
                    form_data = {
                        'plate_id': plate_id,
                        'lot_id': LOT_ID,
                        'lane': lane,
                        'type': entry_type,
                        'timestamp': formatted_time
                    }
                    
                    # Prepare files for API if image is available
                    files = None
                    if image_data is not None:
                        try:
                            _, img_encoded = cv2.imencode('.png', image_data)
                            img_bytes = img_encoded.tobytes()
                            files = {
                                'image': ('frame.png', img_bytes, 'image/png')
                            }
                        except Exception as img_err:
                            print(f"Error encoding image: {str(img_err)}")
                    
                    # Print diagnostic info
                    print(f"SYNC WORKER: Syncing log {log_id} - {lane} lane, plate {plate_id}")
                    
                    # Send to API
                    success, response = self.api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 15.0)  # Longer timeout for file uploads
                    )
                    
                    if success:
                        # Mark as synced in local DB regardless of the status field
                        # This includes cases where the API returns a 'denied' status
                        # as long as the HTTP response was successful (200 OK)
                        remote_id = response.get('id') if isinstance(response, dict) else None
                        
                        # Check if the response contains a denied status but still mark as synced
                        if isinstance(response, dict) and response.get('status') == 'denied':
                            print(f"SYNC WORKER: Log {log_id} was denied by server but marked as synced locally")
                        else:
                            print(f"SYNC WORKER: Successfully synced log {log_id}")
                            
                        # Mark as synced in both cases
                        self.db_manager.mark_log_synced(log_id)
                        synced_count += 1
                    else:
                        error_msg = response if response else "Unknown error"
                        print(f"SYNC WORKER: Failed to sync log {log_id}: {error_msg}")
                        # Don't sync more if API became unavailable
                        if "Connection" in str(error_msg) or "timeout" in str(error_msg).lower():
                            print("SYNC WORKER: API connection error, stopping sync")
                            break
                    
                except Exception as e:
                    print(f"SYNC WORKER: Error processing log: {str(e)}")
                    
            # Final progress update
            self.sync_progress.emit("logs", synced_count, total_count)
            self.sync_complete.emit("logs", True, f"Synced {synced_count}/{total_count} logs")
            
            return synced_count
            
        except Exception as e:
            print(f"SYNC WORKER Error: {str(e)}")
            self.sync_complete.emit("logs", False, str(e))
            return 0

class SyncService(QObject):
    """Service for managing synchronization between local DB and server"""
    # Signals for tracking synchronization status
    sync_status_changed = pyqtSignal(str, str)  # entity_type, status
    sync_progress = pyqtSignal(str, int, int)  # entity_type, completed, total
    sync_all_complete = pyqtSignal(int, str)  # count, context
    api_status_changed = pyqtSignal(bool)  # is_connected
    
    def __init__(self):
        super().__init__()
        
        # Initialize API client
        self.api_client = ApiClient(base_url=API_BASE_URL)
        
        # Initialize DB manager for local database operations
        self.db_manager = DBManager()
        
        # API connectivity status
        self.api_available = True
        self.api_retry_count = 0
        self.max_api_retries = 3
        
        # Connectivity tracking
        self.consecutive_failures = 0
        
        # Sync timers and timestamps
        self.last_sync_time = 0
        self.min_sync_interval = 30  # Minimum seconds between syncs (to prevent rapid consecutive syncs)
        
        # Token refresh tracking
        self.last_token_refresh_time = 0
        self.min_token_refresh_interval = 30  # Minimum seconds between token refreshes
        
        # Count tracking
        self.last_sync_count = 0
        
        # Create and start the sync worker thread
        print("Starting sync worker thread")
        self.sync_worker = SyncWorker(self)
        self.sync_worker.sync_progress.connect(self._handle_sync_progress)
        self.sync_worker.sync_complete.connect(self._handle_sync_complete)
        self.sync_worker.start()
        
        # Start API connection check timer
        print("Setting up API connection check timer")
        self.api_check_timer = QTimer(self)
        self.api_check_timer.timeout.connect(self.check_api_connection)
        self.api_check_timer.start(30000)  # Check every 30 seconds
        
        # Schedule an initial sync check after startup
        print("Scheduling initial sync check")
        QTimer.singleShot(5000, self._check_initial_sync)
    
    def _check_initial_sync(self):
        """Perform initial sync after app startup"""
        print("\n=== CHECKING FOR INITIAL SYNC ===")
        
        # Only proceed if API is available
        if not self.api_available:
            print("API not available, skipping initial sync")
            self.sync_all_complete.emit(0, "startup")
            return
            
        # Get pending counts
        counts = self.get_pending_sync_counts()
        
        if counts["total"] > 0:
            print(f"Found {counts['total']} items to sync at startup")
            # Use the startup context for initial sync
            self.sync_now(context="startup")
        else:
            print("No items to sync at startup")
            # Still notify with startup context so UI can update properly
            self.sync_all_complete.emit(0, "startup")
    
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
                # Mark as available immediately to allow other operations
                self.api_available = True
                self.api_status_changed.emit(True)
                # Resume worker but don't trigger a sync
                if hasattr(self, 'sync_worker'):
                    self.sync_worker.resume()
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
    
    def sync_now(self, entity_type=None, context=None):
        """
        Trigger a synchronization at startup or shutdown.
        If entity_type is None, sync everything.
        
        Args:
            entity_type (str, optional): Type of entity to sync ('logs', 'blacklist', etc.)
            context (str, optional): Context of the sync ('startup', 'shutdown', etc.)
            
        Returns:
            dict: A result dictionary containing success, count, and message
        """
        print(f"\n==== SYNC OPERATION STARTED ({context or 'system'}) ====")
        print(f"Triggered sync_now for entity_type: {entity_type or 'all'}")
        
        # Initialize result dictionary
        result = {
            "success": False,
            "count": 0,
            "message": ""
        }
        
        if not self.api_available:
            print("Cannot sync: API not available")
            # Emit completion with 0 count and context
            self.sync_all_complete.emit(0, context or "system")
            result["message"] = "API not available"
            return result
            
        # Always use the current context for the worker
        self.sync_worker.context = context
            
        # Check if we have a valid token before syncing
        if not self._ensure_fresh_token():
            print("Cannot sync: Failed to refresh authentication token")
            # Emit completion with 0 count and context
            self.sync_all_complete.emit(0, context or "system")
            result["message"] = "Authentication failed"
            return result
            
        try:
            counts = self.get_pending_sync_counts()
            if counts["total"] == 0:
                print("Nothing to sync")
                # Emit completion with 0 count and context
                self.sync_all_complete.emit(0, context or "system")
                result["success"] = True
                result["message"] = "Nothing to sync"
                return result
                
            print(f"Found {counts['total']} items to sync")
            
            # Sync specific entity type or all
            if entity_type:
                self.sync_worker.request_sync(entity_type)
            else:
                # Sync logs first, then blacklist (order matters)
                if counts["logs"] > 0:
                    self.sync_worker.request_sync("logs")
            
            # Update last sync time
            self.last_sync_time = time.time()
            
            # Store the count for later use
            self.last_sync_count = counts["total"]
            
            result["success"] = True
            result["count"] = counts["total"]
            result["message"] = "Sync started"
            return result
            
        except Exception as e:
            print(f"Error triggering sync: {str(e)}")
            # Emit completion with 0 count and context on error
            self.sync_all_complete.emit(0, context or "system")
            result["message"] = f"Error: {str(e)}"
            return result
    
    def stop(self):
        """Stop the sync service cleanly"""
        print("Stopping sync service...")
        try:
            # First check if there are unsynced items and sync them if possible
            if self.api_available:
                # CRITICAL FIX: Double-check API availability with a direct health check
                try:
                    print("Performing final API health check before shutdown sync")
                    is_api_healthy = self.api_client.check_health(timeout=(2.0, 3.0))
                    if not is_api_healthy:
                        print("API health check failed before shutdown, marking API as unavailable")
                        self.api_available = False
                except Exception as e:
                    print(f"Error during final API health check: {str(e)}")
                    self.api_available = False
                
                # Only proceed with sync if API is still available after check
                if self.api_available:
                    counts = self.get_pending_sync_counts()
                    if counts["total"] > 0:
                        print(f"Found {counts['total']} unsynced items before shutdown, attempting final sync")
                        # Use synchronous sync here to ensure it completes before shutdown
                        self._perform_shutdown_sync()
                    else:
                        # Signal completion with 0 count and shutdown context
                        self.sync_all_complete.emit(0, "shutdown")
                else:
                    print("API not available for shutdown sync, skipping")
                    # Signal completion with 0 count and shutdown context
                    self.sync_all_complete.emit(0, "shutdown")
            else:
                print("API not available for shutdown sync, skipping")
                # Signal completion with 0 count and shutdown context
                self.sync_all_complete.emit(0, "shutdown")
            
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
            # Ensure we emit completion signal even on error
            try:
                self.sync_all_complete.emit(0, "shutdown")
            except:
                pass
    
    def _perform_shutdown_sync(self):
        """Perform a synchronous sync operation during shutdown"""
        print("\n=== STARTING SHUTDOWN SYNC OPERATION ===")
        try:
            # This method directly syncs logs during shutdown
            import os
            import cv2
            from config import LOT_ID
            
            # CRITICAL FIX: Database connectivity check before proceeding
            try:
                # Verify that database is accessible before attempting sync
                db_test = self.db_manager._get_connection()
                if db_test is None:
                    print("DEBUG: Database not accessible for shutdown sync, aborting")
                    self.sync_all_complete.emit(0, "shutdown")
                    return
            except Exception as db_err:
                print(f"DEBUG: Database error during shutdown sync: {str(db_err)}")
                self.sync_all_complete.emit(0, "shutdown") 
                return
            
            # First check if API is available - don't proceed if not connected
            if not self.api_available:
                print("DEBUG: API not available for shutdown sync, aborting")
                # Signal completion with 0 count and shutdown context
                # Important: Don't mark anything as synced when API is unavailable
                self.sync_all_complete.emit(0, "shutdown")
                return
            
            # CRITICAL FIX: Double-check API with a direct health check before proceeding
            try:
                print("DEBUG: Performing quick API health check before shutdown sync")
                is_api_healthy = self.api_client.check_health(timeout=(2.0, 3.0))
                if not is_api_healthy:
                    print("DEBUG: API health check failed before shutdown sync")
                    self.api_available = False
                    self.sync_all_complete.emit(0, "shutdown")
                    return
                print("DEBUG: API health check passed for shutdown sync")
            except Exception as health_err:
                print(f"DEBUG: API health check error: {str(health_err)}")
                self.api_available = False
                self.sync_all_complete.emit(0, "shutdown")
                return
            
            # Check if we have a valid token before syncing
            print("DEBUG: Ensuring fresh token before shutdown sync")
            if not self._ensure_fresh_token():
                print("DEBUG: Failed to ensure valid token for shutdown sync")
                self.api_available = False
                self.sync_all_complete.emit(0, "shutdown")
                return
                
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=50)
            
            if not unsynced_logs:
                print("DEBUG: No logs to sync during shutdown")
                self.sync_all_complete.emit(0, "shutdown")
                return
                
            print(f"DEBUG: Found {len(unsynced_logs)} unsynced logs for shutdown sync")
            
            # Filter only auto and manual entries (not blacklist or skipped)
            filtered_logs = [log for log in unsynced_logs if log['type'] in ('auto', 'manual')]
            
            if not filtered_logs:
                print("DEBUG: No valid logs to sync after filtering for shutdown")
                self.sync_all_complete.emit(0, "shutdown")
                return
                
            print(f"DEBUG: Beginning sync of {len(filtered_logs)} logs during shutdown")
            
            synced_count = 0
            total_count = len(filtered_logs)
            
            # Report initial progress
            self.sync_progress.emit("logs", 0, total_count)
            
            for idx, log in enumerate(filtered_logs):
                try:
                    # Report progress
                    completed = idx
                    self.sync_progress.emit("logs", completed, total_count)
                    
                    # Get log details
                    log_id = log['id']
                    lane = log['lane']
                    plate_id = log['plate_id']
                    entry_type = log['type']
                    timestamp = log['timestamp']
                    formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')
                    
                    # Get image if available
                    image_path = log.get('image_path')
                    image_data = None
                    
                    if image_path and os.path.exists(image_path):
                        try:
                            image_data = cv2.imread(image_path)
                        except Exception as img_err:
                            print(f"DEBUG: Error reading image {image_path}: {str(img_err)}")
                    
                    # Prepare form data for API
                    form_data = {
                        'plate_id': plate_id,
                        'lot_id': LOT_ID,
                        'lane': lane,
                        'type': entry_type,
                        'timestamp': formatted_time
                    }
                    
                    # Prepare files for API if image is available
                    files = None
                    if image_data is not None:
                        try:
                            _, img_encoded = cv2.imencode('.png', image_data)
                            img_bytes = img_encoded.tobytes()
                            files = {
                                'image': ('frame.png', img_bytes, 'image/png')
                            }
                        except Exception as img_err:
                            print(f"DEBUG: Error encoding image: {str(img_err)}")
                    
                    # Send to API with moderate timeout
                    success, response = self.api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 10.0)  # 5s connect, 10s read
                    )
                    
                    if success:
                        # Mark as synced in local DB regardless of the status field
                        # This includes cases where the API returns a 'denied' status
                        # as long as the HTTP response was successful (200 OK)
                        
                        # Check if the response contains a denied status but still mark as synced
                        if isinstance(response, dict) and response.get('status') == 'denied':
                            print(f"DEBUG: Log {log_id} was denied by server but marked as synced locally during shutdown")
                        else:
                            print(f"DEBUG: Successfully synced log {log_id} during shutdown")
                        
                        # Mark as synced in both cases
                        self.db_manager.mark_log_synced(log_id)
                        synced_count += 1
                    else:
                        error_msg = response if response else "Unknown error"
                        print(f"DEBUG: Failed to sync log {log_id} during shutdown: {error_msg}")
                        
                        # Don't sync more if API became unavailable
                        if "Connection" in str(error_msg) or "timeout" in str(error_msg).lower():
                            print("DEBUG: API connection error during shutdown sync, stopping")
                            break
                
                except Exception as e:
                    print(f"DEBUG: Error processing log during shutdown: {str(e)}")
                    
            # Final progress update
            self.sync_progress.emit("logs", synced_count, total_count)
            
            print(f"\n=== SHUTDOWN SYNC COMPLETE: {synced_count}/{len(filtered_logs)} logs synced ===")
            
            # Signal completion with synced count and shutdown context
            print(f"DEBUG: Emitting sync_all_complete signal with count={synced_count}")
            self.sync_all_complete.emit(synced_count, "shutdown")
                
        except Exception as e:
            print(f"DEBUG: Error during shutdown sync: {str(e)}")
            # Signal completion with 0 count on error
            self.sync_all_complete.emit(0, "shutdown")
    
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

        # Log timing for debugging
        current_time = time.time()
        time_since_last = current_time - self.last_sync_time
        print(f"Time since last sync: {time_since_last:.1f}s")
        
        # Always update timestamp
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
                # Set API as available when refresh succeeds
                self.api_available = True
                return True
            else:
                print("Refresh token failed, falling back to credentials")
                # Mark API as unavailable if refresh fails
                self.api_available = False
            
        # Fall back to credentials if refresh token not available or failed
        if not token_refreshed and (auth_manager.username and auth_manager.password):
            print(f"Using credentials for pre-sync token refresh ({auth_manager.username})")
            
            # Attempt login to get fresh token
            try:
                success, message, _ = self.api_client.login(
                    auth_manager.username,
                    auth_manager.password,
                    timeout=(3.0, 5.0)
                )
                
                if success:
                    print("Token refreshed successfully before sync using credentials")
                    self.last_token_refresh_time = current_time
                    # Update API availability status when credentials succeed
                    self.api_available = True
                    return True
                else:
                    print(f"Failed to refresh token before sync: {message}")
                    # Update API availability status when credentials fail
                    self.api_available = False
                    return False
            except Exception as e:
                print(f"Login error during token refresh: {str(e)}")
                # Update API availability status on exception
                self.api_available = False
                return False
        
        # If we got here with no success, ensure API is marked unavailable
        if not token_refreshed:
            self.api_available = False
        
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