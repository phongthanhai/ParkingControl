from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QFrame, QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, Qt, Q_ARG
import cv2
import RPi.GPIO as GPIO
import time
import threading
from config import CAMERA_SOURCES, GPIO_PINS, AUTO_CLOSE_DELAY, VIETNAMESE_PLATE_PATTERN
from app.controllers.lane_controller import LaneWorker, LaneState

class LaneWidget(QWidget):
    def __init__(self, title):
        super().__init__()
        # Initialize all UI elements
        self.title_label = QLabel(title)
        self.image_label = QLabel()
        self.plate_label = QLabel("Initializing...")
        self.status_label = QLabel("")
        self.manual_input = QLineEdit()
        self.submit_btn = QPushButton("Submit")
        self.reconnect_btn = QPushButton("Reconnect Camera")
        self.reconnect_btn.setVisible(False)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        # Title
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 18px; color: #2c3e50;")
        
        # Image display
        self.image_label.setFixedSize(640, 480)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px solid #ccc; background: black;")
        
        # Plate text
        self.plate_label.setAlignment(Qt.AlignCenter)
        self.plate_label.setStyleSheet("font-size: 16px; color: #2c3e50;")
        
        # Status text
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #666;")
        
        # Manual input
        self.manual_input.setPlaceholderText("Enter plate manually")
        self.manual_input.setVisible(False)
        self.submit_btn.setVisible(False)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.manual_input)
        input_layout.addWidget(self.submit_btn)
        
        # Control layout
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.reconnect_btn)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label)
        layout.addWidget(self.plate_label)
        layout.addWidget(self.status_label)
        layout.addLayout(input_layout)
        layout.addLayout(control_layout)
        
        self.setLayout(layout)
    
    def show_error(self, message):
        """Display error message in the widget"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("font-size: 14px; color: #dc3545;")
        self.reconnect_btn.setVisible(True)
        
    def reset_status(self):
        """Reset status display"""
        self.status_label.setText("")
        self.status_label.setStyleSheet("font-size: 14px; color: #666;")
        self.reconnect_btn.setVisible(False)

class ControlScreen(QWidget):
    log_signal = pyqtSignal(dict)
    manual_submit_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.lane_widgets = {}
        self.lane_workers = {}
        self.active_timers = {}
        self.worker_guard = threading.Lock()  # Protects worker creation/deletion
        
        self._setup_gpio()
        self._setup_ui()
        
        # Delayed initialization of camera workers for stability
        QTimer.singleShot(500, self._setup_camera_workers)
        
        # Setup watchdog timer for worker health check
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self._check_workers_health)
        self.watchdog_timer.start(10000)  # Check every 10 seconds

    def _setup_gpio(self):
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            for pin in GPIO_PINS.values():
                if pin is not None:
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
        except Exception as e:
            QMessageBox.warning(self, "GPIO Warning", f"Failed to initialize GPIO: {str(e)}")

    def _setup_ui(self):
        main_layout = QHBoxLayout()
        
        # Create lane widgets only for configured cameras
        if CAMERA_SOURCES.get('entry') is not None:
            entry_widget = LaneWidget("Entry Lane")
            entry_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('entry')
            )
            entry_widget.reconnect_btn.clicked.connect(
                lambda: self._restart_worker('entry')
            )
            self.lane_widgets['entry'] = entry_widget
            main_layout.addWidget(entry_widget)
            
        if CAMERA_SOURCES.get('exit') is not None:
            exit_widget = LaneWidget("Exit Lane")
            exit_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('exit')
            )
            exit_widget.reconnect_btn.clicked.connect(
                lambda: self._restart_worker('exit')
            )
            self.lane_widgets['exit'] = exit_widget
            main_layout.addWidget(exit_widget)
        
        self.setLayout(main_layout)

    def _setup_camera_workers(self):
        with self.worker_guard:
            for lane in ['entry', 'exit']:
                if CAMERA_SOURCES.get(lane) is not None:
                    self._create_worker(lane)

    def _create_worker(self, lane):
        """Create and start a worker for the specified lane"""
        try:
            widget = self.lane_widgets.get(lane)
            if widget:
                widget.plate_label.setText("Initializing camera...")
            
            # Stop any existing worker
            if lane in self.lane_workers:
                self.lane_workers[lane].stop()
                del self.lane_workers[lane]
            
            # Create and configure new worker
            worker = LaneWorker(lane)
            
            # Connect signals using safe direct connection type
            worker.detection_signal.connect(
                self._handle_detection, 
                type=Qt.QueuedConnection
            )
            worker.status_signal.connect(
                self._handle_status,
                type=Qt.QueuedConnection  
            )
            worker.error_signal.connect(
                self._handle_error,
                type=Qt.QueuedConnection
            )
            
            # Start worker and store reference
            worker.start()
            self.lane_workers[lane] = worker
            
            if widget:
                widget.reset_status()
                
        except Exception as e:
            self._show_error(lane, f"Worker Creation Error: {str(e)}")

    def _handle_detection(self, lane, frame, text, confidence, valid):
        widget = self.lane_widgets.get(lane)
        if not widget:
            return

        try:
            # Safety check for frame
            if frame is None or frame.size == 0:
                return
                
            # Convert frame to QImage
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Update UI
            pixmap = QPixmap.fromImage(q_img)
            if not pixmap.isNull():
                widget.image_label.setPixmap(pixmap)
            
            # Update text with confidence if available
            display_text = text
            if confidence > 0:
                display_text = f"{text} ({confidence:.2f})"
            widget.plate_label.setText(display_text)
            
            # Show manual input if needed
            if text.startswith("Invalid"):
                widget.manual_input.setVisible(True)
                widget.submit_btn.setVisible(True)
                
        except Exception as e:
            self._show_error(lane, f"UI Update Error: {str(e)}")

    def _handle_status(self, lane, status, data):
        widget = self.lane_widgets.get(lane)
        if not widget:
            return
            
        try:
            if status == "success":
                self._activate_gate(lane)
                self._log_entry(lane, data, "auto")
                widget.status_label.setText("Access granted - automatic")
                widget.status_label.setStyleSheet("font-size: 14px; color: #28a745;")
            elif status == "requires_manual":
                widget.plate_label.setText("Manual input required")
                widget.manual_input.setVisible(True)
                widget.submit_btn.setVisible(True)
                widget.status_label.setText("Waiting for manual input")
                widget.status_label.setStyleSheet("font-size: 14px; color: #ffc107;")
        except Exception as e:
            print(f"Status handling error: {str(e)}")

    def _activate_gate(self, lane):
        try:
            # Activate GPIO
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.HIGH)
            
            # Set reset timer - cancel existing timer if present
            if lane in self.active_timers and self.active_timers[lane].isActive():
                self.active_timers[lane].stop()
            
            timer = QTimer(self)
            timer.timeout.connect(lambda: self._reset_lane(lane))
            timer.setSingleShot(True)
            timer.start(AUTO_CLOSE_DELAY * 1000)
            self.active_timers[lane] = timer
        except Exception as e:
            self._show_error(lane, f"Gate Control Error: {str(e)}")

    def _reset_lane(self, lane):
        try:
            # Reset GPIO
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.LOW)
            
            # Reset UI
            widget = self.lane_widgets.get(lane)
            if widget:
                widget.manual_input.clear()
                widget.manual_input.setVisible(False)
                widget.submit_btn.setVisible(False)
                widget.plate_label.setText("Scanning...")
                widget.status_label.setText("")
            
            # Resume processing safely
            with self.worker_guard:
                if lane in self.lane_workers and self.lane_workers[lane].isRunning():
                    self.lane_workers[lane].resume_processing()
        except Exception as e:
            self._show_error(lane, f"Reset Error: {str(e)}")

    def _handle_error(self, lane, error):
        self._show_error(lane, error)
        
        # Schedule a restart attempt
        QTimer.singleShot(5000, lambda: self._restart_worker(lane))

    def _show_error(self, lane, message):
        widget = self.lane_widgets.get(lane)
        if widget:
            widget.show_error(message)
        print(f"Error in {lane} lane: {message}")

    def _restart_worker(self, lane):
        """Safely restart a worker thread"""
        with self.worker_guard:
            if lane in self.lane_workers:
                worker = self.lane_workers[lane]
                # If in error state, try to restart camera
                if hasattr(worker, 'state') and worker.state == LaneState.ERROR:
                    # Try to restart in current thread first
                    worker.restart_camera()
                else:
                    # Otherwise create a new worker
                    self._create_worker(lane)

    def _handle_manual_submit(self, lane):
        widget = self.lane_widgets.get(lane)
        if not widget:
            return
            
        plate_text = widget.manual_input.text().strip()
        if not plate_text:
            widget.status_label.setText("Please enter a license plate number")
            widget.status_label.setStyleSheet("font-size: 14px; color: #ffc107;")
            return
            
        if VIETNAMESE_PLATE_PATTERN.match(plate_text):
            self._activate_gate(lane)
            self._log_entry(lane, {"text": plate_text}, "manual")
            widget.status_label.setText("Access granted - manual entry")
            widget.status_label.setStyleSheet("font-size: 14px; color: #28a745;")
        else:
            widget.status_label.setText("Invalid format - Vietnamese plates only")
            widget.status_label.setStyleSheet("font-size: 14px; color: #dc3545;")

    def _log_entry(self, lane, data, entry_type):
        try:
            self.log_signal.emit({
                "lane": lane,
                "plate": data.get('text', 'N/A'),
                "confidence": data.get('confidence', 0.0),
                "timestamp": time.time(),
                "type": entry_type
            })
        except Exception as e:
            print(f"Logging error: {str(e)}")

    def _check_workers_health(self):
        """Check if workers are in error state and restart if needed"""
        with self.worker_guard:
            for lane, worker in list(self.lane_workers.items()):
                if not worker.isRunning():
                    print(f"Worker for {lane} is not running, restarting...")
                    self._create_worker(lane)
                elif hasattr(worker, 'state') and worker.state == LaneState.ERROR:
                    print(f"Worker for {lane} is in error state, restarting...")
                    self._create_worker(lane)

    def closeEvent(self, event):
        # Stop watchdog timer
        if self.watchdog_timer.isActive():
            self.watchdog_timer.stop()
        
        # Safely stop all workers
        with self.worker_guard:
            for worker in list(self.lane_workers.values()):
                try:
                    worker.stop()
                except Exception:
                    pass
            self.lane_workers.clear()
        
        # Clean up GPIO
        try:
            GPIO.cleanup()
        except Exception:
            pass
            
        super().closeEvent(event)