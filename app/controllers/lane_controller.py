from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QTimer
import cv2
import time
import threading
import numpy as np
from config import (
    CAMERA_SOURCES, CAMERA_RESOLUTION, CAMERA_FPS,
    VIETNAMESE_PLATE_PATTERN, OCR_RATE_LIMIT
)
from app.models.detection import PlateDetector
from app.controllers.api_client import PlateRecognizer

class LaneState:
    IDLE = "idle"
    DETECTING = "detecting"
    PROCESSING = "processing"
    PAUSED = "paused"
    ERROR = "error"

class LaneWorker(QThread):
    detection_signal = pyqtSignal(str, object, str, float, bool)  # lane, frame, text, confidence, valid
    status_signal = pyqtSignal(str, str, dict)  # lane, status, data
    error_signal = pyqtSignal(str, str)  # lane, error
    
    def __init__(self, lane_type):
        super().__init__()
        self.lane_type = lane_type
        self.state = LaneState.IDLE
        
        # Thread safety objects
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.camera_lock = threading.Lock()
        
        # Processing objects - initialize here, but don't connect signals until in thread
        self.detector = None
        self.recognizer = None
        
        # Control flags
        self._running = True
        self._paused = False
        self._camera_index = CAMERA_SOURCES.get(lane_type)
        self.last_api_call = 0
        
        # Error handling
        self._error_count = 0
        self._max_errors = 3
        self._last_frame = None
        
        # Initialize in the thread's run method to avoid cross-thread issues
        self._cap = None
        
        # Cooldown
        self.cooldown_active = False
        self.cooldown_timer  = None
        self.frame_buffer_clear_count = 0
        self.required_clear_frames = 10
        
        # Store last detection data for manual verification
        self.last_detection_data = None
        
        # Flag to check if signals are connected
        self._signals_connected = False
    
    def run(self):
        self._initialize_resources()
        self._main_loop()
    
    def _initialize_resources(self):
        try:
            # Initialize processing resources in the worker thread
            print(f"{self.lane_type}: Initializing resources in thread {threading.current_thread().name}")
            self.detector = PlateDetector()
            
            # Create recognizer and connect signals
            self.recognizer = PlateRecognizer()
            
            # Connect signals directly in the thread
            if not self._signals_connected:
                print(f"{self.lane_type}: Connecting PlateRecognizer signals")
                # Ensure we disconnect any existing connections first to avoid duplicates
                try:
                    self.recognizer.error_signal.disconnect()
                    self.recognizer.result_signal.disconnect()
                except TypeError:
                    # No connections exist yet, which is fine
                    pass
                    
                # Connect with direct connection type for best performance within the same thread
                self.recognizer.error_signal.connect(
                    lambda msg: self.error_signal.emit(self.lane_type, f"API Error: {msg}"),
                    type=Qt.DirectConnection
                )
                
                # Connect the result signal to handle OCR results asynchronously
                self.recognizer.result_signal.connect(
                    self._handle_ocr_result,
                    type=Qt.DirectConnection
                )
                
                self._signals_connected = True
                print(f"{self.lane_type}: Signals connected successfully")
            
            self._init_camera()
        except Exception as e:
            print(f"{self.lane_type}: Resource initialization failed: {str(e)}")
            self.error_signal.emit(self.lane_type, f"Initialization Error: {str(e)}")
            self.state = LaneState.ERROR
    
    def _init_camera(self):
        try:
            if self._camera_index is None:
                raise ValueError(f"No camera configured for {self.lane_type}")
            
            # Set initial timeout for camera initialization
            init_start_time = time.time()
            init_timeout = 5.0  # 5 seconds max for initialization
            
            with self.camera_lock:
                if self._cap is not None and self._cap.isOpened():
                    self._cap.release()
                
                self._cap = cv2.VideoCapture(self._camera_index)
                
                # Check if camera opened successfully with timeout
                attempts = 0
                max_attempts = 3
                while not self._cap.isOpened() and attempts < max_attempts:
                    # Check for timeout
                    if time.time() - init_start_time > init_timeout:
                        raise RuntimeError(f"Camera {self._camera_index} initialization timed out")
                        
                    # Wait a bit and retry
                    time.sleep(0.5)
                    attempts += 1
                    self._cap = cv2.VideoCapture(self._camera_index)
                
                if not self._cap.isOpened():
                    raise RuntimeError(f"Camera {self._camera_index} not available after {max_attempts} attempts")
                
                # Camera configuration
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
                self._cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                
                # Warm-up period - read a few frames to stabilize
                # Add timeout to warm-up as well
                warmup_start = time.time()
                warmup_timeout = 3.0  # 3 seconds max for warm-up
                
                for _ in range(5):
                    # Check for timeout during warm-up
                    if time.time() - warmup_start > warmup_timeout:
                        print(f"Camera {self._camera_index} warm-up timed out, continuing anyway")
                        break
                        
                    ret, _ = self._cap.read()
                    if not ret:
                        print(f"Warning: Failed to read frame during camera warm-up")
                    time.sleep(0.1)
                
                self.state = LaneState.DETECTING
                self._error_count = 0
                
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Camera Initialization Error: {str(e)}")
            self.state = LaneState.ERROR
            
            # Schedule a retry if we haven't exceeded max errors
            if self._error_count < self._max_errors:
                self._error_count += 1
                QTimer.singleShot(2000, self._init_camera)
    
    def _main_loop(self):
        while self._running:
            # Handle paused state
            if self._paused:
                # Use condition variable for efficient pausing
                self.mutex.lock()
                self.condition.wait(self.mutex)
                self.mutex.unlock()
                continue
                
            # Handle error state
            if self.state == LaneState.ERROR:
                time.sleep(0.5)
                continue
                
            # Read frame with proper locking
            frame = self._read_frame()
            if frame is None:
                continue
                
            # Process the frame
            self._process_frame(frame)
                
            # Small delay to prevent CPU hogging
            time.sleep(0.01)
    
    def _read_frame(self):
        if self._cap is None or not self._cap.isOpened():
            if self.state != LaneState.ERROR:
                self.error_signal.emit(self.lane_type, "Camera not available")
                self.state = LaneState.ERROR
                QTimer.singleShot(2000, self._init_camera)
            return None
            
        try:
            with self.camera_lock:
                ret, frame = self._cap.read()
                
            if not ret or frame is None:
                self._error_count += 1
                if self._error_count > self._max_errors:
                    self.error_signal.emit(self.lane_type, "Failed to capture frame")
                    self.state = LaneState.ERROR
                    QTimer.singleShot(2000, self._init_camera)
                return None
                
            self._error_count = 0
            self._last_frame = frame.copy()  # Keep a copy for debugging
            return frame
            
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Frame Capture Error: {str(e)}")
            self.state = LaneState.ERROR
            QTimer.singleShot(2000, self._init_camera)
            return None
    
    def _process_frame(self, frame):
        if self.detector is None:
            return
            
        try:
            if self.cooldown_active:
                self.detection_signal.emit(
                    self.lane_type,
                    frame,
                    "Clearing buffer...",
                    0.0,
                    False
                )
                
                self.frame_buffer_clear_count += 1
                if self.frame_buffer_clear_count >= self.required_clear_frames:
                    if self.cooldown_timer is not None and not self.cooldown_timer.isActive():
                        self.cooldown_active = False
                return
                
            # Only process frames if we're in DETECTING state
            if self.state != LaneState.DETECTING:
                # Skip processing for other states
                return
                
            # Detection
            display_frame, plate_img = self.detector.detect(frame)
            
            # Ensure we have valid data types for signal
            plate_text = "Scanning..."
            confidence = 0.0
            
            # Emit detection signal with initial values
            self.detection_signal.emit(
                self.lane_type,
                display_frame,
                plate_text,
                confidence,
                False
            )
            
            # OCR processing with rate limiting
            if plate_img is not None and (time.time() - self.last_api_call) > OCR_RATE_LIMIT:
                print(f"{self.lane_type}: License plate detected, starting OCR")
                
                # Store the last detection data for potential manual entry
                self.last_detection_data = {
                    "text": "",
                    "confidence": 0.0,
                    "image": display_frame,  # Store the display frame with the rectangle drawn
                    "plate_img": plate_img,  # Store the cropped plate image separately
                    "is_valid": False
                }
                
                # Set state to processing
                print(f"{self.lane_type}: Changing state from {self.state} to {LaneState.PROCESSING}")
                self.state = LaneState.PROCESSING
                
                try:
                    # This will start the async API call, results will come through _handle_ocr_result
                    result = self.recognizer.process(plate_img)
                    if result is not None:
                        print(f"{self.lane_type}: PlateRecognizer returned result directly (not async): {result}")
                    else:
                        print(f"{self.lane_type}: PlateRecognizer API call started - waiting for async result")
                    
                    # Start a timeout timer to handle the case where the API doesn't respond
                    # This prevents us from getting stuck waiting for a response
                    QTimer.singleShot(5000, lambda: self._check_ocr_timeout())
                    
                except Exception as e:
                    print(f"{self.lane_type}: Error starting OCR: {str(e)}")
                    self.error_signal.emit(self.lane_type, f"PlateRecognizer API Error: {str(e)}")
                    # Handle as API timeout
                    self._handle_api_timeout(display_frame)
                
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Processing Error: {str(e)}")
    
    def _check_ocr_timeout(self):
        """Check if we've been waiting too long for OCR results"""
        # Only run this check if we're still in processing state
        if self.state == LaneState.PROCESSING:
            print(f"{self.lane_type}: OCR timeout detected - still in PROCESSING state after 5s")
            # We've waited too long, handle as a timeout
            if self.last_detection_data:
                display_frame = self.last_detection_data.get("image")
                self._handle_api_timeout(display_frame)
    
    def _handle_api_timeout(self, display_frame):
        """Handle API timeout scenario"""
        print(f"{self.lane_type}: Handling API timeout - changing state to PAUSED and requesting manual entry")
        self.state = LaneState.PAUSED  # Update state
        self._pause_processing()
        self.status_signal.emit(
            self.lane_type,
            "requires_manual",
            {"reason": "API timeout", "image": display_frame, "text": ""}
        )
    
    def _handle_ocr_result(self, result):
        """Handle OCR result from the PlateRecognizer API"""
        # Unpack the result
        plate_text, confidence = result

        # Skip if we got a null result
        if plate_text is None:
            # If we're in PROCESSING state, this is a timeout
            if self.state == LaneState.PROCESSING:
                self.state = LaneState.DETECTING
                # Handle as an API timeout if we have detection data
                if self.last_detection_data:
                    display_frame = self.last_detection_data.get("image")
                    self._handle_api_timeout(display_frame)
            return
        
        # Update last API call time
        self.last_api_call = time.time()
        
        # Process the result if we have valid data
        if self.last_detection_data:
            # Update the last detection data
            self.last_detection_data["text"] = plate_text
            self.last_detection_data["confidence"] = confidence
            is_valid = VIETNAMESE_PLATE_PATTERN.match(plate_text) is not None
            self.last_detection_data["is_valid"] = is_valid
            
            # Get the display frame from the stored data
            display_frame = self.last_detection_data.get("image")
            
            # Change state based on result - do this BEFORE emitting signals
            if is_valid and confidence >= 0.9:
                # High confidence valid plate - proceed automatically
                self.state = LaneState.PAUSED  # Pause processing while gate operates
                
                # CRITICAL FIX: First emit the detection signal with updated text/confidence
                self.detection_signal.emit(
                    self.lane_type,
                    display_frame,
                    plate_text,
                    confidence,
                    is_valid
                )
                
                # Then emit success signal to trigger guard control
                print(f"Emitting success signal for {plate_text} with confidence {confidence}")
                self._pause_processing()
                self.status_signal.emit(
                    self.lane_type,
                    "success",
                    {"text": plate_text, "confidence": confidence, "image": display_frame}
                )
            else:
                # Low confidence or invalid plate - require manual verification
                self.state = LaneState.PAUSED
                
                # First emit the detection signal with updated text/confidence
                self.detection_signal.emit(
                    self.lane_type,
                    display_frame,
                    plate_text,
                    confidence,
                    is_valid
                )
                
                # Then emit manual verification needed
                self._pause_processing()
                if not is_valid:
                    print(f"Emitting manual required (invalid format) for {plate_text}")
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "invalid format", "text": plate_text, "confidence": confidence, "image": display_frame}
                    )
                else:  # confidence < 0.9
                    print(f"Emitting manual required (low confidence) for {plate_text} with confidence {confidence}")
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "low confidence", "text": plate_text, "confidence": confidence, "image": display_frame}
                    )
        else:
            # No detection data available - this shouldn't happen but handle gracefully
            print("Warning: OCR result received but no detection data available")
            self.state = LaneState.DETECTING
    
    def _pause_processing(self):
        self.mutex.lock()
        self._paused = True
        self.state = LaneState.PAUSED
        self.mutex.unlock()
    
    def resume_processing(self):
        """Resume processing after a pause (used after user action)"""
        print(f"{self.lane_type}: Resuming processing, previous state: {self.state}")
        
        # Start cooldown timer
        self.cooldown_active = True
        # Clear existing cooldown timer
        if self.cooldown_timer is not None and self.cooldown_timer.isActive():
            self.cooldown_timer.stop()
            
        # New timer
        self.cooldown_timer = QTimer()
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self._end_cooldown)
        self.cooldown_timer.start(8000) #seconds of cooldown before allowing detection
        
        # Clear last detection data
        self.last_detection_data = None
        
        # Make sure we reset state to DETECTING when cooldown ends
        self.mutex.lock()
        try:
            self._paused = False
            # Set the state explicitly to DETECTING if not in error
            if self.state != LaneState.ERROR:
                self.state = LaneState.DETECTING
            self.condition.wakeAll()
        finally:
            self.mutex.unlock()
        
        print(f"{self.lane_type}: Processing resumed, new state: {self.state}, cooldown active")
    
    def _end_cooldown(self):
        """End cooldown period and resume normal detection"""
        print(f"{self.lane_type}: Ending cooldown period, resuming detection")
        self.cooldown_active = False
        self.frame_buffer_clear_count = 0
        
        # Resume detection explicitly
        self.mutex.lock()
        try:
            if self.state != LaneState.ERROR:
                self.state = LaneState.DETECTING
                print(f"{self.lane_type}: State set to DETECTING after cooldown")
        finally:
            self.mutex.unlock()
            
        # Clear last detection data if it's still lingering
        self.last_detection_data = None
    
    def restart_camera(self):
        """Attempt to restart the camera after an error"""
        if self.state == LaneState.ERROR:
            self._init_camera()
    
    def stop(self):
        """Clean shutdown of the worker thread"""
        print(f"Stopping {self.lane_type} lane worker thread...")
        
        try:
            # Stop any active cooldown timer
            if self.cooldown_timer is not None and self.cooldown_timer.isActive():
                self.cooldown_timer.stop()
            
            # Signal thread to stop
            self.mutex.lock()
            self._running = False
            self._paused = False
            self.condition.wakeAll()
            self.mutex.unlock()
            
            # Release camera resources
            with self.camera_lock:
                if self._cap is not None and self._cap.isOpened():
                    self._cap.release()
                    self._cap = None
            
            # Safe cleanup of detector and recognizer
            if hasattr(self, 'recognizer') and self.recognizer is not None:
                try:
                    # Disconnect any signals
                    self.recognizer.error_signal.disconnect()
                    self.recognizer.result_signal.disconnect()
                    # Stop recognizer threads
                    self.recognizer.stop_all_workers()
                    self.recognizer = None
                except Exception as e:
                    print(f"Error cleaning up recognizer in {self.lane_type} lane: {str(e)}")
            
            self.detector = None
            
            # Wait for thread to finish with timeout
            if self.isRunning():
                print(f"Waiting for {self.lane_type} lane thread to finish...")
                if not self.wait(3000):  # Wait up to 3 seconds
                    print(f"WARNING: {self.lane_type} lane thread did not stop gracefully, forcing termination")
                    self.terminate()
                    self.wait(500)  # Give it 500ms to terminate
                
            print(f"{self.lane_type} lane worker thread stopped")
        except Exception as e:
            print(f"Error stopping {self.lane_type} lane thread: {str(e)}")
            # Try to force termination as a last resort
            if self.isRunning():
                self.terminate()
                self.wait()
