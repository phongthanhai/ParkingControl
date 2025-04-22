from PyQt5.QtCore import QThread, pyqtSignal
import cv2
import numpy as np
import RPi.GPIO as GPIO
from config import (
    CAMERA_SOURCES, CAMERA_RESOLUTION, CAMERA_FPS,
    GPIO_PINS, VIETNAMESE_PLATE_PATTERN
)
from app.models.detection import PlateDetector
from app.controllers.api_client import PlateRecognizer

class LaneWorker(QThread):
    detection_signal = pyqtSignal(str, object, str)  # lane, frame, plate_text
    error_signal = pyqtSignal(str, str)  # lane, error message
    status_signal = pyqtSignal(str, str)  # lane, status

    def __init__(self, lane_type):
        super().__init__()
        self.lane_type = lane_type
        self.detector = PlateDetector()
        self.recognizer = PlateRecognizer()
        self._running = True
        self.active = True
        self.last_frame = None

    def run(self):
        try:
            cap = cv2.VideoCapture(CAMERA_SOURCES[self.lane_type])
            if not cap.isOpened():
                raise RuntimeError("Camera not detected")
            
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

            while self._running and self.active:
                ret, frame = cap.read()
                if not ret:
                    continue

                self.last_frame = frame
                display_frame, plate_img = self.detector.detect(frame)
                
                if plate_img is not None:
                    plate_text = self.recognizer.process(plate_img)
                    valid = VIETNAMESE_PLATE_PATTERN.match(plate_text or "") is not None
                    self.detection_signal.emit(
                        self.lane_type,
                        display_frame,
                        plate_text if valid else "Invalid format"
                    )
                    if valid:
                        self.active = False
                        self.status_signal.emit(self.lane_type, "success")
                        break
                else:
                    self.detection_signal.emit(
                        self.lane_type,
                        display_frame,
                        "Scanning..."
                    )

            cap.release()
        except Exception as e:
            self.error_signal.emit(self.lane_type, str(e))
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self.wait()

    def reset(self):
        self.active = True
        self.start()