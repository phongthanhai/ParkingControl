from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QFrame, QLineEdit, QPushButton, QMessageBox,
                            QTableWidget, QTableWidgetItem, QHeaderView, 
                            QScrollArea, QSizePolicy, QComboBox)
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, Qt, Q_ARG
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
        self.title_label.setStyleSheet("font-weight: bold; font-size: 20px; color: #2c3e50; margin-bottom: 10px;")
        
        # Image display
        self.image_label.setFixedSize(640, 480)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px solid #3498db; background: black; border-radius: 4px;")
        
        # Plate text
        self.plate_label.setAlignment(Qt.AlignCenter)
        self.plate_label.setStyleSheet("""
            font-size: 18px; 
            color: #2c3e50;
            background-color: #ecf0f1;
            padding: 8px;
            border-radius: 4px;
            margin: 10px 0;
        """)
        
        # Status text
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 14px; 
            color: #666;
            min-height: 20px;
            margin-bottom: 5px;
        """)
        
        # Manual input
        self.manual_input.setPlaceholderText("Enter plate manually")
        self.manual_input.setStyleSheet("""
            padding: 8px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
        """)
        self.manual_input.setVisible(False)
        
        self.submit_btn.setStyleSheet("""
            background-color: #2ecc71;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        self.submit_btn.setVisible(False)
        
        # Reconnect button styling
        self.reconnect_btn.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        
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
        self.status_label.setStyleSheet("font-size: 14px; color: #dc3545; font-weight: bold;")
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
        
        # Setup timer for occupancy updates
        self.occupancy_timer = QTimer(self)
        self.occupancy_timer.timeout.connect(self._update_occupancy)
        self.occupancy_timer.start(30000)  # Update occupancy every 30 seconds
        
        # Setup refresh button
        self.add_refresh_button()
        
        # Initial data load
        QTimer.singleShot(1000, self.refresh_data)
        
        # Optional: Setup auto-refresh timer (every 5 minutes)
        self.setup_refresh_timer(300000)    

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
        # Create a scrollable main widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Create lane widgets layout
        lanes_layout = QHBoxLayout()
        lanes_layout.setSpacing(20)
        
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
            lanes_layout.addWidget(entry_widget)
            
        if CAMERA_SOURCES.get('exit') is not None:
            exit_widget = LaneWidget("Exit Lane")
            exit_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('exit')
            )
            exit_widget.reconnect_btn.clicked.connect(
                lambda: self._restart_worker('exit')
            )
            self.lane_widgets['exit'] = exit_widget
            lanes_layout.addWidget(exit_widget)
        
        main_layout.addLayout(lanes_layout)
        
        # Add occupancy indicator
        self.occupancy_frame = QFrame()
        self.occupancy_frame.setFrameShape(QFrame.StyledPanel)
        self.occupancy_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f8f9fa;
                padding: 10px;
            }
        """)
        
        occupancy_layout = QVBoxLayout(self.occupancy_frame)
        
        occupancy_title = QLabel("Parking Occupancy")
        occupancy_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        occupancy_title.setAlignment(Qt.AlignCenter)
        
        self.occupancy_label = QLabel("Loading...")
        self.occupancy_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: white;
            background-color: #3498db;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        """)
        self.occupancy_label.setAlignment(Qt.AlignCenter)
        
        occupancy_layout.addWidget(occupancy_title)
        occupancy_layout.addWidget(self.occupancy_label)
        
        main_layout.addWidget(self.occupancy_frame)
        
        # Add log table
        log_frame = QFrame()
        log_frame.setFrameShape(QFrame.StyledPanel)
        log_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f8f9fa;
                padding: 10px;
            }
        """)
        
        log_layout = QVBoxLayout(log_frame)
        
        log_title = QLabel("Activity Log")
        log_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(5)
        self.log_table.setHorizontalHeaderLabels(["Date", "Time", "Lane", "License Plate", "Type"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.setMinimumHeight(200)
        self.log_table.setMaximumHeight(400)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                gridline-color: #ddd;
                selection-background-color: #3498db;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #3498db;
                color: white;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)
        
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log_table)
        
        main_layout.addWidget(log_frame)
        
        # Set up keyboard shortcut info
        shortcut_frame = QFrame()
        shortcut_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        
        shortcut_layout = QHBoxLayout(shortcut_frame)
        shortcut_label = QLabel("Hotkeys: 1-Open Entry | 2-Close Entry | 3-Open Exit | 4-Close Exit")
        shortcut_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        shortcut_layout.addWidget(shortcut_label)
        
        main_layout.addWidget(shortcut_frame)
        
        # Set the main container as the scroll area widget
        scroll_area.setWidget(main_container)
        
        # Set the scroll area as the main layout for this widget
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)
        
        # Set overall styling
        self.setStyleSheet("""
            QWidget {
                font-family: Arial, sans-serif;
            }
            QPushButton {
                transition: background-color 0.3s;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        # Initialize the occupancy
        self._update_occupancy()
        
        # Initialize the log table
        self._update_log_table()

        # Add these lines at the end of your _setup_ui method

        # Enhance UI components
        self._enhance_occupancy_display()
        self._enhance_log_table()

        # Initialize the log table with sample data
        self.fetch_logs()


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
                widget.status_label.setStyleSheet("font-size: 14px; color: #28a745; font-weight: bold;")
                print(f"GPIO {GPIO_PINS[lane]} activated for {lane} lane")
            elif status == "requires_manual":
                reason = data.get('reason', 'unknown')
                widget.plate_label.setText(f"Manual input required: {reason}")
                
                # Pre-populate with detected text if available
                if 'text' in data:
                    widget.manual_input.setText(data['text'])
                    widget.manual_input.selectAll()  # Select all for easy editing
                
                widget.manual_input.setVisible(True)
                widget.submit_btn.setVisible(True)
                
                if reason == "API timeout":
                    widget.status_label.setText("API timeout - Enter plate manually")
                elif reason == "low confidence":
                    conf = data.get('confidence', 0)
                    widget.status_label.setText(f"Low confidence ({conf:.2f}) - Verify plate")
                elif reason == "invalid format":
                    widget.status_label.setText("Invalid plate format - Enter correct plate")
                else:
                    widget.status_label.setText("Waiting for manual input")
                    
                widget.status_label.setStyleSheet("font-size: 14px; color: #ffc107; font-weight: bold;")
        except Exception as e:
            print(f"Status handling error: {str(e)}")

    def _activate_gate(self, lane):
        try:
            # Activate GPIO
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.HIGH)
                print(f"GPIO {GPIO_PINS[lane]} set HIGH for {lane} lane")
            
            # Set reset timer - cancel existing timer if present
            if lane in self.active_timers and self.active_timers[lane].isActive():
                self.active_timers[lane].stop()
            
            timer = QTimer(self)
            timer.timeout.connect(lambda: self._reset_lane(lane))
            timer.setSingleShot(True)
            timer.start(AUTO_CLOSE_DELAY * 1000)
            self.active_timers[lane] = timer
            print(f"Auto-close timer started for {lane} lane: {AUTO_CLOSE_DELAY} seconds")
        except Exception as e:
            self._show_error(lane, f"Gate Control Error: {str(e)}")

    def _reset_lane(self, lane):
        try:
            # Reset GPIO
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.LOW)
                print(f"GPIO {GPIO_PINS[lane]} set LOW for {lane} lane")
            
            # Reset UI
            widget = self.lane_widgets.get(lane)
            if widget:
                widget.manual_input.clear()
                widget.manual_input.setVisible(False)
                widget.submit_btn.setVisible(False)
                widget.plate_label.setText("Scanning...")
                widget.status_label.setText("")
                print(f"{lane} lane UI reset - resuming detection")
            
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
            widget.status_label.setStyleSheet("font-size: 14px; color: #ffc107; font-weight: bold;")
            return
            
        if VIETNAMESE_PLATE_PATTERN.match(plate_text):
            self._activate_gate(lane)
            self._log_entry(lane, {"text": plate_text}, "manual")
            widget.status_label.setText("Access granted - manual entry")
            widget.status_label.setStyleSheet("font-size: 14px; color: #28a745; font-weight: bold;")
        else:
            widget.status_label.setText("Invalid format - Vietnamese plates only")
            widget.status_label.setStyleSheet("font-size: 14px; color: #dc3545; font-weight: bold;")

    def _log_entry(self, lane, data, entry_type):
        try:
            log_data = {
                "lane": lane,
                "plate": data.get('text', 'N/A'),
                "confidence": data.get('confidence', 0.0),
                "timestamp": time.time(),
                "type": entry_type
            }
            print(f"Log entry created: {log_data}")
            self.log_signal.emit(log_data)
            
            # Add entry to the log table directly as well
            self._add_log_entry(log_data)
        except Exception as e:
            print(f"Logging error: {str(e)}")

    def _add_log_entry(self, data):
        """Add a new entry to the log table"""
        try:
            timestamp = data.get('timestamp', time.time())
            date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
            time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
            
            row_position = self.log_table.rowCount()
            self.log_table.insertRow(row_position)
            
            self.log_table.setItem(row_position, 0, QTableWidgetItem(date_str))
            self.log_table.setItem(row_position, 1, QTableWidgetItem(time_str))
            self.log_table.setItem(row_position, 2, QTableWidgetItem(data.get('lane', 'N/A').title()))
            self.log_table.setItem(row_position, 3, QTableWidgetItem(data.get('plate', 'N/A')))
            self.log_table.setItem(row_position, 4, QTableWidgetItem(data.get('type', 'N/A').title()))
            
            # Auto-scroll to the newest entry
            self.log_table.scrollToBottom()
        except Exception as e:
            print(f"Error adding log entry: {str(e)}")

    def _update_log_table(self):
        """Fetch and display log data from API"""
        # This function would be called when new data is available
        # For now, we'll populate with sample data
        try:
            # Sample data - in production, this would come from your API
            sample_logs = [
                {
                    "timestamp": time.time() - 3600,  # 1 hour ago
                    "lane": "entry",
                    "plate": "30A-12345",
                    "type": "auto"
                },
                {
                    "timestamp": time.time() - 1800,  # 30 minutes ago
                    "lane": "exit",
                    "plate": "59D-67890",
                    "type": "manual"
                }
            ]
            
            # Clear existing entries
            self.log_table.setRowCount(0)
            
            # Add sample entries
            for log in sample_logs:
                self._add_log_entry(log)
                
            print("Log table updated with sample data")
            
        except Exception as e:
            print(f"Error updating log table: {str(e)}")

    # Add these functions to your existing ControlScreen class in the 605-line file

    def _update_occupancy(self):
        """Update the occupancy display with data from API"""
        try:
            # In production, replace this with actual API call
            # For example: response = requests.get("http://your-api/occupancy")
            # occupancy_data = response.json()
            
            # Simulate API response for now
            import random
            occupancy_data = {
                "current": random.randint(30, 95),
                "total": 100,
                "percentage": random.randint(30, 95)
            }
            
            # Update the UI
            percentage = occupancy_data.get('percentage', 0)
            current = occupancy_data.get('current', 0)
            total = occupancy_data.get('total', 100)
            
            # Set color based on occupancy level
            if percentage < 60:
                color = "#27ae60"  # Green
            elif percentage < 85:
                color = "#f1c40f"  # Yellow
            else:
                color = "#e74c3c"  # Red
                
            self.occupancy_label.setText(f"{current}/{total} spaces ({percentage}%)")
            self.occupancy_label.setStyleSheet(f"""
                font-size: 24px;
                font-weight: bold;
                color: white;
                background-color: {color};
                padding: 10px;
                border-radius: 4px;
                margin: 10px 0;
            """)
            
            print(f"Occupancy updated: {percentage}%")
            
        except Exception as e:
            print(f"Error updating occupancy: {str(e)}")
            self.occupancy_label.setText("Occupancy data unavailable")
            self.occupancy_label.setStyleSheet("""
                font-size: 24px;
                font-weight: bold;
                color: white;
                background-color: #7f8c8d;
                padding: 10px;
                border-radius: 4px;
                margin: 10px 0;
            """)

    def fetch_logs(self, start_date=None, end_date=None, limit=50):
        """
        Fetch logs from API with optional date filtering
        
        Args:
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Maximum number of logs to fetch
        """
        try:
            # In production, replace with actual API call
            # Example:
            # params = {'limit': limit}
            # if start_date:
            #     params['start_date'] = start_date
            # if end_date:
            #     params['end_date'] = end_date
            # response = requests.get("http://your-api/logs", params=params)
            # log_data = response.json()
            
            # Simulate API response with sample data
            import time
            import random
            
            # Sample plate numbers
            plates = ["30A-12345", "29B-67890", "51C-98765", "59D-54321", "43E-13579"]
            lane_types = ["entry", "exit"]
            action_types = ["auto", "manual"]
            
            # Generate random logs
            log_data = []
            for i in range(limit):
                timestamp = time.time() - random.randint(0, 86400)  # Random time in last 24 hours
                log_data.append({
                    "timestamp": timestamp,
                    "lane": random.choice(lane_types),
                    "plate": random.choice(plates),
                    "type": random.choice(action_types)
                })
                
            # Sort by timestamp (newest first)
            log_data.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Update the log table
            self._populate_log_table(log_data)
            
            print(f"Fetched {len(log_data)} logs")
            return log_data
            
        except Exception as e:
            print(f"Error fetching logs: {str(e)}")
            return []

    def _populate_log_table(self, log_data):
        """
        Populate the log table with data from API
        
        Args:
            log_data: List of log entries
        """
        try:
            # Clear existing rows
            self.log_table.setRowCount(0)
            
            # Add each log entry to the table
            for log in log_data:
                self._add_log_entry(log)
                
        except Exception as e:
            print(f"Error populating log table: {str(e)}")

    def refresh_data(self):
        """Refresh both occupancy and log data from API"""
        self._update_occupancy()
        self.fetch_logs()
        
        # Show success message temporarily
        status_msg = QLabel("Data refreshed successfully")
        status_msg.setStyleSheet("""
            background-color: #2ecc71;
            color: white;
            padding: 10px;
            border-radius: 4px;
            font-weight: bold;
        """)
        status_msg.setAlignment(Qt.AlignCenter)
        
        # Add to layout temporarily
        main_layout = self.findChild(QVBoxLayout)
        if main_layout:
            main_layout.addWidget(status_msg)
            
            # Remove after 3 seconds
            QTimer.singleShot(3000, lambda: status_msg.deleteLater())

    def setup_refresh_timer(self, interval=60000):
        """Setup automatic refresh timer
        
        Args:
            interval: Refresh interval in milliseconds (default: 60 seconds)
        """
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(interval)
        print(f"Auto-refresh timer started: {interval/1000} seconds")

    def add_refresh_button(self):
        """Add a refresh button to the UI"""
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        
        # Add to layout near occupancy display
        occupancy_layout = self.occupancy_frame.layout()
        if occupancy_layout:
            occupancy_layout.addWidget(refresh_btn)

    def _check_workers_health(self):
        """Periodic check of worker thread health"""
        with self.worker_guard:
            for lane, worker in list(self.lane_workers.items()):
                if not worker.isRunning() or hasattr(worker, 'state') and worker.state == LaneState.ERROR:
                    print(f"Worker for {lane} lane is in bad state, restarting...")
                    self._create_worker(lane)
                    
                    # Update the UI to show reconnection attempt
                    widget = self.lane_widgets.get(lane)
                    if widget:
                        widget.status_label.setText("Reconnecting camera...")
                        widget.status_label.setStyleSheet("font-size: 14px; color: #3498db; font-weight: bold;")


    # Add this code to your _setup_ui method after creating the occupancy_frame

    # Enhanced occupancy display with visual meter
    def _enhance_occupancy_display(self):
        """Create an enhanced occupancy display with visual meter"""
        meter_layout = QHBoxLayout()
        
        # Add percentage indicators
        for percent in [0, 25, 50, 75, 100]:
            label = QLabel(f"{percent}%")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
            meter_layout.addWidget(label)
        
        # Add meter to layout
        occupancy_layout = self.occupancy_frame.layout()
        occupancy_layout.addLayout(meter_layout)
        
        # Add capacity info
        capacity_layout = QHBoxLayout()
        capacity_label = QLabel("Total capacity:")
        capacity_label.setStyleSheet("color: #7f8c8d;")
        
        self.capacity_value = QLabel("100 vehicles")
        self.capacity_value.setStyleSheet("font-weight: bold; color: #2c3e50;")
        
        capacity_layout.addWidget(capacity_label)
        capacity_layout.addWidget(self.capacity_value)
        capacity_layout.addStretch()
        
        last_updated = QLabel("Last updated:")
        last_updated.setStyleSheet("color: #7f8c8d;")
        
        self.update_time = QLabel("Just now")
        self.update_time.setStyleSheet("font-weight: bold; color: #2c3e50;")
        
        capacity_layout.addWidget(last_updated)
        capacity_layout.addWidget(self.update_time)
        
        occupancy_layout.addLayout(capacity_layout)

    # Enhanced log table with filtering
    def _enhance_log_table(self):
        """Add filtering capabilities to log table"""
        filter_layout = QHBoxLayout()
        
        # Date range filter
        date_label = QLabel("Filter by date:")
        date_label.setStyleSheet("color: #7f8c8d;")
        
        self.date_filter = QLineEdit()
        self.date_filter.setPlaceholderText("YYYY-MM-DD")
        self.date_filter.setFixedWidth(120)
        
        # Lane filter
        lane_label = QLabel("Lane:")
        lane_label.setStyleSheet("color: #7f8c8d;")
        
        self.lane_filter = QComboBox()
        self.lane_filter.addItems(["All", "Entry", "Exit"])
        self.lane_filter.setFixedWidth(100)
        
        # Type filter
        type_label = QLabel("Type:")
        type_label.setStyleSheet("color: #7f8c8d;")
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Auto", "Manual"])
        self.type_filter.setFixedWidth(100)
        
        # Apply filter button
        apply_btn = QPushButton("Apply Filters")
        apply_btn.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
        """)
        apply_btn.clicked.connect(self._apply_log_filters)
        
        # Add to layout
        filter_layout.addWidget(date_label)
        filter_layout.addWidget(self.date_filter)
        filter_layout.addWidget(lane_label)
        filter_layout.addWidget(self.lane_filter)
        filter_layout.addWidget(type_label)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addStretch()
        filter_layout.addWidget(apply_btn)
        
        # Add to frame
        log_frame = self.log_table.parent()
        if isinstance(log_frame, QFrame):
            log_layout = log_frame.layout()
            # Insert filter layout after title but before table
            log_layout.insertLayout(1, filter_layout)
        
    def _apply_log_filters(self):
        """Apply filters to log table"""
        date_filter = self.date_filter.text().strip()
        lane_filter = self.lane_filter.currentText().lower()
        type_filter = self.type_filter.currentText().lower()
        
        # Fetch filtered logs
        # In production, send these filters to your API
        # For now, just refresh and simulate filtering
        self.fetch_logs()
        
        # Show applied filters
        filter_msg = "Filters applied: "
        filters = []
        
        if date_filter:
            filters.append(f"Date: {date_filter}")
        if lane_filter != "all":
            filters.append(f"Lane: {lane_filter}")
        if type_filter != "all":
            filters.append(f"Type: {type_filter}")
        
        if filters:
            filter_msg += ", ".join(filters)
            print(filter_msg)
        else:
            print("No filters applied, showing all logs")