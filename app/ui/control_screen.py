from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QFrame, QLineEdit, QPushButton)
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import cv2
import RPi.GPIO as GPIO
import requests
import json
import time
from app.controllers.lane_controller import LaneWorker
from config import AUTO_CLOSE_DELAY

class ControlScreen(QWidget):
    log_signal = pyqtSignal(dict)
    manual_input_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.lane_workers = {}
        self.timers = {}
        self.manual_inputs = {}
        self.setup_gpio()
        self.setup_ui()
        self.setup_cameras()

    def setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        for pin in GPIO_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Camera Views
        camera_layout = QHBoxLayout()
        self.entry_view = self.create_lane_view("ENTRY LANE")
        self.exit_view = self.create_lane_view("EXIT LANE")
        
        camera_layout.addLayout(self.entry_view)
        camera_layout.addWidget(self.create_separator())
        camera_layout.addLayout(self.exit_view)
        main_layout.addLayout(camera_layout)
        
        self.setLayout(main_layout)

    def create_lane_view(self, title):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 18px; color: #2c3e50;")
        
        # Image Display
        image_label = QLabel()
        image_label.setFixedSize(500, 300)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("border: 2px solid #95a5a6; background: #ecf0f1;")
        
        # Plate Text
        plate_label = QLabel("Scanning...")
        plate_label.setAlignment(Qt.AlignCenter)
        plate_label.setStyleSheet("font-size: 16px; color: #2c3e50;")
        
        # Manual Input
        manual_layout = QHBoxLayout()
        manual_input = QLineEdit()
        manual_input.setPlaceholderText("Enter plate manually")
        manual_input.setVisible(False)
        submit_btn = QPushButton("Submit")
        submit_btn.setVisible(False)
        
        manual_layout.addWidget(manual_input)
        manual_layout.addWidget(submit_btn)
        
        layout.addWidget(title_label)
        layout.addWidget(image_label)
        layout.addWidget(plate_label)
        layout.addLayout(manual_layout)
        
        return layout

    def create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background: #ced4da;")
        separator.setFixedHeight(300)
        return separator

    def setup_cameras(self):
        for lane in ['entry', 'exit']:
            try:
                worker = LaneWorker(lane)
                worker.detection_signal.connect(self.update_lane_view)
                worker.error_signal.connect(self.handle_camera_error)
                worker.status_signal.connect(self.handle_success)
                worker.start()
                self.lane_workers[lane] = worker
            except:
                self.show_camera_error(lane)

    def update_lane_view(self, lane, frame, plate_text):
        q_img = QImage(frame.data, frame.shape[1], frame.shape[0], 
                      QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_img)
        
        view = self.entry_view if lane == 'entry' else self.exit_view
        view.itemAt(1).widget().setPixmap(pixmap)
        view.itemAt(2).widget().setText(plate_text)

        if "Invalid" in plate_text:
            self.show_manual_input(lane)

    def handle_success(self, lane):
        self.start_countdown(lane)
        self.log_signal.emit({
            'lane': lane,
            'plate': self.lane_workers[lane].last_plate,
            'timestamp': time.time()
        })

    def start_countdown(self, lane):
        self.timers[lane] = QTimer(self)
        self.timers[lane].timeout.connect(lambda: self.auto_process(lane))
        self.timers[lane].start(AUTO_CLOSE_DELAY * 1000)

    def auto_process(self, lane):
        GPIO.output(GPIO_PINS[lane], GPIO.HIGH)
        self.timers[lane].stop()
        self.lane_workers[lane].reset()

    def show_manual_input(self, lane):
        view = self.entry_view if lane == 'entry' else self.exit_view
        view.itemAt(3).widget().setVisible(True)
        view.itemAt(4).widget().setVisible(True)

    def handle_camera_error(self, lane, error):
        pixmap = QPixmap(500, 300)
        pixmap.fill(Qt.white)
        view = self.entry_view if lane == 'entry' else self.exit_view
        view.itemAt(1).widget().setPixmap(pixmap)
        view.itemAt(2).widget().setText("Camera Error")
        if lane in self.lane_workers:
            del self.lane_workers[lane]

    def closeEvent(self, event):
        for worker in self.lane_workers.values():
            worker.stop()
        GPIO.cleanup()
        super().closeEvent(event)