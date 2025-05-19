import os
import time
import threading
import cv2
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer, QMutex
from app.utils.db_manager import DBManager
from app.controllers.api_client import ApiClient
from config import LOT_ID, API_BASE_URL

class SyncStatus:
    """Enum-like class for sync status values"""
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    RUNNING = "running"

class SyncWorker(QThread):
    """Worker thread for background synchronization operations"""
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
        
    def run(self):
        while self._running:
            if not self._paused and self.sync_service.api_available:
                try:
                    # Force token refresh before each sync cycle
                    if self.sync_service._ensure_fresh_token():
                        print("Worker starting sync with fresh token")
                        # Sync in this order: vehicle blacklist, logs (which handles everything)
                        self._sync_blacklist()
                        sync_count = self._sync_logs()
                        
                        # Signal completion of entire sync process with count
                        sync_count = sync_count if sync_count is not None else 0
                        self.sync_service.last_sync_count = sync_count
                        self.sync_service.sync_all_complete.emit(sync_count)
                    else:
                        print("Worker skipping sync cycle due to token refresh failure")
                except Exception as e:
                    print(f"Sync worker error: {str(e)}")
            
            # Sleep between sync attempts
            time.sleep(10)  # 10 second sleep between sync cycles
    
    def stop(self):
        print("Stopping sync worker thread...")
        self.mutex.lock()
        self._running = False
        self.mutex.unlock()
        
        # Wait for the thread to finish with a timeout
        if self.isRunning():
            if not self.wait(5000):  # Wait up to 5 seconds
                print("WARNING: Sync worker thread did not stop gracefully, forcing termination")
                self.terminate()
                self.wait(500)  # Give it 500ms to terminate
            
        print("Sync worker thread stopped")
    
    def pause(self):
        self.mutex.lock()
        self._paused = True
        self.mutex.unlock()
    
    def resume(self):
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
            return 0
        
        self.mutex.lock()
        self._current_operation = "logs"
        self.mutex.unlock()
            
        try:
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=20)
            
            if not unsynced_logs:
                self.sync_complete.emit("logs", True, "No logs to sync")
                self.mutex.lock()
                self._current_operation = None
                self.mutex.unlock()
                return 0
                
            # Only sync auto and manual entries, not denied-blacklist or skipped
            filtered_logs = [log for log in unsynced_logs 
                            if log['type'] in ('auto', 'manual')]
            
            # If no valid logs after filtering, exit
            if not filtered_logs:
                self.sync_complete.emit("logs", True, "No valid logs to sync")
                self.mutex.lock()
                self._current_operation = None
                self.mutex.unlock()
                return 0
                
            total_logs = len(filtered_logs)
            self.sync_progress.emit("logs", 0, total_logs)
            print(f"Starting to sync {total_logs} logs to server...")
            
            # Process each log
            synced_count = 0
            failed_count = 0
            for i, log in enumerate(filtered_logs):
                if not self._running or self._paused:
                    break
                
                try:
                    # Check if this log is already marked as synced
                    if log.get('synced', 0) == 1:
                        print(f"Skipping log {log['id']} as it's already marked as synced")
                        continue
                        
                    # Prepare form data
                    form_data = {
                        'plate_id': log['plate_id'],
                        'lot_id': LOT_ID,
                        'lane': log['lane'],
                        'type': log['type'],
                        'timestamp': log['timestamp']
                    }
                    
                    print(f"Syncing log {log['id']}: {log['plate_id']} - {log['lane']} - {log['type']}") 
                    
                    # Handle image if available
                    files = None
                    if log['image_path'] and os.path.exists(log['image_path']):
                        # Read image and convert to bytes
                        try:
                            img = cv2.imread(log['image_path'])
                            if img is not None:
                                print(f"Found image for log {log['id']}, adding to sync")
                                _, img_encoded = cv2.imencode('.png', img)
                                img_bytes = img_encoded.tobytes()
                                files = {
                                    'image': ('frame.png', img_bytes, 'image/png')
                                }
                            else:
                                print(f"Image for log {log['id']} couldn't be read, sending without image")
                        except Exception as img_err:
                            print(f"Error processing image for log {log['id']}: {str(img_err)}")
                            # Continue without the image rather than failing the sync
                    
                    # Check if API is still available before attempting the call
                    if not self.sync_service.api_available:
                        print("API became unavailable during sync, aborting batch")
                        break
                        
                    # Send to API - guard-control endpoint handles everything
                    print(f"Sending log {log['id']} to API...")
                    try:
                        success, response = self.api_client.post_with_files(
                            'services/guard-control/',
                            data=form_data,
                            files=files,
                            timeout=(5.0, 15.0)
                        )
                        
                        if success:
                            # Mark as synced in a separate transaction to ensure status is updated
                            # even if other logs fail
                            self.db_manager.mark_log_synced(log['id'])
                            synced_count += 1
                            print(f"Successfully synced log {log['id']}")
                        else:
                            # Log failure but continue with next entries
                            failed_count += 1
                            # Check if this is an auth failure
                            if isinstance(response, str) and "Authentication failed" in response:
                                print(f"Authentication failed during sync, need to refresh token")
                                # Force API check to run in the main thread
                                self.sync_service.api_available = False
                                self.sync_service.api_status_changed.emit(False)
                                break
                            print(f"Failed to sync log {log['id']}: {response}")
                    except Exception as api_err:
                        failed_count += 1
                        print(f"API error syncing log {log['id']}: {str(api_err)}")
                        # Check for connection errors that indicate API is unavailable
                        if "Connection" in str(api_err) or "timeout" in str(api_err).lower():
                            print("Connection error detected, stopping sync batch")
                            self.sync_service.api_available = False
                            self.sync_service.api_status_changed.emit(False)
                            break
                    
                    # Update progress (ensure we report accurate progress)
                    progress = i + 1
                    self.sync_progress.emit("logs", progress, total_logs)
                    
                    # Small delay to prevent UI freezing and avoid overwhelming the server
                    time.sleep(0.2)
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Error syncing log {log['id']}: {str(e)}")
                    # Don't mark as synced on error, it will be retried next time
            
            # Always emit final progress with the actual count
            self.sync_progress.emit("logs", synced_count + failed_count, total_logs)
                
            # Show detailed summary
            result_message = f"Synced {synced_count}/{total_logs} log entries"
            if failed_count > 0:
                result_message += f" ({failed_count} failed)"
                
            # Only report success if we actually synced something
            self.sync_complete.emit("logs", synced_count > 0, result_message)
                                   
        except Exception as e:
            self.sync_complete.emit("logs", False, f"Log sync error: {str(e)}")
            synced_count = 0
        
        self.mutex.lock()
        self._current_operation = None
        self.mutex.unlock()
        
        return synced_count

class SyncService(QObject):
    """
    Service to manage synchronization between local SQLite and backend API.
    Handles both automatic background sync and manual sync operations.
    """
    sync_status_changed = pyqtSignal(str, str)  # type, status
    sync_progress = pyqtSignal(str, int, int)   # entity_type, completed, total
    api_status_changed = pyqtSignal(bool)       # is_available
    sync_all_complete = pyqtSignal(int)         # count of synced items
    
    def __init__(self):
        super().__init__()
        self.db_manager = DBManager()
        self.api_client = ApiClient(base_url=API_BASE_URL)
        self.api_available = True
        self.api_retry_count = 0
        self.max_api_retries = 3
        self.last_sync_attempt = 0
        self.sync_cooldown = 60  # seconds between sync attempts
        self.auto_reconnect = False  # Don't automatically reconnect
        self.last_sync_count = 0  # Track number of items synced in last operation
        
        # Set up background sync worker
        self.sync_worker = SyncWorker(self)
        self.sync_worker.sync_progress.connect(self._handle_sync_progress)
        self.sync_worker.sync_complete.connect(self._handle_sync_complete)
        
        # Set up API check timer with more frequent checks
        self.api_check_timer = QTimer()
        self.api_check_timer.timeout.connect(self.check_api_connection)
        self.api_check_timer.start(3000)  # Check API status every 3 seconds for faster disconnection detection
        
        # Initial API check
        self.check_api_connection()
        
        # Start background sync worker
        self.sync_worker.start()
    
    def can_sync(self):
        """Check if synchronization is possible."""
        if not self.api_available:
            return False
            
        current_time = time.time()
        if current_time - self.last_sync_attempt < self.sync_cooldown:
            return False
            
        self.last_sync_attempt = current_time
        return True
    
    def check_api_connection(self):
        """Check if the backend API server is available."""
        try:
            # Use the asynchronous non-blocking health check
            self.api_client.check_health_async(
                callback=self._handle_api_check_result,
                timeout=(2.0, 3.0)
            )
            
        except Exception as e:
            # Immediately mark as disconnected on any exception
            print(f"Backend API connection check error: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)
            self.sync_worker.pause()
            
            # Continue incrementing retry count for logging
            self.api_retry_count += 1

    def _handle_api_check_result(self, success):
        """Handle result from asynchronous API health check"""
        try:
            # Update API status based on check result
            if success:
                if not self.api_available:
                    print("Backend API connection restored, resuming sync operations")
                    self.api_available = True
                    self.api_retry_count = 0
                    self.api_status_changed.emit(True)
                    self.sync_worker.resume()
                    
                    # Auto-trigger sync when connection is restored
                    QTimer.singleShot(1000, lambda: self.sync_now())
            else:
                # Mark as disconnected immediately after failure for faster UI feedback
                if self.api_available:
                    print("Backend API connection lost, pausing sync operations")
                
                self.api_available = False
                self.api_status_changed.emit(False)
                self.sync_worker.pause()
                
                # Continue incrementing retry count for logging purposes
                self.api_retry_count += 1
        except Exception as e:
            print(f"Error handling API check result: {str(e)}")
            # In case of error, assume API is down
            self.api_available = False
            self.api_status_changed.emit(False)
            self.sync_worker.pause()
    
    def _handle_sync_progress(self, entity_type, completed, total):
        """Handle progress updates from the sync worker."""
        self.sync_progress.emit(entity_type, completed, total)
    
    def _handle_sync_complete(self, entity_type, success, message):
        """Handle completion notification from the sync worker."""
        status = SyncStatus.SUCCESS if success else SyncStatus.FAILED
        self.sync_status_changed.emit(entity_type, status)
        print(f"Sync {entity_type}: {status} - {message}")
    
    def sync_now(self, entity_type=None):
        """
        Manually trigger a synchronization.
        If entity_type is None, sync everything.
        """
        if not self.api_available:
            print("Cannot sync: API is not available")
            return False
            
        # Always try to check connection first
        self.check_api_connection()
        
        if not self.api_available:
            return False
        
        print("Starting manual sync process...")
        
        # Force token refresh before sync to avoid authentication issues
        if not self._ensure_fresh_token():
            print("Failed to refresh authentication token before sync")
            self.api_available = False
            self.api_status_changed.emit(False)
            return False
        
        # Perform sync operations directly in the main thread for manual sync
        # This avoids potential threading issues when user initiates sync
        if entity_type is None or entity_type == "blacklist":
            print("Manually syncing blacklist...")
            self.sync_status_changed.emit("blacklist", SyncStatus.RUNNING)
            
            # Handle blacklist sync
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
                    self.sync_status_changed.emit("blacklist", SyncStatus.SUCCESS)
                    print(f"Manually synced blacklist: Updated {len(response)} records")
                else:
                    self.sync_status_changed.emit("blacklist", SyncStatus.FAILED)
                    print(f"Failed to retrieve blacklist data: {response}")
                    
                    # Check if this is an authentication issue
                    if isinstance(response, str) and "Authentication failed" in response:
                        print("Authentication failed during blacklist sync")
                        self.api_available = False
                        self.api_status_changed.emit(False)
                        return False
            except Exception as e:
                self.sync_status_changed.emit("blacklist", SyncStatus.FAILED)
                print(f"Blacklist sync error: {str(e)}")
                
                # Check for connection errors
                if "Connection" in str(e) or "timeout" in str(e).lower():
                    print("Connection error detected during blacklist sync")
                    self.api_available = False
                    self.api_status_changed.emit(False)
                    return False
            
        if entity_type is None or entity_type == "logs":
            print("Manually syncing logs...")
            self.sync_status_changed.emit("logs", SyncStatus.RUNNING)
            
            # Handle logs sync
            try:
                # Get unsynced logs
                unsynced_logs = self.db_manager.get_unsynced_logs(limit=20)
                
                if not unsynced_logs:
                    print("No logs to sync")
                    self.sync_status_changed.emit("logs", SyncStatus.SUCCESS)
                    self.last_sync_count = 0
                    self.sync_all_complete.emit(0)
                    return True
                    
                # Only sync auto and manual entries, not denied-blacklist or skipped
                filtered_logs = [log for log in unsynced_logs 
                                if log['type'] in ('auto', 'manual')]
                
                if not filtered_logs:
                    print("No valid logs to sync after filtering")
                    self.sync_status_changed.emit("logs", SyncStatus.SUCCESS)
                    self.last_sync_count = 0
                    self.sync_all_complete.emit(0)
                    return True
                    
                total_logs = len(filtered_logs)
                self.sync_progress.emit("logs", 0, total_logs)
                print(f"Starting to sync {total_logs} logs to server...")
                
                # Process each log
                synced_count = 0
                failed_count = 0
                for i, log in enumerate(filtered_logs):
                    try:
                        # Check if this log is already marked as synced
                        if log.get('synced', 0) == 1:
                            print(f"Skipping log {log['id']} as it's already marked as synced")
                            continue
                            
                        # Prepare form data
                        form_data = {
                            'plate_id': log['plate_id'],
                            'lot_id': LOT_ID,
                            'lane': log['lane'],
                            'type': log['type'],
                            'timestamp': log['timestamp']
                        }
                        
                        print(f"Syncing log {log['id']}: {log['plate_id']} - {log['lane']} - {log['type']}") 
                        
                        # Handle image if available
                        files = None
                        if log.get('image_path') and os.path.exists(log['image_path']):
                            try:
                                # Read image and convert to bytes
                                img = cv2.imread(log['image_path'])
                                if img is not None:
                                    print(f"Found image for log {log['id']}, adding to sync")
                                    _, img_encoded = cv2.imencode('.png', img)
                                    img_bytes = img_encoded.tobytes()
                                    files = {
                                        'image': ('frame.png', img_bytes, 'image/png')
                                    }
                                else:
                                    print(f"Image for log {log['id']} couldn't be read, sending without image")
                            except Exception as img_err:
                                print(f"Error processing image for log {log['id']}: {str(img_err)}")
                                # Continue without the image rather than failing the sync
                        
                        # Check if API is still available
                        if not self.api_available:
                            print("API became unavailable during sync, aborting batch")
                            break
                        
                        # Send to API - guard-control endpoint handles everything
                        print(f"Sending log {log['id']} to API...")
                        try:
                            success, response = self.api_client.post_with_files(
                                'services/guard-control/',
                                data=form_data,
                                files=files,
                                timeout=(5.0, 15.0)
                            )
                            
                            if success:
                                # Mark as synced in a separate transaction
                                self.db_manager.mark_log_synced(log['id'])
                                synced_count += 1
                                print(f"Successfully synced log {log['id']}")
                            else:
                                failed_count += 1
                                print(f"Failed to sync log {log['id']}: {response}")
                                
                                # Check if it's an authentication failure
                                if isinstance(response, str) and "Authentication failed" in response:
                                    print("Authentication failed during sync, stopping batch")
                                    self.api_available = False
                                    self.api_status_changed.emit(False)
                                    break
                                
                        except Exception as api_err:
                            failed_count += 1
                            print(f"API error syncing log {log['id']}: {str(api_err)}")
                            
                            # Check for connection errors that indicate API is unavailable
                            if "Connection" in str(api_err) or "timeout" in str(api_err).lower():
                                print("Connection error detected, stopping sync batch")
                                self.api_available = False
                                self.api_status_changed.emit(False)
                                break
                        
                        # Update progress
                        progress = i + 1
                        self.sync_progress.emit("logs", progress, total_logs)
                        
                        # Small delay to prevent UI freezing and avoid overwhelming the server
                        time.sleep(0.2)
                        
                    except Exception as e:
                        failed_count += 1
                        print(f"Error syncing log {log['id']}: {str(e)}")
                        # Don't mark as synced on error, so it can be retried next time
                
                # Emit final progress with actual count, not total
                self.sync_progress.emit("logs", synced_count + failed_count, total_logs)
                
                # Show detailed result
                result_message = f"Synced {synced_count}/{total_logs} logs"
                if failed_count > 0:
                    result_message += f" ({failed_count} failed)"
                
                # Only report success if we actually synced something
                if synced_count > 0:
                    self.sync_status_changed.emit("logs", SyncStatus.SUCCESS)
                    print(f"Successfully {result_message}")
                else:
                    self.sync_status_changed.emit("logs", SyncStatus.FAILED)
                    print(f"Failed to sync any logs")
                
            except Exception as e:
                self.sync_status_changed.emit("logs", SyncStatus.FAILED)
                print(f"Error in log sync process: {str(e)}")
                
                # Check for connection errors
                if "Connection" in str(e) or "timeout" in str(e).lower():
                    print("Connection error detected during log sync")
                    self.api_available = False
                    self.api_status_changed.emit(False)
                    return False
        
            # Signal completion of entire sync process with synced count
            self.last_sync_count = synced_count
            self.sync_all_complete.emit(synced_count)
        return True
    
    def _ensure_fresh_token(self):
        """Ensure we have a fresh authentication token by forcing a login"""
        from app.utils.auth_manager import AuthManager
        auth_manager = AuthManager()
        
        # Use AuthManager's cooldown system to determine if refresh needed
        if not auth_manager.should_refresh_token():
            # Either refresh is in progress or token is fresh enough
            return auth_manager.is_authenticated()
        
        # Check if we have stored credentials
        if not auth_manager.has_stored_credentials():
            print("No stored credentials available for token refresh")
            auth_manager.finish_token_refresh(success=False)
            return False
            
        print(f"Pre-sync token refresh for {auth_manager.username}")
        
        try:
            # Attempt login to get fresh token
            success, message, _ = self.api_client.login(
                auth_manager.username,
                auth_manager.password,
                timeout=(3.0, 5.0)
            )
            
            if success:
                print("Token refreshed successfully before sync")
                auth_manager.finish_token_refresh(success=True)
                return True
            else:
                print(f"Failed to refresh token before sync: {message}")
                auth_manager.finish_token_refresh(success=False)
                return False
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            auth_manager.finish_token_refresh(success=False)
            return False
    
    def reconnect(self):
        """Manually attempt to reconnect to the API"""
        self.api_retry_count = 0
        
        print("Attempting to reconnect to API server...")
        
        # Define timeout
        api_check_timeout = (2.0, 3.0)
        
        try:
            # Use the asynchronous health check (doesn't require auth)
            self.api_client.check_health_async(
                callback=lambda success: self._handle_reconnect_health_check(success, api_check_timeout),
                timeout=api_check_timeout
            )
            
            return True  # Return success for initial attempt
            
        except Exception as e:
            print(f"Reconnection error: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)
            return False

    def _handle_reconnect_health_check(self, success, timeout):
        """Handle health check result during reconnect attempt"""
        try:
            if success:
                print("Server is available, checking authentication...")
                # Server is up, now check if token has expired by making an authenticated request
                self._perform_async_auth_check(timeout)
            else:
                print("Server is not available")
                self.api_available = False
                self.api_status_changed.emit(False)
        except Exception as e:
            print(f"Error handling reconnect health check: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)

    def _perform_async_auth_check(self, timeout):
        """Perform auth check asynchronously"""
        try:
            # Define an inner function to handle auth check result
            def handle_auth_result(auth_success, auth_response):
                self._handle_reconnect_auth_check(auth_success, auth_response)
            
            # Create a worker thread for auth check
            worker = threading.Thread(
                target=self._do_auth_check,
                args=(timeout, handle_auth_result)
            )
            worker.daemon = True
            worker.start()
            
        except Exception as e:
            print(f"Error performing async auth check: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)

    def _do_auth_check(self, timeout, callback):
        """Perform the actual auth check in a separate thread"""
        try:
            auth_result = self.api_client.get(
                'services/lot-occupancy/1', 
                timeout=timeout,
                retry_on_auth_fail=False  # Don't auto-retry
            )
            # Call the callback with the result
            callback(auth_result[0], auth_result[1] if len(auth_result) > 1 else None)
        except Exception as e:
            print(f"Auth check thread error: {str(e)}")
            callback(False, str(e))

    def _handle_reconnect_auth_check(self, success, response):
        """Handle authentication check result during reconnect"""
        try:
            # If auth failed but server is up, we need to refresh token
            if not success:
                print("Authentication failed, attempting to refresh token...")
                # Check if auth_manager has stored credentials
                from app.utils.auth_manager import AuthManager
                auth_manager = AuthManager()
                
                # If we have stored credentials, try to login again
                if auth_manager.username and auth_manager.password:
                    print(f"Attempting to refresh authentication token for user {auth_manager.username}...")
                    
                    # Use the async API call
                    self._perform_async_login(
                        auth_manager.username, 
                        auth_manager.password,
                        timeout=(3.0, 5.0)
                    )
                else:
                    print("No stored credentials available for token refresh")
                    self.api_available = False
                    self.api_status_changed.emit(False)
            else:
                print("Authentication is valid")
                self.api_available = True
                self.api_status_changed.emit(True)
                self.sync_worker.resume()
        except Exception as e:
            print(f"Error handling reconnect auth check: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)

    def _perform_async_login(self, username, password, timeout):
        """Perform login asynchronously"""
        try:
            # Define an inner function to handle login result
            def handle_login_result(login_success, login_data):
                # Parse result data 
                if isinstance(login_data, tuple) and len(login_data) >= 2:
                    login_success, login_msg = login_data[0], login_data[1]
                else:
                    login_success = False
                    login_msg = "Unknown login error"
                    
                if login_success:
                    print("Authentication token refreshed successfully")
                    self.api_available = True
                    self.api_status_changed.emit(True)
                    self.sync_worker.resume()
                else:
                    print(f"Failed to refresh authentication token: {login_msg}")
                    self.api_available = False
                    self.api_status_changed.emit(False)
            
            # Create a worker thread for login
            worker = threading.Thread(
                target=self._do_login,
                args=(username, password, timeout, handle_login_result)
            )
            worker.daemon = True
            worker.start()
            
        except Exception as e:
            print(f"Error performing async login: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)

    def _do_login(self, username, password, timeout, callback):
        """Perform the actual login in a separate thread"""
        try:
            login_result = self.api_client.login(
                username, 
                password,
                timeout=timeout
            )
            # Call the callback with the result
            callback(login_result[0], login_result)
        except Exception as e:
            print(f"Login thread error: {str(e)}")
            callback(False, (False, str(e), None))
    
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
    
    def stop(self):
        """Stop the sync service."""
        print("Stopping sync service and worker threads...")
        try:
            # Stop the API check timer
            if hasattr(self, 'api_check_timer') and self.api_check_timer.isActive():
                self.api_check_timer.stop()
                print("API check timer stopped")
            
            # Signal the worker to stop first
            if self.sync_worker and self.sync_worker.isRunning():
                print("Signaling sync worker thread to stop...")
                self.sync_worker.stop()
                print("Sync worker thread stopped")
                
            # Clear any references that could cause circular dependencies
            self.sync_worker = None
            
        except Exception as e:
            print(f"Error during sync service shutdown: {str(e)}")
            # Try to force termination as a last resort
            if hasattr(self, 'sync_worker') and self.sync_worker and self.sync_worker.isRunning():
                try:
                    self.sync_worker.terminate()
                    self.sync_worker.wait()
                except:
                    pass
    
    def __del__(self):
        """Clean up resources."""
        try:
            self.stop()
        except Exception as e:
            print(f"Error during sync service cleanup: {str(e)}") 