import os
import time
import cv2
import threading
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer, QMutex, QMetaObject, Qt, Q_ARG
from app.utils.db_manager import DBManager
from app.controllers.api_client import ApiClient
from config import LOT_ID, API_BASE_URL
from app.utils.image_storage import ImageStorage
from app.controllers.simple_api_client import SimpleApiClient
from app.utils.connection_state import ConnectionManager

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
        self.mutex = QMutex()  # Use QMutex instead of threading.Lock()
        self._running = True
        self._paused = False
        self._current_operation = None
        self.context = None  # Track context for completion messaging
        
    def run(self):
        """Main worker loop"""
        while self._running:
            self.mutex.lock()
            if self._paused:
                self.mutex.unlock()
                self.msleep(1000)  # Sleep for 1 second when paused
                continue
            self.mutex.unlock()
            
            # Check if sync service allows sync operations
            if self.sync_service.can_sync():
                self._sync_logs()
            
            # Sleep for a reasonable interval between sync attempts
            self.msleep(30000)  # 30 seconds
    
    def stop(self):
        """Stop the worker thread"""
        self.mutex.lock()
        self._running = False
        self.mutex.unlock()
        
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
                
            total_count = len(filtered_logs)
            synced_count = 0
            
            # Emit initial progress
            self.sync_progress.emit("logs", 0, total_count)
            
            for i, log in enumerate(filtered_logs):
                # Check if we should stop or pause
                self.mutex.lock()
                if not self._running or self._paused:
                    self.mutex.unlock()
                    break
                self.mutex.unlock()
                
                # Check if sync service still allows operations
                if not self.sync_service.can_sync():
                    print("SYNC WORKER: Sync no longer allowed, stopping")
                    break
                
                try:
                    log_id = log['id']
                    lane = log['lane']
                    plate_id = log['plate_id']
                    entry_type = log['type']
                    timestamp = log['timestamp']
                    image_path = log.get('image_path')
                    
                    # Format timestamp for API
                    if isinstance(timestamp, (int, float)):
                        from datetime import datetime
                        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')
                    else:
                        formatted_time = str(timestamp)
                    
                    # Load image if available
                    image_data = None
                    if image_path:
                        try:
                            image_data = cv2.imread(image_path)
                        except Exception as img_err:
                            print(f"SYNC WORKER: Error loading image {image_path}: {str(img_err)}")
                    
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
                            print(f"SYNC WORKER: Error encoding image: {str(img_err)}")
                    
                    # Send to API using the simple API client
                    success, response = self.sync_service.api_client.post_guard_control(form_data, files)
                    
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
                        if "circuit breaker" in str(error_msg).lower() or "unavailable" in str(error_msg).lower():
                            print("SYNC WORKER: API unavailable, stopping sync")
                            break
                    
                    # Update progress
                    self.sync_progress.emit("logs", synced_count, total_count)
                    
                except Exception as e:
                    print(f"SYNC WORKER: Error processing log: {str(e)}")
                    
            # Final progress update
            self.sync_progress.emit("logs", synced_count, total_count)
            self.sync_complete.emit("logs", True, f"Synced {synced_count}/{total_count} logs")
            
            return synced_count
            
        except Exception as e:
            print(f"SYNC WORKER: Error in sync operation: {str(e)}")
            self.sync_complete.emit("logs", False, f"Sync error: {str(e)}")
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
        
        # CRITICAL FIX: Use simple API client and centralized connection manager
        self.api_client = SimpleApiClient(base_url=API_BASE_URL)
        self.connection_manager = ConnectionManager()
        
        # Connect to connection manager signals
        self.connection_manager.state_changed.connect(self.api_status_changed.emit)
        
        # Initialize DB manager for local database operations
        self.db_manager = DBManager()
        
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
        
        # Start health monitoring timer
        print("Setting up health monitoring timer")
        self.health_check_timer = QTimer(self)
        self.health_check_timer.timeout.connect(self._perform_health_check)
        self.health_check_timer.start(30000)  # Check every 30 seconds
        
        # Schedule an initial sync check after startup
        print("Scheduling initial sync check with 30-second delay")
        QTimer.singleShot(30000, self._check_initial_sync)  # Increased from 15000ms to 30000ms

    def can_sync(self):
        """Check if sync operations are allowed based on connection state"""
        return self.connection_manager.is_online()

    def _perform_health_check(self):
        """Simplified health check using the centralized connection manager"""
        try:
            # The API client's health check automatically updates the connection manager
            self.api_client.health_check()
        except Exception as e:
            print(f"SyncService health check error: {str(e)}")

    def _check_initial_sync(self):
        """Perform initial sync after app startup"""
        print("\n=== CHECKING FOR INITIAL SYNC ===")
        
        # Check if we can sync
        if not self.can_sync():
            print("API not available for initial sync, scheduling retry in 15 seconds")
            QTimer.singleShot(15000, self._check_initial_sync)
            return
            
        print("API available, checking for unsynced items...")
        QTimer.singleShot(500, self._perform_initial_sync_after_delay)
    
    def _perform_initial_sync_after_delay(self):
        """Perform the actual initial sync after a small delay to ensure DB is ready"""
        try:
            # Check API status again after the delay
            if not self.can_sync():
                print("API became unavailable during initial sync delay, scheduling retry")
                QTimer.singleShot(15000, self._check_initial_sync)
                return
                
            counts = self.get_pending_sync_counts()
            
            if counts["total"] > 0:
                print(f"Found {counts['total']} items to sync at startup")
                # Use the startup context for initial sync
                self.sync_now(context="startup")
            else:
                print("No items to sync at startup")
                # Still notify with startup context so UI can update properly
                self.sync_all_complete.emit(0, "startup")
        except Exception as e:
            print(f"Error during initial sync after delay: {str(e)}")
            # Signal completion with error
            self.sync_all_complete.emit(0, "startup")

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
        
        if not self.can_sync():
            print("Cannot sync: API not available")
            # Emit completion with 0 count and context
            self.sync_all_complete.emit(0, context or "system")
            result["message"] = "API not available"
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
    
    def _handle_sync_progress(self, entity_type, completed, total):
        """Handle progress updates from the sync worker."""
        self.sync_progress.emit(entity_type, completed, total)
    
    def _handle_sync_complete(self, entity_type, success, message):
        """Handle completion notification from the sync worker."""
        status = SyncStatus.SUCCESS if success else SyncStatus.FAILED
        self.sync_status_changed.emit(entity_type, status)
        print(f"Sync {entity_type}: {status} - {message}")
    
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