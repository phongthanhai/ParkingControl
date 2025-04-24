from PyQt5.QtCore import QThread, pyqtSignal
import cv2
import numpy as np
from config import (
    CAMERA_SOURCES, CAMERA_RESOLUTION, CAMERA_FPS,
    VIETNAMESE_PLATE_PATTERN
)
from app.models.detection import PlateDetector
from app.controllers.api_client import PlateRecognizer

class LaneWorker(QThread):
    detection_signal = pyqtSignal(str, object, str, float, bool)  # lane, frame, text, confidence, valid
    status_signal = pyqtSignal(str, str, dict)  # lane, status, data
    error_signal = pyqtSignal(str, str)  # lane, error

    def __init__(self, lane_type):
        super().__init__()
        self.lane_type = lane_type
        self.detector = PlateDetector()
        self.recognizer = PlateRecognizer()
        self._running = True
        self._paused = False
        self._current_frame = None

    def run(self):
        cap = None
        try:
            if CAMERA_SOURCES.get(self.lane_type) is None:
                raise ValueError(f"No camera for {self.lane_type}")
            
            cap = cv2.VideoCapture(CAMERA_SOURCES[self.lane_type])
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

            while self._running:
                if not self._paused:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    
                    self._process_frame(frame)

        except Exception as e:
            self.error_signal.emit(self.lane_type, str(e))
        finally:
            if cap and cap.isOpened():
                cap.release()

    def _process_frame(self, frame):
        # Detection
        display_frame, plate_img = self.detector.detect(frame)
        
        # OCR processing
        plate_text, confidence = None, 0.0
        if plate_img is not None:
            plate_text, confidence = self.recognizer.process(plate_img)
            is_valid = VIETNAMESE_PLATE_PATTERN.match(plate_text or "") is not None
            
            self.detection_signal.emit(
                self.lane_type,
                display_frame,
                plate_text,
                confidence,
                is_valid
            )
            
            if is_valid and confidence >= 0.7:  
                self._pause_processing()
                self.status_signal.emit(
                    self.lane_type,
                    "success",
                    {"text": plate_text, "confidence": confidence}
                )
            else:
                self.status_signal.emit(
                    self.lane_type,
                    "requires_manual",
                    {"text": plate_text, "confidence": confidence}
                )

    def _pause_processing(self):
        self._paused = True

    def resume_processing(self):
        self._paused = False

    def stop(self):
        self._running = False
        if self.isRunning():
            self.quit()
            self.wait(2000)
