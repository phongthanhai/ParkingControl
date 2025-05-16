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

class ApiCheckWorker(QThread):
    """Worker thread for asynchronous API health checks"""
    finished = pyqtSignal(bool)
    
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
    
    def run(self):
        try:
            api_check_timeout = (2.0, 3.0)
            success, _ = self.api_client.get('services/health', 
                                           timeout=api_check_timeout, 
                                           auth_required=False)
            self.finished.emit(success)
        except Exception as e:
            print(f"API check error: {str(e)}")
            self.finished.emit(False)

class SyncWorker(QThread):
    """Worker thread for background synchronization operations"""
    sync_progress = pyqtSignal(str, int, int)  # entity_type, completed, total
    sync_complete = pyqtSignal(str, bool, str)  # entity_type, success, message
    
    def __init__(self, sync_service):
        super().__init__()
        self.setObjectName("SyncWorker")  # Set object name for debugging
        self.sync_service = sync_service
        self.db_manager = DBManager()
        self.api_client = ApiClient(base_url=API_BASE_URL)
        self._running = True
        self._paused = False
        self.mutex = QMutex()
        self._current_operation = None
        
    def run(self):
        print("SyncWorker thread started")
        try:
            while self._running:
                if not self._paused and self.sync_service.api_available:
                    try:
                        # Sync in this order: vehicle blacklist, logs (which handles everything)
                        self._sync_blacklist()
                        self._sync_logs()
                        
                        # Signal completion of entire sync process
                        self.sync_service.sync_all_complete.emit()
                    except Exception as e:
                        print(f"Sync worker error: {str(e)}")
                
                # Sleep between sync attempts
                for i in range(10):  # Check stop flag every second instead of sleeping for 10s at once
                    if not self._running:
                        break
                    time.sleep(1)
        except Exception as e:
            print(f"Error in SyncWorker thread: {str(e)}")
        finally:
            print("SyncWorker thread ending")
    
    def stop(self):
        print("SyncWorker stop requested")
        self.mutex.lock()
        self._running = False
        self._paused = False  # Make sure we're not paused when stopping
        self.mutex.unlock()
        
        # Wake the condition if it's waiting
        if hasattr(self, 'condition') and self.condition:
            self.condition.wakeAll()
            
        print("SyncWorker stop request completed")
    
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
            print("Starting blacklist sync...")
            # Get blacklisted vehicles from API
            success, response = self.api_client.get(
                'vehicles/blacklisted/',
                params={'skip': 0, 'limit': 1000},
                timeout=(3.0, 10.0)
            )
            
            if success and response:
                # Update local database
                self.db_manager.update_blacklist(response)
                print(f"Successfully synced {len(response)} blacklist records")
                self.sync_complete.emit("blacklist", True, f"Updated {len(response)} blacklist records")
            else:
                print(f"Failed to retrieve blacklist data: {response}")
                self.sync_complete.emit("blacklist", False, "Failed to retrieve blacklist data")
        
        except Exception as e:
            print(f"Blacklist sync error: {str(e)}")
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
            print("Starting log sync...")
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=20)
            
            if not unsynced_logs:
                print("No logs to sync")
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
                print("No valid logs to sync after filtering")
                self.sync_complete.emit("logs", True, "No valid logs to sync")
                self.mutex.lock()
                self._current_operation = None
                self.mutex.unlock()
                return
                
            total_logs = len(filtered_logs)
            print(f"Attempting to sync {total_logs} logs")
            self.sync_progress.emit("logs", 0, total_logs)
            
            # Process each log
            synced_count = 0
            for i, log in enumerate(filtered_logs):
                if not self._running or self._paused:
                    break
                
                try:
                    print(f"Processing log {i+1}/{total_logs}: {log['plate_id']}")
                    # Prepare form data
                    form_data = {
                        'plate_id': log['plate_id'],
                        'lot_id': LOT_ID,
                        'lane': log['lane'],
                        'type': log['type'],
                        'timestamp': log['timestamp']
                    }
                    
                    print(f"Sending data: {form_data}")
                    
                    # Handle image if available
                    files = None
                    if log['image_path'] and os.path.exists(log['image_path']):
                        print(f"Including image from {log['image_path']}")
                        # Read image and convert to bytes
                        img = cv2.imread(log['image_path'])
                        if img is not None:
                            _, img_encoded = cv2.imencode('.png', img)
                            img_bytes = img_encoded.tobytes()
                            files = {
                                'image': ('frame.png', img_bytes, 'image/png')
                            }
                        else:
                            print(f"Failed to read image from {log['image_path']}")
                    
                    # Send to API - guard-control endpoint handles everything
                    success, response = self.api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 15.0)
                    )
                    
                    print(f"API Response: Success={success}, Response={response}")
                    
                    if success:
                        # Mark as synced
                        self.db_manager.mark_log_synced(log['id'])
                        synced_count += 1
                        print(f"Successfully synced log {log['id']}")
                    else:
                        print(f"Failed to sync log {log['id']}: {response}")
                    
                    # Update progress (ensure we report accurate progress)
                    progress = i + 1
                    self.sync_progress.emit("logs", progress, total_logs)
                    
                    # Small delay to prevent UI freezing
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error syncing log {log['id']}: {str(e)}")
            
            # Always emit final progress at 100%
            if total_logs > 0:
                self.sync_progress.emit("logs", total_logs, total_logs)
                
            print(f"Sync complete. Successfully synced {synced_count}/{total_logs} logs")
            self.sync_complete.emit("logs", synced_count > 0, 
                                   f"Synced {synced_count}/{total_logs} log entries")
                                   
        except Exception as e:
            print(f"Log sync error: {str(e)}")
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
        # Create and start the API check worker
        worker = ApiCheckWorker(self.api_client)
        
        def handle_check_result(success):
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
        
        worker.finished.connect(handle_check_result)
        worker.start()
    
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
        
        if entity_type is None or entity_type == "blacklist":
            self.sync_status_changed.emit("blacklist", SyncStatus.RUNNING)
            self.sync_worker._sync_blacklist()
            
        if entity_type is None or entity_type == "logs":
            self.sync_status_changed.emit("logs", SyncStatus.RUNNING)
            self.sync_worker._sync_logs()
        
        return True
    
    def reconnect(self):
        """Manually attempt to reconnect to the API"""
        self.api_retry_count = 0
        
        # First try to check if server is available
        api_check_timeout = (2.0, 3.0)
        try:
            # Use the dedicated health check endpoint (doesn't require auth)
            success, _ = self.api_client.get('services/health', timeout=api_check_timeout, auth_required=False)
            
            if success:
                # Server is up, now check if token has expired by making an authenticated request
                auth_success, _ = self.api_client.get('services/lot-occupancy/1', timeout=api_check_timeout)
                
                # If auth failed but server is up, we need to refresh token
                if not auth_success:
                    print("API is available but authentication failed. Token may have expired.")
                    # Check if auth_manager has stored credentials
                    from app.utils.auth_manager import AuthManager
                    auth_manager = AuthManager()
                    
                    # If we have stored credentials, try to login again
                    if hasattr(auth_manager, 'username') and hasattr(auth_manager, 'password'):
                        print("Attempting to refresh authentication token...")
                        login_success, _, _ = self.api_client.login(
                            auth_manager.username, 
                            auth_manager.password,
                            timeout=(3.0, 5.0)
                        )
                        if login_success:
                            print("Authentication token refreshed successfully")
                            self.api_available = True
                            self.check_api_connection()  # Update status after token refresh
                            return True
                        else:
                            print("Failed to refresh authentication token")
                            return False
            
            # Standard connection check if token refresh wasn't needed or possible
            self.check_api_connection()
            return self.api_available
            
        except Exception as e:
            print(f"Reconnection error: {str(e)}")
            return False
    
    def get_pending_sync_counts(self):
        """Get counts of pending items for each sync category."""
        # Filter to count only auto and manual entries (not blacklist or skipped)
        try:
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=1000)
            filtered_logs = [log for log in unsynced_logs 
                           if log['type'] in ('auto', 'manual')]
            total = len(filtered_logs)
            
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
        """Stop the sync service and cleanup threads."""
        print("Stopping sync service...")
        
        # Stop the sync worker
        if self.sync_worker and self.sync_worker.isRunning():
            print("Stopping sync worker thread...")
            self.sync_worker.stop()
            self.sync_worker.wait(2000)  # Wait up to 2 seconds
            
            # Force quit if still running
            if self.sync_worker.isRunning():
                print("Force terminating sync worker thread...")
                self.sync_worker.terminate()
                self.sync_worker.wait()
        
        # Stop the API check timer
        if self.api_check_timer and self.api_check_timer.isActive():
            print("Stopping API check timer...")
            self.api_check_timer.stop()
        
        print("Sync service stopped successfully")
    
    def __del__(self):
        """Clean up resources."""
        self.stop() 