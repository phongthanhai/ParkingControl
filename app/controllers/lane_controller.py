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
            
            self._init_camera()
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Initialization Error: {str(e)}")
            self.state = LaneState.ERROR
    
    def _init_camera(self):
        try:
            if self._camera_index is None:
                raise ValueError(f"No camera configured for {self.lane_type}")
            
            with self.camera_lock:
                if self._cap is not None and self._cap.isOpened():
                    self._cap.release()
                
                self._cap = cv2.VideoCapture(self._camera_index)
                
                if not self._cap.isOpened():
                    raise RuntimeError(f"Camera {self._camera_index} not available")
                
                # Camera configuration
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
                self._cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                
                # Warm-up period - read a few frames to stabilize
                for _ in range(5):
                    self._cap.read()
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
            # Detection
            display_frame, plate_img = self.detector.detect(frame)
            
            # OCR processing with rate limiting
            plate_text, confidence = None, 0.0
            if plate_img is not None and (time.time() - self.last_api_call) > OCR_RATE_LIMIT:
                result = self.recognizer.process(plate_img)
                if result is not None:
                    plate_text, confidence = result
                    self.last_api_call = time.time()
            
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
            
            # State management
            if is_valid and confidence >= 0.7:
                self._pause_processing()
                self.status_signal.emit(
                    self.lane_type,
                    "success",
                    {"text": plate_text, "confidence": confidence}
                )
                
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Processing Error: {str(e)}")
    
    def _pause_processing(self):
        self.mutex.lock()
        self._paused = True
        self.state = LaneState.PAUSED
        self.mutex.unlock()
    
    def resume_processing(self):
        self.mutex.lock()
        self._paused = False
        if self.state != LaneState.ERROR:
            self.state = LaneState.DETECTING
        self.condition.wakeAll()
        self.mutex.unlock()
    
    def restart_camera(self):
        """Attempt to restart the camera after an error"""
        if self.state == LaneState.ERROR:
            self._init_camera()
    
    def stop(self):
        """Clean shutdown of the worker thread"""
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
        
        # Wait for thread to finish
        if self.isRunning():
            self.quit()
            if not self.wait(3000):  # Wait up to 3 seconds
                self.terminate()
                self.wait()