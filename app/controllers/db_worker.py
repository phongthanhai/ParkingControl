import threading
import time
import queue
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
                
                except Exception as e:
                    print(f"Error processing database operation: {str(e)}")
                    self.operation_complete.emit(operation_id, False, str(e))
                
                finally:
                    # Mark the task as done
                    self.queue.task_done()
                
            except Exception as e:
                print(f"Error in DB worker thread: {str(e)}")
    
    def stop(self):
        """Stop the worker thread"""
        self._running = False
        self.wait()
    
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
        
        # If we have an image but no path, save it now
        if not image_path and params.get('image') is not None:
            image_path = self.image_storage.save_image(
                params.get('image'),
                lane, 
                plate_id, 
                entry_type
            )
        
        # Store in database
        log_id = self.db_manager.add_log_entry(
            lane=lane,
            plate_id=plate_id,
            confidence=confidence,
            entry_type=entry_type,
            image_path=image_path,
            synced=synced
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