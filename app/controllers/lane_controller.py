from PyQt5.QtCore import QThread, pyqtSignal, QObject
import cv2
import numpy as np
from config import CAMERA_SOURCES, CAMERA_RESOLUTION, CAMERA_FPS
from app.models.detection import PlateDetector
from app.controllers.api_client import PlateRecognizer

class LaneWorker(QThread):
    detection_signal = pyqtSignal(str, object, str)  # lane, frame, plate_text

    def __init__(self, lane_type):
        super().__init__()
        self.lane_type = lane_type
        self.detector = PlateDetector()
        self.recognizer = PlateRecognizer()
        self._running = True

    def run(self):
        cap = cv2.VideoCapture(CAMERA_SOURCES[self.lane_type])
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                continue

            display_frame, plate_img = self.detector.detect(frame)
            plate_text = None
            
            if plate_img is not None:
                plate_text = self.recognizer.process(plate_img)

            self.detection_signal.emit(
                self.lane_type,
                display_frame,
                plate_text if plate_text else "Scanning..."
            )

    def stop(self):
        self._running = False
        self.wait()