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
        
        # Processing objects
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
        
        # Store current processing frame for async API callbacks
        self.current_processing_frame = None
        self.current_display_frame = None
        self.current_plate_img = None
    
    def run(self):
        self._initialize_resources()
        self._main_loop()
    
    def _initialize_resources(self):
        try:
            # Initialize processing resources in the worker thread
            self.detector = PlateDetector()
            self.recognizer = PlateRecognizer()
            self.recognizer.error_signal.connect(
                lambda msg: self.error_signal.emit(self.lane_type, f"API Error: {msg}")
            )
            
            # Connect to the result signal to handle asynchronous results
            self.recognizer.result_signal.connect(self._handle_recognition_result)
            
            self._init_camera()
        except Exception as e:
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
                
            # Detection
            display_frame, plate_img = self.detector.detect(frame)
            
            # Store frames for async processing
            self.current_processing_frame = frame
            self.current_display_frame = display_frame
            self.current_plate_img = plate_img
            
            # OCR processing with rate limiting
            api_timeout = False
            
            if plate_img is not None and (time.time() - self.last_api_call) > OCR_RATE_LIMIT:
                try:
                    # Call process which will return None but trigger an async operation
                    # The result will come back via self._handle_recognition_result
                    self.recognizer.process(plate_img)
                    self.last_api_call = time.time()
                    
                    # Show "Scanning..." while waiting for OCR result
                    self.detection_signal.emit(
                        self.lane_type,
                        display_frame,
                        "Scanning...",
                        0.0,
                        False
                    )
                    
                except Exception as e:
                    api_timeout = True
                    self.error_signal.emit(self.lane_type, f"PlateRecognizer API Error: {str(e)}")
            else:
                # If we don't send to OCR, still update the display
                self.detection_signal.emit(
                    self.lane_type,
                    display_frame,
                    "Scanning...",
                    0.0,
                    False
                )
                
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Processing Error: {str(e)}")
            
    def _handle_recognition_result(self, result):
        """Handle the asynchronous result from PlateRecognizer"""
        try:
            plate_text, confidence = result
            
            # Make sure we have the frames we were processing
            if self.current_display_frame is None or self.current_plate_img is None:
                return
                
            display_frame = self.current_display_frame
            plate_img = self.current_plate_img
            
            # Ensure we have valid data types for signal
            plate_text = plate_text if plate_text is not None else "Scanning..."
            confidence = float(confidence) if confidence is not None else 0.0
            
            # Validation
            is_valid = False
            if plate_text and plate_text != "Scanning...":
                is_valid = VIETNAMESE_PLATE_PATTERN.match(plate_text) is not None
            
            # Emit detection signal with safe values
            self.detection_signal.emit(
                self.lane_type,
                display_frame,
                plate_text,
                confidence,
                is_valid
            )
            
            # State management for manual entry cases
            if plate_img is not None:
                # Store the last detection data for potential manual entry
                self.last_detection_data = {
                    "text": plate_text if plate_text != "Scanning..." else "",
                    "confidence": confidence,
                    "image": display_frame,  # Store the display frame with the rectangle drawn
                    "plate_img": plate_img,  # Store the cropped plate image separately
                    "is_valid": is_valid
                }
                
                # Case 1: Not valid text (API timeout or failed recognition)
                if plate_text is None or plate_text == "Scanning...":
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "API timeout", "image": display_frame, "text": ""}
                    )
                # Case 2: Successfully detected plate but confidence too low
                elif plate_text and confidence < 0.9:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "low confidence", "text": plate_text, "confidence": confidence, "image": display_frame}
                    )
                # Case 3: Successfully detected plate but doesn't match regex
                elif plate_text and not is_valid:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "invalid format", "text": plate_text, "confidence": confidence, "image": display_frame}
                    )
                # Case 4: Success case - high confidence valid plate
                elif is_valid and confidence >= 0.9:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "success",
                        {"text": plate_text, "confidence": confidence, "image": display_frame}
                    )
            
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Recognition Result Error: {str(e)}")
    
    def _pause_processing(self):
        self.mutex.lock()
        self._paused = True
        self.state = LaneState.PAUSED
        self.mutex.unlock()
    
    def resume_processing(self):
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
        self.current_plate_img = None
        self.current_display_frame = None
        
        self.mutex.lock()
        self._paused = False
        self.condition.wakeAll()
        self.mutex.unlock()
    
    def _end_cooldown(self):
        self.cooldown_active = False
        self.frame_buffer_clear_count = 0
        
        #resume detection
        self.mutex.lock()
        if self.state != LaneState.ERROR:
            self.state = LaneState.DETECTING
        self.mutex.unlock()
    
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
