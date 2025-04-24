from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QFrame, QLineEdit, QPushButton, QSizePolicy)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import cv2
import RPi.GPIO as GPIO
import time
from config import CAMERA_SOURCES, GPIO_PINS, AUTO_CLOSE_DELAY, VIETNAMESE_PLATE_PATTERN
from app.controllers.lane_controller import LaneWorker

class LaneWidget(QWidget):
    def __init__(self, title):
        super().__init__()
        self.title_label = QLabel(title)
        self.image_label = QLabel()
        self.plate_label = QLabel("Scanning...")
        self.manual_input = QLineEdit()
        self.submit_btn = QPushButton("Submit")
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        
        # Image display
        self.image_label.setFixedSize(640, 480)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px solid #ccc;")
        
        # Plate text
        self.plate_label.setAlignment(Qt.AlignCenter)
        self.plate_label.setStyleSheet("font-size: 16px;")
        
        # Manual input
        self.manual_input.setPlaceholderText("Enter plate manually")
        self.manual_input.setVisible(False)
        self.submit_btn.setVisible(False)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.manual_input)
        input_layout.addWidget(self.submit_btn)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.plate_label)
        layout.addLayout(input_layout)
        
        self.setLayout(layout)

class ControlScreen(QWidget):
    log_signal = pyqtSignal(dict)
    manual_submit_signal = pyqtSignal(str, str)  # lane, plate
    
    def __init__(self):
        super().__init__()
        self.lane_widgets = {}
        self.lane_workers = {}
        self.active_timers = {}
        self._setup_gpio()
        self._setup_ui()
        self._setup_camera_workers()

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        for pin in GPIO_PINS.values():
            if pin is not None:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

    def _setup_ui(self):
        main_layout = QHBoxLayout()
        
        # Create lane widgets only for configured cameras
        if CAMERA_SOURCES.get('entry') is not None:
            entry_widget = LaneWidget("Entry Lane")
            entry_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('entry')
            )
            self.lane_widgets['entry'] = entry_widget
            main_layout.addWidget(entry_widget)
            
        if CAMERA_SOURCES.get('exit') is not None:
            exit_widget = LaneWidget("Exit Lane") 
            exit_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('exit')
            )
            self.lane_widgets['exit'] = exit_widget
            main_layout.addWidget(exit_widget)
        
        self.setLayout(main_layout)

    def _setup_camera_workers(self):
        for lane in ['entry', 'exit']:
            if CAMERA_SOURCES.get(lane) is not None:
                worker = LaneWorker(lane)
                worker.detection_signal.connect(self._handle_detection)
                worker.status_signal.connect(self._handle_worker_status)
                worker.error_signal.connect(self._handle_worker_error)
                worker.start()
                self.lane_workers[lane] = worker

    def _handle_detection(self, lane, frame, plate_text, confidence, is_valid):
        widget = self.lane_widgets[lane]
        
        # Convert frame to QImage
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        q_img = QImage(rgb_image.data, w, h, QImage.Format_RGB888)
        
        # Update UI
        widget.image_label.setPixmap(QPixmap.fromImage(q_img))
        widget.plate_label.setText(plate_text or "Scanning...")
        
        if not is_valid and plate_text:
            widget.manual_input.setVisible(True)
            widget.submit_btn.setVisible(True)

    def _handle_worker_status(self, lane, status, plate_data):
        if status == "success":
            self._trigger_gate_open(lane)
            self.log_signal.emit({
                "lane": lane,
                "plate": plate_data['text'],
                "confidence": plate_data['confidence'],
                "timestamp": time.time(),
                "status": "automatic"
            })
        elif status == "requires_manual":
            self.lane_widgets[lane].plate_label.setText("Requires manual input")

    def _handle_worker_error(self, lane, error):
        widget = self.lane_widgets[lane]
        widget.image_label.setText("Camera Error")
        widget.plate_label.setText(error)
        if lane in self.lane_workers:
            self.lane_workers[lane].stop()
            del self.lane_workers[lane]

    def _trigger_gate_open(self, lane):
        # Open gate
        if GPIO_PINS.get(lane):
            GPIO.output(GPIO_PINS[lane], GPIO.HIGH)
            print(f"[GPIO] Gate for '{lane}' lane opened (GPIO pin {GPIO_PINS[lane]})")
        
        # Set timer to close gate
        timer = QTimer(self)
        timer.timeout.connect(lambda: self._reset_lane(lane))
        timer.start(AUTO_CLOSE_DELAY * 1000)
        self.active_timers[lane] = timer

    def _reset_lane(self, lane):
        # Close gate
        if GPIO_PINS.get(lane):
            GPIO.output(GPIO_PINS[lane], GPIO.LOW)
            print(f"[GPIO] Gate for '{lane}' lane closed (GPIO pin {GPIO_PINS[lane]})")

        
        # Reset UI
        widget = self.lane_widgets[lane]
        widget.manual_input.setVisible(False)
        widget.submit_btn.setVisible(False)
        widget.plate_label.setText("Scanning...")
        
        # Restart processing
        if lane in self.lane_workers:
            self.lane_workers[lane].resume_processing()

    def _handle_manual_submit(self, lane):
        widget = self.lane_widgets[lane]
        plate_text = widget.manual_input.text()
        
        if VIETNAMESE_PLATE_PATTERN.match(plate_text):
            self.manual_submit_signal.emit(lane, plate_text)
            self._trigger_gate_open(lane)
            self.log_signal.emit({
                "lane": lane,
                "plate": plate_text,
                "confidence": None,
                "timestamp": time.time(),
                "status": "manual"
            })
        else:
            widget.plate_label.setText("Invalid plate format")

    def closeEvent(self, event):
        for worker in self.lane_workers.values():
            worker.stop()
        GPIO.cleanup()
        super().closeEvent(event)