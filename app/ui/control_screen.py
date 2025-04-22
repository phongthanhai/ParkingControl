from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QFrame, QLineEdit, QPushButton)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import cv2
import RPi.GPIO as GPIO
import time
from config import CAMERA_SOURCES, GPIO_PINS, AUTO_CLOSE_DELAY, VIETNAMESE_PLATE_PATTERN
from app.controllers.lane_controller import LaneWorker

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
        for lane, pin in GPIO_PINS.items():
            if pin is not None:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Camera Views
        camera_layout = QHBoxLayout()
        self.entry_view = self.create_lane_view("ENTRY LANE")
        
        # Only create exit view if camera exists in config
        if CAMERA_SOURCES.get('exit') is not None:
            camera_layout.addWidget(self.create_separator())
            self.exit_view = self.create_lane_view("EXIT LANE")
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
        self.image_label = QLabel()
        self.image_label.setFixedSize(500, 300)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px solid #95a5a6; background: #ecf0f1;")
        
        # Plate Text
        self.plate_label = QLabel("Scanning...")
        self.plate_label.setAlignment(Qt.AlignCenter)
        self.plate_label.setStyleSheet("font-size: 16px; color: #2c3e50;")
        
        # Manual Input
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Enter plate manually")
        self.manual_input.setVisible(False)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setVisible(False)
        
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(self.manual_input)
        manual_layout.addWidget(self.submit_btn)
        
        layout.addWidget(title_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.plate_label)
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
            if CAMERA_SOURCES.get(lane) is not None:
                try:
                    worker = LaneWorker(lane)
                    worker.detection_signal.connect(self.update_lane_view)
                    worker.error_signal.connect(self.handle_camera_error)
                    worker.status_signal.connect(self.handle_success)
                    worker.start()
                    self.lane_workers[lane] = worker
                except Exception as e:
                    self.show_camera_error(lane, str(e))

    def update_lane_view(self, lane, frame, plate_text):
        try:
            # Convert OpenCV frame to QPixmap
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)

            # Update UI elements
            if lane == 'entry':
                self.entry_view.itemAt(1).widget().setPixmap(pixmap)
                self.entry_view.itemAt(2).widget().setText(plate_text)
                
                if plate_text and "Invalid" in plate_text:
                    self.entry_view.itemAt(3).widget().setVisible(True)
                    self.entry_view.itemAt(4).widget().setVisible(True)
            
            elif lane == 'exit' and CAMERA_SOURCES.get('exit') is not None:
                self.exit_view.itemAt(1).widget().setPixmap(pixmap)
                self.exit_view.itemAt(2).widget().setText(plate_text)

        except Exception as e:
            print(f"UI Update Error: {str(e)}")

    def handle_success(self, lane):
        self.start_countdown(lane)
        self.log_signal.emit({
            'lane': lane,
            'plate': self.lane_workers[lane].last_plate,
            'timestamp': time.time()
        })

    def start_countdown(self, lane):
        if lane in self.timers:
            self.timers[lane].stop()
            
        self.timers[lane] = QTimer(self)
        self.timers[lane].timeout.connect(lambda: self.auto_process(lane))
        self.timers[lane].start(AUTO_CLOSE_DELAY * 1000)

    def auto_process(self, lane):
        try:
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.HIGH)
            self.timers[lane].stop()
            self.lane_workers[lane].reset()
        except Exception as e:
            print(f"GPIO Error: {str(e)}")

    def handle_camera_error(self, lane, error):
        error_pixmap = QPixmap(500, 300)
        error_pixmap.fill(Qt.white)
        
        if lane == 'entry':
            self.entry_view.itemAt(1).widget().setPixmap(error_pixmap)
            self.entry_view.itemAt(2).widget().setText("Camera Error")
        elif lane == 'exit' and CAMERA_SOURCES.get('exit') is not None:
            self.exit_view.itemAt(1).widget().setPixmap(error_pixmap)
            self.exit_view.itemAt(2).widget().setText("Camera Error")
        
        if lane in self.lane_workers:
            del self.lane_workers[lane]

    def closeEvent(self, event):
        for worker in self.lane_workers.values():
            worker.stop()
        GPIO.cleanup()
        super().closeEvent(event)