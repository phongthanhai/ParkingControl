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
                        self._sync_logs()
                        
                        # Signal completion of entire sync process
                        self.sync_service.sync_all_complete.emit()
                    else:
                        print("Worker skipping sync cycle due to token refresh failure")
                except Exception as e:
                    print(f"Sync worker error: {str(e)}")
            
            # Sleep between sync attempts
            time.sleep(10)  # 10 second sleep between sync cycles
    
    def stop(self):
        self.mutex.lock()
        self._running = False
        self.mutex.unlock()
    
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
            return
        
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
                return
                
            # Only sync auto and manual entries, not denied-blacklist or skipped
            filtered_logs = [log for log in unsynced_logs 
                            if log['type'] in ('auto', 'manual')]
            
            # If no valid logs after filtering, exit
            if not filtered_logs:
                self.sync_complete.emit("logs", True, "No valid logs to sync")
                self.mutex.lock()
                self._current_operation = None
                self.mutex.unlock()
                return
                
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
                    
                    # Send to API - guard-control endpoint handles everything
                    print(f"Sending log {log['id']} to API...")
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
                        failed_count += 1
                        print(f"Failed to sync log {log['id']}: {response}")
                    
                    # Update progress (ensure we report accurate progress)
                    progress = i + 1
                    self.sync_progress.emit("logs", progress, total_logs)
                    
                    # Small delay to prevent UI freezing
                    time.sleep(0.1)
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Error syncing log {log['id']}: {str(e)}")
            
            # Always emit final progress at 100%
            if total_logs > 0:
                self.sync_progress.emit("logs", total_logs, total_logs)
                
            # Show detailed summary
            result_message = f"Synced {synced_count}/{total_logs} log entries"
            if failed_count > 0:
                result_message += f" ({failed_count} failed)"
                
            self.sync_complete.emit("logs", synced_count > 0, result_message)
                                   
        except Exception as e:
            self.sync_complete.emit("logs", False, f"Log sync error: {str(e)}")
        
        self.mutex.lock()
        self._current_operation = None
        self.mutex.unlock()

class SyncService(QObject):
    """
    Service to manage synchronization between local SQLite and backend API.
    Handles both automatic background sync and manual sync operations.
    """
    sync_status_changed = pyqtSignal(str, str)  # type, status
    sync_progress = pyqtSignal(str, int, int)   # entity_type, completed, total
    api_status_changed = pyqtSignal(bool)       # is_available
    sync_all_complete = pyqtSignal()            # emitted when all sync is done
    
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
        
        # Set up background sync worker
        self.sync_worker = SyncWorker(self)
        self.sync_worker.sync_progress.connect(self._handle_sync_progress)
        self.sync_worker.sync_complete.connect(self._handle_sync_complete)
        
        # Set up API check timer
        self.api_check_timer = QTimer()
        self.api_check_timer.timeout.connect(self.check_api_connection)
        self.api_check_timer.start(10000)  # Check API status every 10 seconds
        
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
        """Check if the API server is available."""
        try:
            # Use a short timeout for connectivity checks
            api_check_timeout = (2.0, 3.0)
            
            # Use the dedicated health check endpoint
            success, _ = self.api_client.get('services/health', timeout=api_check_timeout, auth_required=False)
            
            # Update API status
            if success and not self.api_available:
                self.api_available = True
                self.api_retry_count = 0
                self.api_status_changed.emit(True)
                print("API connection restored, resuming sync operations")
                self.sync_worker.resume()
            elif not success and self.api_available:
                self.api_retry_count += 1
                if self.api_retry_count >= self.max_api_retries:
                    self.api_available = False
                    self.api_status_changed.emit(False)
                    print("API connection lost, pausing sync operations")
                    self.sync_worker.pause()
            
        except Exception as e:
            self.api_retry_count += 1
            if self.api_retry_count >= self.max_api_retries:
                self.api_available = False
                self.api_status_changed.emit(False)
                print(f"API connection check error: {str(e)}")
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
            except Exception as e:
                self.sync_status_changed.emit("blacklist", SyncStatus.FAILED)
                print(f"Blacklist sync error: {str(e)}")
            
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
                    self.sync_all_complete.emit()
                    return True
                    
                # Only sync auto and manual entries, not denied-blacklist or skipped
                filtered_logs = [log for log in unsynced_logs 
                                if log['type'] in ('auto', 'manual')]
                
                if not filtered_logs:
                    print("No valid logs to sync after filtering")
                    self.sync_status_changed.emit("logs", SyncStatus.SUCCESS)
                    self.sync_all_complete.emit()
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
                        
                        # Send to API - guard-control endpoint handles everything
                        print(f"Sending log {log['id']} to API...")
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
                        
                        # Update progress
                        progress = i + 1
                        self.sync_progress.emit("logs", progress, total_logs)
                        
                    except Exception as e:
                        failed_count += 1
                        print(f"Error syncing log {log['id']}: {str(e)}")
                
                # Always emit final progress at 100%
                if total_logs > 0:
                    self.sync_progress.emit("logs", total_logs, total_logs)
                
                # Show detailed result
                result_message = f"Synced {synced_count}/{total_logs} logs"
                if failed_count > 0:
                    result_message += f" ({failed_count} failed)"
                
                if synced_count > 0:
                    self.sync_status_changed.emit("logs", SyncStatus.SUCCESS)
                    print(f"Successfully {result_message}")
                else:
                    self.sync_status_changed.emit("logs", SyncStatus.FAILED)
                    print(f"Failed to sync any logs")
                
            except Exception as e:
                self.sync_status_changed.emit("logs", SyncStatus.FAILED)
                print(f"Error in log sync process: {str(e)}")
        
        # Signal completion of entire sync process
        self.sync_all_complete.emit()
        return True
    
    def _ensure_fresh_token(self):
        """Ensure we have a fresh authentication token by forcing a login"""
        from app.utils.auth_manager import AuthManager
        auth_manager = AuthManager()
        
        # Check if we have stored credentials
        if not (auth_manager.username and auth_manager.password):
            print("No stored credentials available for token refresh")
            return False
            
        print(f"Pre-sync token refresh for {auth_manager.username}")
        
        # Attempt login to get fresh token
        success, message, _ = self.api_client.login(
            auth_manager.username,
            auth_manager.password,
            timeout=(3.0, 5.0)
        )
        
        if success:
            print("Token refreshed successfully before sync")
            return True
        else:
            print(f"Failed to refresh token before sync: {message}")
            return False
    
    def reconnect(self):
        """Manually attempt to reconnect to the API"""
        self.api_retry_count = 0
        
        print("Attempting to reconnect to API server...")
        
        # First try to check if server is available
        api_check_timeout = (2.0, 3.0)
        try:
            # Use the dedicated health check endpoint (doesn't require auth)
            success, _ = self.api_client.get('services/health', timeout=api_check_timeout, auth_required=False)
            
            if success:
                print("Server is available, checking authentication...")
                # Server is up, now check if token has expired by making an authenticated request
                auth_success, auth_response = self.api_client.get('services/lot-occupancy/1', timeout=api_check_timeout)
                
                # If auth failed but server is up, we need to refresh token
                if not auth_success:
                    print("Authentication failed, attempting to refresh token...")
                    # Check if auth_manager has stored credentials
                    from app.utils.auth_manager import AuthManager
                    auth_manager = AuthManager()
                    
                    # If we have stored credentials, try to login again
                    if auth_manager.username and auth_manager.password:
                        print(f"Attempting to refresh authentication token for user {auth_manager.username}...")
                        login_success, login_msg, _ = self.api_client.login(
                            auth_manager.username, 
                            auth_manager.password,
                            timeout=(3.0, 5.0)
                        )
                        if login_success:
                            print("Authentication token refreshed successfully")
                            self.api_available = True
                            self.api_status_changed.emit(True)
                            self.sync_worker.resume()
                            return True
                        else:
                            print(f"Failed to refresh authentication token: {login_msg}")
                            self.api_available = False
                            self.api_status_changed.emit(False)
                            return False
                    else:
                        print("No stored credentials available for token refresh")
                        self.api_available = False
                        self.api_status_changed.emit(False)
                        return False
                else:
                    print("Authentication is valid")
                    self.api_available = True
                    self.api_status_changed.emit(True)
                    self.sync_worker.resume()
                    return True
            else:
                print("Server is not available")
                self.api_available = False
                self.api_status_changed.emit(False)
                return False
            
        except Exception as e:
            print(f"Reconnection error: {str(e)}")
            self.api_available = False
            self.api_status_changed.emit(False)
            return False
    
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
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.stop()
            self.sync_worker.wait(1000)  # Wait up to 1 second
        
        if self.api_check_timer and self.api_check_timer.isActive():
            self.api_check_timer.stop()
    
    def __del__(self):
        """Clean up resources."""
        self.stop() 