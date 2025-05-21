import threading
import time
import queue
import sqlite3
from PyQt5.QtCore import QThread, pyqtSignal
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage

class DBOperationType:
    """Enum for database operation types"""
    LOG_ENTRY = "log_entry"
    PARKING_SESSION = "parking_session"
    BARRIER_ACTION = "barrier_action"
    VEHICLE = "vehicle"

class DBWorker(QThread):
    """
    Worker thread for handling database operations asynchronously.
    This prevents UI freezing when database operations are performed.
    """
    operation_complete = pyqtSignal(str, bool, object)  # operation_id, success, result

    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self._running = True
        self.db_manager = DBManager()
        self.image_storage = ImageStorage()
        
        # Connection retry settings
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        
        # Start the worker thread
        self.start()

    def run(self):
        """Main thread loop that processes database operations from the queue"""
        while self._running:
            try:
                # Get the next operation from the queue with a timeout
                # This allows the thread to check _running periodically
                try:
                    operation = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process the operation
                operation_id = operation.get('id')
                operation_type = operation.get('type')
                params = operation.get('params', {})
                
                retry_count = 0
                while retry_count <= self.max_retries:
                    try:
                        # Perform the appropriate database operation based on type
                        if operation_type == DBOperationType.LOG_ENTRY:
                            result = self._handle_log_entry(params)
                            self.operation_complete.emit(operation_id, True, result)
                        
                        elif operation_type == DBOperationType.PARKING_SESSION:
                            result = self._handle_parking_session(params)
                            self.operation_complete.emit(operation_id, True, result)
                        
                        elif operation_type == DBOperationType.BARRIER_ACTION:
                            result = self._handle_barrier_action(params)
                            self.operation_complete.emit(operation_id, True, result)
                        
                        elif operation_type == DBOperationType.VEHICLE:
                            result = self._handle_vehicle(params)
                            self.operation_complete.emit(operation_id, True, result)
                        
                        else:
                            print(f"Unknown operation type: {operation_type}")
                            self.operation_complete.emit(operation_id, False, f"Unknown operation type: {operation_type}")
                            
                        # If we get here, the operation succeeded, so break the retry loop
                        break
                    
                    except sqlite3.OperationalError as e:
                        # Specific handling for database locked errors
                        if "database is locked" in str(e) and retry_count < self.max_retries:
                            retry_count += 1
                            print(f"Database locked, retrying operation {operation_id} (attempt {retry_count}/{self.max_retries})")
                            time.sleep(self.retry_delay * retry_count)  # Exponential backoff
                            continue
                        else:
                            # Either not a locking error or max retries exceeded
                            print(f"Database error in operation {operation_id}: {str(e)}")
                            self.operation_complete.emit(operation_id, False, f"Database error: {str(e)}")
                            break
                            
                    except Exception as e:
                        print(f"Error processing database operation {operation_id}: {str(e)}")
                        self.operation_complete.emit(operation_id, False, str(e))
                        break
                
                # Mark the task as done
                self.queue.task_done()
                
            except Exception as e:
                print(f"Error in DB worker thread: {str(e)}")
    
    def stop(self):
        """Stop the worker thread"""
        print("Stopping DB worker thread...")
        self._running = False
        
        # Wake up the thread if it's waiting on the queue
        try:
            # Put a sentinel value in the queue to wake up the thread
            self.queue.put(None, block=False)
        except queue.Full:
            pass
        
        # Wait for the thread to finish with a timeout
        if self.isRunning():
            if not self.wait(5000):  # Wait up to 5 seconds
                print("WARNING: DB worker thread did not stop gracefully, forcing termination")
                self.terminate()
                self.wait(500)  # Give it 500ms to terminate
            
        print("DB worker thread stopped")
        
        # Clean up resources
        self.db_manager = None
        self.image_storage = None
    
    def queue_operation(self, operation_type, **kwargs):
        """
        Queue a database operation to be processed asynchronously
        
        Args:
            operation_type: The type of operation (from DBOperationType)
            **kwargs: Parameters for the operation
            
        Returns:
            str: Operation ID that can be used to track completion
        """
        operation_id = f"{operation_type}_{time.time()}_{threading.get_ident()}"
        
        self.queue.put({
            'id': operation_id,
            'type': operation_type,
            'params': kwargs
        })
        
        return operation_id
    
    def _handle_log_entry(self, params):
        """Handle storing a log entry in the database"""
        lane = params.get('lane')
        plate_id = params.get('plate_id')
        confidence = params.get('confidence', 0.0)
        entry_type = params.get('entry_type')
        image_path = params.get('image_path')
        synced = params.get('synced', False)
        timestamp = params.get('timestamp')  # Get timestamp if provided
        
        # If we have an image but no path, save it now
        if not image_path and params.get('image_data') is not None:
            image_path = self.image_storage.save_image(
                params.get('image_data'),
                lane, 
                plate_id, 
                entry_type,
                timestamp=timestamp  # Pass timestamp to ensure consistency
            )
        
        # Store in database
        log_id = self.db_manager.add_log_entry(
            lane=lane,
            plate_id=plate_id,
            confidence=confidence,
            entry_type=entry_type,
            image_path=image_path,
            synced=synced,
            timestamp=timestamp  # Pass timestamp to ensure consistency
        )
        
        return {
            'log_id': log_id,
            'image_path': image_path
        }
    
    def _handle_parking_session(self, params):
        """Handle creating or updating a parking session"""
        action = params.get('action', 'create')
        lane = params.get('lane')
        plate_id = params.get('plate_id')
        confidence = params.get('confidence', 0.0)
        image_path = params.get('image_path')
        
        if action == 'create' and lane == 'entry':
            # Start a new parking session
            session_id = self.db_manager.start_parking_session(
                plate_id=plate_id,
                lot_id=params.get('lot_id'),
                entry_confidence=confidence,
                entry_img=image_path
            )
            return {'session_id': session_id}
            
        elif action == 'update' and lane == 'exit':
            # End an existing parking session
            session_id = self.db_manager.end_parking_session(
                plate_id=plate_id,
                lot_id=params.get('lot_id'),
                exit_confidence=confidence,
                exit_img=image_path
            )
            return {'session_id': session_id}
        
        return None
    
    def _handle_barrier_action(self, params):
        """Handle recording a barrier action"""
        session_id = params.get('session_id')
        action_type = params.get('action_type')
        trigger_type = params.get('trigger_type')
        
        action_id = self.db_manager.add_barrier_action(
            session_id=session_id,
            action_type=action_type,
            trigger_type=trigger_type
        )
        
        return {'action_id': action_id}
    
    def _handle_vehicle(self, params):
        """Handle adding or updating a vehicle"""
        plate_id = params.get('plate_id')
        is_blacklisted = params.get('is_blacklisted', False)
        
        vehicle_id = self.db_manager.add_vehicle(
            plate_id=plate_id,
            is_blacklisted=is_blacklisted
        )
        
        return {'vehicle_id': vehicle_id} 