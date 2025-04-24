from PyQt5.QtCore import QThread, pyqtSignal
import cv2
import time
from config import (
    CAMERA_SOURCES, CAMERA_RESOLUTION, CAMERA_FPS,
    VIETNAMESE_PLATE_PATTERN, OCR_RATE_LIMIT
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
        self.last_api_call = 0

    def run(self):
        cap = None
        try:
            if CAMERA_SOURCES.get(self.lane_type) is None:
                raise ValueError(f"No camera configured for {self.lane_type}")
            
            cap = cv2.VideoCapture(CAMERA_SOURCES[self.lane_type])
            if not cap.isOpened():
                raise RuntimeError(f"Camera {CAMERA_SOURCES[self.lane_type]} not available")

            # Camera configuration
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

            # Warm-up period
            for _ in range(10):
                cap.read()
            
            while self._running:
                if self._paused:
                    time.sleep(0.1)
                    continue
                
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue
                
                self._process_frame(frame)

        except Exception as e:
            self.error_signal.emit(self.lane_type, f"Camera Error: {str(e)}")
        finally:
            if cap and cap.isOpened():
                cap.release()
            self.stop()

    def _process_frame(self, frame):
        try:
            # Detection
            display_frame, plate_img = self.detector.detect(frame)
            
            # OCR processing with rate limiting
            plate_text, confidence = None, 0.0
            if plate_img is not None and (time.time() - self.last_api_call) > OCR_RATE_LIMIT:
                plate_text, confidence = self.recognizer.process(plate_img)
                self.last_api_call = time.time()

            # Validation
            is_valid = False
            if plate_text:
                is_valid = VIETNAMESE_PLATE_PATTERN.match(plate_text) is not None

            self.detection_signal.emit(
                self.lane_type,
                display_frame,
                plate_text or "Scanning...",
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
        self._paused = True

    def resume_processing(self):
        self._paused = False
        if not self.isRunning():
            self.start()

    def stop(self):
        self._running = False
        if self.isRunning():
            self.quit()
            self.wait(2000)