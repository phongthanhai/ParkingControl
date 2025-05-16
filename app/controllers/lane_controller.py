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
    detection_signal = pyqtSignal(str, object, str, float, bool)
    status_signal = pyqtSignal(str, str, dict)
    error_signal = pyqtSignal(str, str)
    
    def __init__(self, lane_type):
        super().__init__()
        self.lane_type = lane_type
        self.state = LaneState.IDLE
        
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.camera_lock = threading.Lock()
        
        self.detector = None
        self.recognizer = None
        
        self._running = True
        self._paused = False
        self._camera_index = CAMERA_SOURCES.get(lane_type)
        self.last_api_call = 0
        
        self._error_count = 0
        self._max_errors = 3
        self._last_frame = None
        
        self._cap = None
        
        self.cooldown_active = False
        self.cooldown_timer  = None
        self.frame_buffer_clear_count = 0
        self.required_clear_frames = 10
        
        self.last_detection_data = None
    
    def run(self):
        self._initialize_resources()
        self._main_loop()
    
    def _initialize_resources(self):
        try:
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
            
            init_start_time = time.time()
            init_timeout = 5.0
            
            with self.camera_lock:
                if self._cap is not None and self._cap.isOpened():
                    self._cap.release()
                
                self._cap = cv2.VideoCapture(self._camera_index)
                
                attempts = 0
                max_attempts = 3
                while not self._cap.isOpened() and attempts < max_attempts:
                    if time.time() - init_start_time > init_timeout:
                        raise RuntimeError(f"Camera {self._camera_index} initialization timed out")
                        
                    time.sleep(0.5)
                    attempts += 1
                    self._cap = cv2.VideoCapture(self._camera_index)
                
                if not self._cap.isOpened():
                    raise RuntimeError(f"Camera {self._camera_index} not available after {max_attempts} attempts")
                
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
                self._cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                
                warmup_start = time.time()
                warmup_timeout = 3.0
                
                for _ in range(5):
                    if time.time() - warmup_start > warmup_timeout:
                        break
                        
                    ret, _ = self._cap.read()
                    time.sleep(0.1)
                
                self.state = LaneState.DETECTING
                self._error_count = 0
                
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Camera Initialization Error: {str(e)}")
            self.state = LaneState.ERROR
            
            if self._error_count < self._max_errors:
                self._error_count += 1
                QTimer.singleShot(2000, self._init_camera)
    
    def _main_loop(self):
        while self._running:
            if self._paused:
                self.mutex.lock()
                self.condition.wait(self.mutex)
                self.mutex.unlock()
                continue
                
            if self.state == LaneState.ERROR:
                time.sleep(0.5)
                continue
                
            frame = self._read_frame()
            if frame is None:
                continue
                
            self._process_frame(frame)
                
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
            self._last_frame = frame.copy()
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
                
            display_frame, plate_img = self.detector.detect(frame)
            
            plate_text, confidence = None, 0.0
            api_timeout = False
            
            if plate_img is not None and (time.time() - self.last_api_call) > OCR_RATE_LIMIT:
                try:
                    result = self.recognizer.process(plate_img)
                    if result is not None:
                        plate_text, confidence = result
                        self.last_api_call = time.time()
                    else:
                        api_timeout = True
                except Exception as e:
                    api_timeout = True
                    self.error_signal.emit(self.lane_type, f"API Error: {str(e)}")
            
            plate_text = plate_text if plate_text is not None else "Scanning..."
            confidence = float(confidence) if confidence is not None else 0.0
            
            is_valid = False
            if plate_text and plate_text != "Scanning...":
                is_valid = VIETNAMESE_PLATE_PATTERN.match(plate_text) is not None
            
            self.detection_signal.emit(
                self.lane_type,
                display_frame,
                plate_text,
                confidence,
                is_valid
            )
            
            if plate_img is not None:
                self.last_detection_data = {
                    "text": plate_text if plate_text != "Scanning..." else "",
                    "confidence": confidence,
                    "image": display_frame,
                    "plate_img": plate_img,
                    "is_valid": is_valid
                }
                
                if api_timeout:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "API timeout", "image": display_frame, "text": plate_text if plate_text != "Scanning..." else ""}
                    )
                elif plate_text and plate_text != "Scanning..." and confidence < 0.9:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "low confidence", "text": plate_text, "confidence": confidence, "image": display_frame}
                    )
                elif plate_text and plate_text != "Scanning..." and not is_valid:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "requires_manual",
                        {"reason": "invalid format", "text": plate_text, "confidence": confidence, "image": display_frame}
                    )
                elif is_valid and confidence >= 0.9:
                    self._pause_processing()
                    self.status_signal.emit(
                        self.lane_type,
                        "success",
                        {"text": plate_text, "confidence": confidence, "image": display_frame}
                    )
                
        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Processing Error: {str(e)}")
    
    def _pause_processing(self):
        self.mutex.lock()
        self._paused = True
        self.state = LaneState.PAUSED
        self.mutex.unlock()
    
    def resume_processing(self):
        self.cooldown_active = True
        if self.cooldown_timer is not None and self.cooldown_timer.isActive():
            self.cooldown_timer.stop()
            
        self.cooldown_timer = QTimer()
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self._end_cooldown)
        self.cooldown_timer.start(8000)
        
        self.last_detection_data = None
        
        self.mutex.lock()
        self._paused = False
        self.condition.wakeAll()
        self.mutex.unlock()
    
    def _end_cooldown(self):
        self.cooldown_active = False
        self.frame_buffer_clear_count = 0
        
        self.mutex.lock()
        if self.state != LaneState.ERROR:
            self.state = LaneState.DETECTING
        self.mutex.unlock()
    
    def restart_camera(self):
        if self.state == LaneState.ERROR:
            self._init_camera()
    
    def stop(self):
        self.mutex.lock()
        self._running = False
        self._paused = False
        self.condition.wakeAll()
        self.mutex.unlock()
        
        with self.camera_lock:
            if self._cap is not None and self._cap.isOpened():
                self._cap.release()
                self._cap = None
        
        if self.isRunning():
            self.quit()
            if not self.wait(3000):
                self.terminate()
                self.wait()
