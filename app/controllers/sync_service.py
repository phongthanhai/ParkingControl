import os
import time
import threading
import cv2
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
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
        self.mutex = threading.Lock()
        
    def run(self):
        while self._running:
            if not self._paused and self.sync_service.api_available:
                try:
                    # Sync in this order: vehicle blacklist, logs (which handles everything)
                    self._sync_blacklist()
                    self._sync_logs()
                except Exception as e:
                    print(f"Sync worker error: {str(e)}")
            
            # Sleep between sync attempts
            time.sleep(10)  # 10 second sleep between sync cycles
    
    def stop(self):
        self._running = False
    
    def pause(self):
        self._paused = True
    
    def resume(self):
        self._paused = False
    
    def _sync_blacklist(self):
        """Sync blacklist data from server to local"""
        if not self.sync_service.can_sync():
            return
            
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
    
    def _sync_logs(self):
        """Sync log entries from local to server using the comprehensive guard-control endpoint"""
        if not self.sync_service.can_sync():
            return
            
        try:
            # Get unsynced logs
            unsynced_logs = self.db_manager.get_unsynced_logs(limit=20)
            
            if not unsynced_logs:
                return
                
            self.sync_progress.emit("logs", 0, len(unsynced_logs))
            
            # Process each log
            synced_count = 0
            for i, log in enumerate(unsynced_logs):
                try:
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
                    if log['image_path'] and os.path.exists(log['image_path']):
                        # Read image and convert to bytes
                        img = cv2.imread(log['image_path'])
                        if img is not None:
                            _, img_encoded = cv2.imencode('.png', img)
                            img_bytes = img_encoded.tobytes()
                            files = {
                                'image': ('frame.png', img_bytes, 'image/png')
                            }
                    
                    # Send to API - guard-control endpoint handles everything
                    success, response = self.api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 15.0)
                    )
                    
                    if success:
                        # Mark as synced
                        self.db_manager.mark_log_synced(log['id'])
                        synced_count += 1
                    else:
                        print(f"Failed to sync log {log['id']}: {response}")
                    
                    self.sync_progress.emit("logs", i+1, len(unsynced_logs))
                    time.sleep(0.5)  # Small delay between API calls
                    
                except Exception as e:
                    print(f"Error syncing log {log['id']}: {str(e)}")
            
            self.sync_complete.emit("logs", synced_count > 0, 
                                   f"Synced {synced_count}/{len(unsynced_logs)} log entries")
                                   
        except Exception as e:
            self.sync_complete.emit("logs", False, f"Log sync error: {str(e)}")

class SyncService(QObject):
    """
    Service to manage synchronization between local SQLite and backend API.
    Handles both automatic background sync and manual sync operations.
    """
    sync_status_changed = pyqtSignal(str, str)  # type, status
    sync_progress = pyqtSignal(str, int, int)   # entity_type, completed, total
    api_status_changed = pyqtSignal(bool)       # is_available
    
    def __init__(self):
        super().__init__()
        self.db_manager = DBManager()
        self.api_client = ApiClient(base_url=API_BASE_URL)
        self.api_available = True
        self.api_retry_count = 0
        self.max_api_retries = 3
        self.last_sync_attempt = 0
        self.sync_cooldown = 60  # seconds between sync attempts
        
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
        
        if entity_type is None or entity_type == "blacklist":
            self.sync_status_changed.emit("blacklist", SyncStatus.RUNNING)
            self.sync_worker._sync_blacklist()
            
        if entity_type is None or entity_type == "logs":
            self.sync_status_changed.emit("logs", SyncStatus.RUNNING)
            self.sync_worker._sync_logs()
        
        return True
    
    def get_pending_sync_counts(self):
        """Get counts of pending items for each sync category."""
        return {
            "logs": len(self.db_manager.get_unsynced_logs(limit=1000)),
            "total": len(self.db_manager.get_unsynced_logs(limit=1000))
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