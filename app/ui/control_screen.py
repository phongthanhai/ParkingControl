from PyQt5.QtGui import QPixmap, QImage, QFont, QColor, QPalette
from PyQt5.QtWidgets import QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QScrollArea, QSpacerItem, QWidget, QComboBox, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, Q_ARG, QPropertyAnimation, QEasingCurve, QRect, QThread, QElapsedTimer
import RPi.GPIO as GPIO
import time
import threading
from config import CAMERA_SOURCES, GPIO_PINS, AUTO_CLOSE_DELAY, VIETNAMESE_PLATE_PATTERN, API_BASE_URL, LOT_ID
from app.controllers.lane_controller import LaneWorker, LaneState
import cv2
from app.controllers.api_client import ApiClient
from PyQt5.QtWidgets import QApplication
from datetime import datetime
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage
from app.controllers.sync_service import SyncService, SyncStatus
from app.ui.sync_status_widget import SyncStatusWidget
from app.utils.auth_manager import AuthManager
import numpy as np
from app.controllers.db_worker import DBWorker, DBOperationType

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
        self.skip_btn = QPushButton("Skip")
        self.reconnect_btn = QPushButton("Reconnect Camera")
        
        # Make manual input fields always present but hidden initially
        self.manual_input.setVisible(False)
        self.submit_btn.setVisible(False)
        self.skip_btn.setVisible(False)
        self.reconnect_btn.setVisible(False)
        
        # Apply fixed size policies to maintain consistency
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(640)  # Ensure minimum width for proper layout
        
        self._setup_ui()

    def _setup_ui(self):
        # Main container layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title with consistent height
        title_container = QFrame()
        title_container.setFixedHeight(40)
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 20px; color: #2c3e50;")
        title_layout.addWidget(self.title_label)
        
        main_layout.addWidget(title_container)
        
        # Center-aligned container for image
        image_container = QFrame()
        image_container.setFixedHeight(490)  # Height for image + margin
        image_layout = QHBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image display with fixed size
        self.image_label.setFixedSize(640, 480)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px solid #3498db; background: black; border-radius: 4px;")
        image_layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        
        main_layout.addWidget(image_container)
        
        # Fixed height container for plate and status
        info_container = QFrame()
        info_container.setFixedHeight(80)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Plate text
        self.plate_label.setAlignment(Qt.AlignCenter)
        self.plate_label.setStyleSheet("""
            font-size: 18px; 
            color: #2c3e50;
            background-color: #ecf0f1;
            padding: 8px;
            border-radius: 4px;
        """)
        
        # Status text
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 14px; 
            color: #666;
            min-height: 20px;
        """)
        
        info_layout.addWidget(self.plate_label)
        info_layout.addWidget(self.status_label)
        
        main_layout.addWidget(info_container)
        
        # Input container - Fixed height regardless of visibility
        input_container = QFrame()
        input_container.setFixedHeight(50)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        # Manual input styling
        self.manual_input.setPlaceholderText("Enter plate manually")
        self.manual_input.setStyleSheet("""
            padding: 8px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
        """)
        
        # Create a fixed height for the button to prevent it from changing the layout
        self.manual_input.setFixedHeight(40)
        
        self.submit_btn.setStyleSheet("""
            background-color: #2ecc71;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        self.submit_btn.setFixedHeight(40)
        self.submit_btn.setFixedWidth(120)  # Fixed width for button
        
        # Skip button styling
        self.skip_btn.setStyleSheet("""
            background-color: #f39c12;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        self.skip_btn.setFixedHeight(40)
        self.skip_btn.setFixedWidth(120)  # Fixed width for button
        
        input_layout.addWidget(self.manual_input, 1)  # Give most space to input
        input_layout.addWidget(self.submit_btn, 0)  # Fixed space for button
        input_layout.addWidget(self.skip_btn, 0)  # Fixed space for skip button
        
        main_layout.addWidget(input_container)
        
        # Control container with fixed height
        control_container = QFrame()
        control_container.setFixedHeight(50)
        control_layout = QHBoxLayout(control_container)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        self.reconnect_btn.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        
        control_layout.addWidget(self.reconnect_btn, 0, Qt.AlignCenter)
        
        main_layout.addWidget(control_container)
        
        # Instead of modifying the visibility, we'll keep all elements in the layout
        # but show/hide them as needed. This prevents layout shifts.
    
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
        self.lanes_in_manual_mode = {}  # Track which lanes are in manual input mode
        self.worker_guard = threading.Lock()  # Protects worker creation/deletion
        
        # Initialize UI responsiveness monitor
        self.ui_monitor_timer = QTimer(self)
        self.ui_monitor_timer.timeout.connect(self._check_ui_responsiveness)
        self.ui_monitor_timer.start(1000)  # Check every second
        self.last_ui_check = QElapsedTimer()
        self.last_ui_check.start()
        self.ui_blocked_threshold = 500  # ms
        
        # Initialize database worker for async operations
        self.db_worker = DBWorker()
        self.db_worker.operation_complete.connect(self._handle_db_operation_complete)
        self.pending_db_operations = {}  # Track pending operations
        
        # Initialize API client
        self.api_client = ApiClient(base_url=API_BASE_URL)
        
        # API connectivity status
        self.api_available = True
        self.api_retry_count = 0
        self.max_api_retries = 5  # Increased from 3 to 5 to be more tolerant
        
        # Connectivity tracking
        self.consecutive_failures = 0
        self.last_successful_connection = time.time()
        
        # Debug flags
        self.debug_blacklist = False  # Set to True to enable extensive blacklist logging
        
        self.local_blacklist_logs = []
        
        # Connect log_signal for sync service
        # This signal will be captured by SyncService to handle log synchronization
        print("Setting up log_signal for sync service")
        
        self._setup_gpio()
        self._setup_ui()
        
        # Delayed initialization of camera workers for stability
        QTimer.singleShot(500, self._setup_camera_workers)
        
        # Setup watchdog timer for worker health check
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self._check_workers_health)
        self.watchdog_timer.start(30000)  # Check every 30 seconds (increased from 10 to give more time for manual input)
        
        # Setup timer for occupancy updates
        self.occupancy_timer = QTimer(self)
        self.occupancy_timer.timeout.connect(self._update_occupancy)
        self.occupancy_timer.start(60000)  # Update occupancy every 60 seconds
        
        # Setup dedicated API status check timer - less frequent checks
        self.api_check_timer = QTimer(self)
        self.api_check_timer.timeout.connect(self._check_api_connection)
        self.api_check_timer.start(15000)  # Check API status every 15 seconds (increased from 5 seconds)
        
        # Setup refresh button
        self.add_refresh_button()
        
        # Initial data load
        QTimer.singleShot(1000, self.refresh_data)

    def _setup_gpio(self):
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            for pin in GPIO_PINS.values():
                if pin is not None:
                    GPIO.setup(pin, GPIO.OUT)
                    # Set pins HIGH by default for relay modules (inactive state)
                    GPIO.output(pin, GPIO.HIGH)
                    print(f"GPIO pin {pin} initialized to HIGH (relay inactive)")
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
        
        # API Status indicator at the top
        api_status_layout = QHBoxLayout()
        api_status_label = QLabel("API Status:")
        self.api_status_label = QLabel("API: Connected")
        self.api_status_indicator = QWidget()
        self.api_status_indicator.setFixedSize(15, 15)
        self.api_status_indicator.setStyleSheet("background-color: green; border-radius: 7px;")
        
        # Add reconnect button (initially hidden)
        self.api_reconnect_button = QPushButton("Reconnect")
        self.api_reconnect_button.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        self.api_reconnect_button.clicked.connect(self._reconnect_api)
        self.api_reconnect_button.setVisible(False)
        
        # Add sync status widget next to API status
        self.sync_status_widget = SyncStatusWidget()
        
        api_status_layout.addWidget(api_status_label)
        api_status_layout.addWidget(self.api_status_indicator)
        api_status_layout.addWidget(self.api_status_label)
        api_status_layout.addWidget(self.api_reconnect_button)
        api_status_layout.addWidget(self.sync_status_widget)
        api_status_layout.addStretch()
        
        main_layout.addLayout(api_status_layout)
        
        # Create lane widgets layout with equal spacing
        lanes_layout = QHBoxLayout()
        lanes_layout.setSpacing(20)
        lanes_layout.setContentsMargins(10, 10, 10, 10)  # Even padding around lanes
        
        # Create a container for both lanes to ensure equal sizing
        lanes_container = QFrame()
        lanes_container.setStyleSheet("background: transparent;")
        lanes_container.setLayout(lanes_layout)
        
        # Create lane widgets only for configured cameras
        if CAMERA_SOURCES.get('entry') is not None:
            entry_widget = LaneWidget("Entry Lane")
            entry_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('entry')
            )
            entry_widget.skip_btn.clicked.connect(
                lambda: self._handle_manual_skip('entry')
            )
            entry_widget.reconnect_btn.clicked.connect(
                lambda: self._restart_worker('entry')
            )
            self.lane_widgets['entry'] = entry_widget
            lanes_layout.addWidget(entry_widget, 1)  # Equal stretch factor
            
        if CAMERA_SOURCES.get('exit') is not None:
            exit_widget = LaneWidget("Exit Lane")
            exit_widget.submit_btn.clicked.connect(
                lambda: self._handle_manual_submit('exit')
            )
            exit_widget.skip_btn.clicked.connect(
                lambda: self._handle_manual_skip('exit')
            )
            exit_widget.reconnect_btn.clicked.connect(
                lambda: self._restart_worker('exit')
            )
            self.lane_widgets['exit'] = exit_widget
            lanes_layout.addWidget(exit_widget, 1)  # Equal stretch factor
        
        # Add the lane container to the main layout
        main_layout.addWidget(lanes_container)
        
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
        
        # Initialize lot name label
        self.lot_name_label = QLabel("Loading lot information...")
        self.lot_name_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #34495e;
            margin-bottom: 5px;
        """)
        self.lot_name_label.setAlignment(Qt.AlignCenter)
        
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
        
        # Initialize capacity value and update time labels
        self.capacity_value = QLabel("Loading...")
        self.capacity_value.setStyleSheet("font-weight: bold; color: #2c3e50;")
        
        self.update_time = QLabel("--:--:--")
        self.update_time.setStyleSheet("font-weight: bold; color: #2c3e50;")
        
        # Add widgets to layout in proper order
        occupancy_layout.addWidget(occupancy_title)
        occupancy_layout.addWidget(self.lot_name_label)
        occupancy_layout.addWidget(self.occupancy_label)
        
        main_layout.addWidget(self.occupancy_frame)
        
        # Add log area
        log_frame = QFrame()
        log_frame.setFrameShape(QFrame.StyledPanel)
        log_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f8f9fa;
                padding: 0px;
            }
        """)
        
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(0, 10, 0, 0)  # Remove horizontal padding
        log_layout.setSpacing(0)  # Remove spacing between elements
        
        log_title = QLabel("Activity Log")
        log_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 0 10px;")
        log_title.setContentsMargins(10, 0, 0, 5)  # Add left padding to the title
        
        # Create a scrollable area for log entries
        log_scroll = QScrollArea()
        log_scroll.setWidgetResizable(True)
        log_scroll.setFrameShape(QFrame.NoFrame)
        log_scroll.setMinimumHeight(300)
        log_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        log_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Prevent horizontal scrolling
        
        log_widget = QWidget()
        self.logs_layout = QVBoxLayout(log_widget)
        self.logs_layout.setAlignment(Qt.AlignTop)
        self.logs_layout.setSpacing(0)  # No spacing between rows
        self.logs_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        
        log_scroll.setWidget(log_widget)
        
        # Add header row
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)  # Remove container margins
        header_layout.setSpacing(1)  # Minimal spacing between columns
        
        date_header = QLabel("Date/Time")
        lane_header = QLabel("Lane")
        plate_header = QLabel("License Plate")
        type_header = QLabel("Type")
        
        # Style headers with less padding and no rounded corners
        header_style = """
            QLabel {
                font-weight: bold; 
                color: white; 
                background-color: #3498db; 
                padding: 8px;
                border: none;
            }
        """
        
        date_header.setStyleSheet(header_style)
        lane_header.setStyleSheet(header_style)
        plate_header.setStyleSheet(header_style)
        type_header.setStyleSheet(header_style)
        
        # Remove the general header widget style that was adding padding
        header_widget.setStyleSheet("")
        
        # Add headers to layout
        header_layout.addWidget(date_header, 3)  # 30% of space
        header_layout.addWidget(lane_header, 1)  # 10% of space
        header_layout.addWidget(plate_header, 2)  # 20% of space
        header_layout.addWidget(type_header, 1)  # 10% of space
        
        # Use stretch factors instead of fixed width for more flexible sizing
        # This will scale better with window resizing
        
        log_layout.addWidget(log_title)
        log_layout.addWidget(header_widget)
        log_layout.addWidget(log_scroll)
        
        main_layout.addWidget(log_frame)
        
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
        self._clear_log_table()

        # Enhanced UI components
        self._enhance_occupancy_display()
        self._enhance_log_table()

        # Add blacklist cache
        self.blacklisted_plates = set()
        self.last_blacklist_update = 0
        self.blacklist_update_interval = 300  # Update every 5 minutes
        
        # Setup timer for blacklist updates
        self.blacklist_timer = QTimer(self)
        self.blacklist_timer.timeout.connect(self._update_blacklist_cache)
        self.blacklist_timer.start(self.blacklist_update_interval * 1000)
        
        # Initial blacklist load
        QTimer.singleShot(1000, self._update_blacklist_cache)

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
            
            # Get the display dimensions
            display_width = 640
            display_height = 480
            
            # Resize the image to exactly match the display dimensions, even if it changes aspect ratio
            rgb_image = cv2.resize(rgb_image, (display_width, display_height), interpolation=cv2.INTER_AREA)
            
            # Get the dimensions of the final image
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            
            # Create QImage and QPixmap
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            
            # Update UI
            if not pixmap.isNull():
                widget.image_label.setPixmap(pixmap)
            
            # Update text with confidence if available
            display_text = text
            if confidence > 0:
                display_text = f"{text} ({confidence:.2f})"
            widget.plate_label.setText(display_text)
            
        except Exception as e:
            self._show_error(lane, f"UI Update Error: {str(e)}")

    def _handle_status(self, lane, status, data):
        widget = self.lane_widgets.get(lane)
        if not widget:
            return
            
        try:
            if status == "success":
                # Get plate text for blacklist checking
                plate_text = data.get('text', '')
                
                # Check if detected text is blacklisted
                if plate_text and self._is_blacklisted(plate_text):
                    # Handle blacklisted vehicle - auto-skip after showing message
                    widget.status_label.setText("ACCESS DENIED - BLACKLISTED VEHICLE")
                    widget.status_label.setStyleSheet("font-size: 14px; color: #dc3545; font-weight: bold;")
                    
                    # Hide all input controls, no skip button needed
                    widget.manual_input.setVisible(False)
                    widget.submit_btn.setVisible(False)
                    widget.skip_btn.setVisible(False)
                    
                    # Change the plate text color to indicate blacklist status
                    widget.plate_label.setText(f"BLACKLISTED: {plate_text}")
                    widget.plate_label.setStyleSheet("color: white; background-color: #dc3545; font-weight: bold;")
                    
                    # Log the denial
                    self._log_entry(lane, data, "denied-blacklist")
                    
                    # Set timer to auto-skip after showing message (5 seconds)
                    if lane in self.active_timers and self.active_timers[lane].isActive():
                        self.active_timers[lane].stop()
                    
                    denial_timer = QTimer(self)
                    denial_timer.timeout.connect(lambda: self._reset_lane(lane))
                    denial_timer.setSingleShot(True)
                    denial_timer.start(5000)  # 5 seconds
                    self.active_timers[lane] = denial_timer
                    print(f"Blacklisted vehicle in {lane} lane, will skip automatically")
                else:
                    # Non-blacklisted vehicle - proceed normally
                    self._activate_gate(lane)
                    
                    # Log the entry
                    self._log_entry(lane, data, "auto")
                    widget.status_label.setText("Access granted - automatic")
                    widget.status_label.setStyleSheet("font-size: 14px; color: #28a745; font-weight: bold;")
                
            elif status == "requires_manual":
                reason = data.get('reason', 'unknown')
                
                # Check if detected text is blacklisted
                detected_text = data.get('text', '')
                if detected_text and self._is_blacklisted(detected_text):
                    # Blacklisted vehicle detected - no skip button needed
                    widget.plate_label.setText(f"BLACKLISTED: {detected_text}")
                    widget.plate_label.setStyleSheet("color: white; background-color: #dc3545; font-weight: bold;")
                    
                    # Hide all controls
                    widget.manual_input.setVisible(False) 
                    widget.submit_btn.setVisible(False)
                    widget.skip_btn.setVisible(False)
                    
                    widget.status_label.setText("ACCESS DENIED - BLACKLISTED VEHICLE")
                    widget.status_label.setStyleSheet("font-size: 14px; color: #dc3545; font-weight: bold;")
                    
                    # Log the denial
                    self._log_entry(lane, data, "denied-blacklist")
                    
                    # Set timer to auto-skip after showing message (5 seconds)
                    if lane in self.active_timers and self.active_timers[lane].isActive():
                        self.active_timers[lane].stop()
                    
                    denial_timer = QTimer(self)
                    denial_timer.timeout.connect(lambda: self._reset_lane(lane))
                    denial_timer.setSingleShot(True)
                    denial_timer.start(5000)  # 5 seconds 
                    self.active_timers[lane] = denial_timer
                    print(f"Blacklisted vehicle in {lane} lane detected in manual mode, will skip automatically")
                else:
                    # Standard manual verification needed - show all controls
                    widget.plate_label.setText(f"Manual input required: {reason}")
                    
                    # Mark this lane as in manual input mode
                    self.lanes_in_manual_mode[lane] = True
                    
                    # Pre-populate with detected text if available
                    if 'text' in data:
                        widget.manual_input.setText(data['text'])
                        widget.manual_input.selectAll()  # Select all for easy editing
                    
                    # Show all manual input controls
                    widget.manual_input.setVisible(True)
                    widget.submit_btn.setVisible(True)
                    widget.skip_btn.setVisible(True)
                    
                    # Reset skip button to normal appearance
                    widget.skip_btn.setText("Skip")
                    widget.skip_btn.setStyleSheet("""
                        background-color: #f39c12;
                        color: white;
                        padding: 8px 15px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                    """)
                    
                    # Set consistent status message styling
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
            # Activate GPIO - For relay modules, set LOW to activate
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.LOW)
                print(f"GPIO {GPIO_PINS[lane]} set LOW for {lane} lane (relay ACTIVE)")
            
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
            # Reset GPIO - For relay modules, set HIGH to deactivate
            if GPIO_PINS.get(lane):
                GPIO.output(GPIO_PINS[lane], GPIO.HIGH)
                print(f"GPIO {GPIO_PINS[lane]} set HIGH for {lane} lane (relay INACTIVE)")
            
            # Clear manual input mode flag
            self.lanes_in_manual_mode.pop(lane, None)
            
            # Reset UI
            widget = self.lane_widgets.get(lane)
            if widget:
                widget.manual_input.clear()
                widget.manual_input.setVisible(False)
                widget.submit_btn.setVisible(False)
                widget.skip_btn.setVisible(False)
                
                # Reset skip button to normal appearance
                widget.skip_btn.setText("Skip")
                widget.skip_btn.setStyleSheet("""
                    background-color: #f39c12;
                    color: white;
                    padding: 8px 15px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                """)
                
                # Reset plate label styling
                widget.plate_label.setText("Scanning...")
                widget.plate_label.setStyleSheet("""
                    font-size: 18px; 
                    color: #2c3e50;
                    background-color: #ecf0f1;
                    padding: 8px;
                    border-radius: 4px;
                """)
                
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
        
        # Clear manual input mode flag
        self.lanes_in_manual_mode.pop(lane, None)
        
        plate_text = widget.manual_input.text().strip()
        if not plate_text:
            widget.status_label.setText("Please enter a license plate number")
            widget.status_label.setStyleSheet("font-size: 14px; color: #ffc107; font-weight: bold;")
            return
        
        # Create data with the manually entered plate text (needed for both paths)
        worker = self.lane_workers.get(lane)
        image_data = None
        if worker and hasattr(worker, "last_detection_data") and worker.last_detection_data:
            image_data = worker.last_detection_data.get("image")
        
        plate_data = {
            "text": plate_text,
            "confidence": 1.0,  # Manual entry has full confidence
            "image": image_data
        }
        
        if self._is_blacklisted(plate_text):
            # Handle blacklisted vehicle - auto-skip after showing message
            widget.status_label.setText("ACCESS DENIED - BLACKLISTED VEHICLE")
            widget.status_label.setStyleSheet("font-size: 14px; color: #dc3545; font-weight: bold;")
            
            # Hide all input controls, no skip button needed
            widget.manual_input.setVisible(False)
            widget.submit_btn.setVisible(False)
            widget.skip_btn.setVisible(False)
            
            # Change the plate text color to indicate blacklist status
            widget.plate_label.setText(f"BLACKLISTED: {plate_text}")
            widget.plate_label.setStyleSheet("color: white; background-color: #dc3545; font-weight: bold;")
            
            # Log the denial - USE plate_data here, NOT data
            self._log_entry(lane, plate_data, "denied-blacklist")
            
            # Set timer to auto-skip after showing message (5 seconds)
            if lane in self.active_timers and self.active_timers[lane].isActive():
                self.active_timers[lane].stop()
            
            denial_timer = QTimer(self)
            denial_timer.timeout.connect(lambda: self._reset_lane(lane))
            denial_timer.setSingleShot(True)
            denial_timer.start(5000)  # 5 seconds
            self.active_timers[lane] = denial_timer
            print(f"Blacklisted vehicle in {lane} lane, will skip automatically")
        else:
            # Normal flow for non-blacklisted vehicles
            self._activate_gate(lane)
            
            # Log the entry - plate_data is already created above
            self._log_entry(lane, plate_data, "manual")
            widget.status_label.setText("Access granted - manual entry")
            widget.status_label.setStyleSheet("font-size: 14px; color: #28a745; font-weight: bold;")

            # Immediately hide input controls to prevent double submission
            widget.manual_input.setVisible(False)
            widget.submit_btn.setVisible(False)
            widget.skip_btn.setVisible(False)

    def _handle_manual_skip(self, lane):
        """Handle skip button press for manual entry"""
        widget = self.lane_widgets.get(lane)
        if not widget:
            return
        
        # Clear manual input mode flag
        self.lanes_in_manual_mode.pop(lane, None)
        
        # Display skip status briefly
        widget.status_label.setText("Vehicle skipped")
        widget.status_label.setStyleSheet("font-size: 14px; color: #f39c12; font-weight: bold;")
        
        # Reset UI
        widget.manual_input.clear()
        widget.manual_input.setVisible(False)
        widget.submit_btn.setVisible(False)
        widget.skip_btn.setVisible(False)
        
        # Add entry to local log table UI only, don't store in database
        current_time = time.time()
        formatted_timestamp = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S.%f')
        
        # Create UI-only log entry
        log_data = {
            "lane": lane,
            "plate": widget.manual_input.text() or "SKIPPED",
            "confidence": 0.0,
            "timestamp": current_time,
            "formatted_time": formatted_timestamp,
            "type": "skipped"
        }
        
        # Only add to the UI display, not to database
        self._add_log_entry(log_data)
        print(f"Vehicle skipped in {lane} lane - only shown in UI, not stored in database")
        
        # Resume worker thread (this already includes cooldown period)
        with self.worker_guard:
            if lane in self.lane_workers and self.lane_workers[lane].isRunning():
                print(f"Skipping vehicle in {lane} lane")
                self.lane_workers[lane].resume_processing()

    def _log_entry(self, lane, data, entry_type):
        try:
            # Current timestamp with ms precision
            current_time = time.time()
            formatted_timestamp = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S.%f')
            
            # Create log entry
            log_data = {
                "lane": lane,
                "plate": data.get('text', 'N/A'),
                "confidence": data.get('confidence', 0.0),
                "timestamp": current_time,
                "formatted_time": formatted_timestamp,
                "type": entry_type,
                "processed": False  # Add a processed flag to track this entry 
            }
            print(f"Log entry created: {log_data}")
            
            # Store denied-blacklist entries locally only in UI, not in DB
            if entry_type == "denied-blacklist":
                # Store a copy of the log data in memory only
                self.local_blacklist_logs.append(log_data.copy())
                
                # Add entry to the log table only locally - don't send to API
                self._add_log_entry(log_data)
                print("Blacklisted vehicle entry - stored only in local UI, not sending to server")
                
                # No need to store blacklist entries in local DB for sync
                # We only want to show them in the UI during the current session
                return
            
            # Skip API logging for skipped entries - only add to local UI
            if entry_type == "skipped":
                # Add entry to the log table only locally
                self._add_log_entry(log_data)
                print("Skipped vehicle entry - only shown in UI, not stored or synced")
                return
            
            # Add entry to the log table display
            self._add_log_entry(log_data)
            
            # CRITICAL FIX: Use a completely different approach for online vs offline
            # to avoid any possible duplicate paths
            
            # Check if we're online or offline FIRST, then take completely separate paths
            if self.api_available and entry_type in ('auto', 'manual'):
                #========================
                # ONLINE MODE PATH
                #========================
                try:
                    # Extract image from data if available
                    frame_image = data.get('image')
                    
                    # Save image to local storage
                    db_manager = DBManager()
                    image_storage = ImageStorage()
                    local_image_path = None
                    
                    if frame_image is not None:
                        local_image_path = image_storage.save_image(
                            frame_image, 
                            lane, 
                            data.get('text', 'N/A'), 
                            entry_type
                        )
                    
                    # Prepare form data for API
                    form_data = {
                        'plate_id': data.get('text', 'N/A'),
                        'lot_id': LOT_ID,
                        'lane': lane,
                        'type': entry_type, 
                        'timestamp': formatted_timestamp
                    }
                    
                    # Prepare files for API
                    files = None
                    if frame_image is not None:
                        _, img_encoded = cv2.imencode('.png', frame_image)
                        img_bytes = img_encoded.tobytes()
                        files = {
                            'image': ('frame.png', img_bytes, 'image/png')
                        }
                    
                    # Try the API call
                    print(f"Making direct API call to services/guard-control/ for {lane} lane, {entry_type} type")
                    success, response = self.api_client.post_with_files(
                        'services/guard-control/',
                        data=form_data,
                        files=files,
                        timeout=(5.0, 15.0)
                    )
                    
                    # Handle API success
                    if success:
                        print(f"API log successful: {response}")
                        self.api_available = True
                        self.api_retry_count = 0
                        self._update_api_status(True)
                        
                        # Store in DB as already synced
                        db_manager.add_log_entry(
                            lane=lane,
                            plate_id=data.get('text', 'N/A'),
                            confidence=data.get('confidence', 0.0),
                            entry_type=entry_type,
                            image_path=local_image_path,
                            synced=True
                        )
                        
                        # Handle local session tracking (parking session)
                        self._create_or_update_parking_session(
                            lane, data.get('text', 'N/A'), 
                            data.get('confidence', 0.0), entry_type, local_image_path
                        )
                        
                        # Since we already handled this completely, don't emit signal
                        # This prevents any possible duplicate processing
                        log_data["processed"] = True
                        return
                        
                    else:
                        # API failed, fall through to offline mode
                        error_msg = str(response) if response else "Unknown error"
                        print(f"API log failed: {error_msg}")
                        
                        # Handle connectivity issues
                        if "Connection" in error_msg or "timeout" in error_msg.lower():
                            self.api_retry_count += 1
                            if self.api_retry_count >= self.max_api_retries:
                                self.api_available = False
                                print(f"Backend API marked as unavailable after {self.max_api_retries} failed attempts")
                                self._update_api_status(False)
                                
                except Exception as e:
                    error_msg = str(e)
                    print(f"API logging error: {error_msg}")
                    
                    # Handle connectivity issues
                    if "Connection" in error_msg or "HTTPConnectionPool" in error_msg or "timeout" in error_msg.lower():
                        self.api_retry_count += 1
                        if self.api_retry_count >= self.max_api_retries:
                            self.api_available = False
                            print(f"Backend API marked as unavailable after {self.max_api_retries} failed attempts")
                            self._update_api_status(False)
            
            #========================
            # OFFLINE MODE PATH - Use this path if online path didn't return
            #========================
            if not log_data["processed"] and entry_type in ('auto', 'manual'):
                print(f"Using offline storage for {lane} lane, {entry_type} type")
                
                # Set proper flags to prevent duplication
                log_data['stored_locally'] = True  # Flag to prevent duplicate storage in main.py
                
                # Save locally in database for later sync
                image_path = self._store_log_locally(lane, data, entry_type, None)
                
                # After storing locally, we need to let main.py know this was already stored
                # to prevent it from creating duplicate entries
                log_data['already_synced'] = False  # Not synced with the server yet
                log_data['image_path'] = image_path
                
                # Only emit signal after we've stored it locally
                # This is used for updating the sync service about this entry
                self.log_signal.emit(log_data)
                
        except Exception as e:
            print(f"Logging error: {str(e)}")
    
    def _create_or_update_parking_session(self, lane, plate_id, confidence, entry_type, image_path):
        """Handle parking session logic (starting or ending a session) using async DB worker"""
        try:
            # First ensure vehicle exists
            vehicle_operation_id = self.db_worker.queue_operation(
                DBOperationType.VEHICLE,
                plate_id=plate_id,
                is_blacklisted=False  # Default to not blacklisted
            )
            
            # Don't need to track this operation
            
            # For entry lane, start a parking session
            if lane == 'entry':
                from config import LOT_ID
                session_operation_id = self.db_worker.queue_operation(
                    DBOperationType.PARKING_SESSION,
                    action='create',
                    lane=lane,
                    plate_id=plate_id,
                    lot_id=LOT_ID,
                    confidence=confidence,
                    image_path=image_path
                )
                
                # Track this operation for completion handling
                self.pending_db_operations[session_operation_id] = {
                    'operation_type': DBOperationType.PARKING_SESSION,
                    'callback': lambda success, result: self._handle_session_complete(success, result, lane, entry_type, session_operation_id)
                }
            
            # For exit lane, end an existing session
            elif lane == 'exit':
                from config import LOT_ID
                session_operation_id = self.db_worker.queue_operation(
                    DBOperationType.PARKING_SESSION,
                    action='update',
                    lane=lane,
                    plate_id=plate_id,
                    lot_id=LOT_ID,
                    confidence=confidence,
                    image_path=image_path
                )
                
                # Track this operation for completion handling
                self.pending_db_operations[session_operation_id] = {
                    'operation_type': DBOperationType.PARKING_SESSION,
                    'callback': lambda success, result: self._handle_session_complete(success, result, lane, entry_type, session_operation_id)
                }
                    
        except Exception as e:
            print(f"Error queueing parking session: {str(e)}")

    def _store_log_locally(self, lane, data, entry_type, existing_image_path=None):
        """Store log locally when API fails, using async DB worker"""
        try:
            # Get image data
            image = data.get('image')
            plate_id = data.get('text', 'N/A')
            confidence = data.get('confidence', 0.0)
            
            # Queue the log entry operation
            operation_id = self.db_worker.queue_operation(
                DBOperationType.LOG_ENTRY,
                lane=lane,
                plate_id=plate_id,
                confidence=confidence,
                entry_type=entry_type,
                image_path=existing_image_path,
                image=image if existing_image_path is None else None,  # Only send image if no path
                synced=False
            )
            
            # Queue the parking session operation
            from config import LOT_ID
            
            # For entry lanes, create a new session
            if lane == 'entry':
                session_operation_id = self.db_worker.queue_operation(
                    DBOperationType.PARKING_SESSION,
                    action='create',
                    lane=lane,
                    plate_id=plate_id,
                    lot_id=LOT_ID,
                    confidence=confidence,
                    image_path=existing_image_path  # Will be updated in callback when log completes
                )
                
                # Track this operation for completion handling
                self.pending_db_operations[session_operation_id] = {
                    'operation_type': DBOperationType.PARKING_SESSION,
                    'callback': lambda success, result: self._handle_session_complete(success, result, lane, entry_type, session_operation_id)
                }
            
            # For exit lanes, update an existing session
            elif lane == 'exit':
                session_operation_id = self.db_worker.queue_operation(
                    DBOperationType.PARKING_SESSION,
                    action='update',
                    lane=lane,
                    plate_id=plate_id,
                    lot_id=LOT_ID,
                    confidence=confidence,
                    image_path=existing_image_path  # Will be updated in callback when log completes
                )
                
                # Track this operation for completion handling
                self.pending_db_operations[session_operation_id] = {
                    'operation_type': DBOperationType.PARKING_SESSION,
                    'callback': lambda success, result: self._handle_session_complete(success, result, lane, entry_type, session_operation_id)
                }
            
            # Track the log operation - we'll update the image path when it completes
            log_data = {
                'lane': lane,
                'plate': plate_id,
                'confidence': confidence,
                'timestamp': time.time(),
                'formatted_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                'type': entry_type,
                'already_synced': False  # Not synced with the server yet
            }
            
            self.pending_db_operations[operation_id] = {
                'operation_type': DBOperationType.LOG_ENTRY,
                'log_data': log_data,
                'notify_sync': True  # Flag to emit log_signal when complete
            }
            
            print(f"Queued log entry for async storage with ID {operation_id}")
            
            # Return placeholder - real path will be set in the operation complete handler
            return existing_image_path
            
        except Exception as e:
            print(f"Error queueing log for local storage: {str(e)}")
            return None
    
    def _handle_session_complete(self, success, result, lane, entry_type, operation_id):
        """Handle completion of an async parking session operation"""
        if not success:
            print(f"Failed to create/update parking session: {result}")
            return
        
        session_id = result.get('session_id')
        if not session_id:
            print("No session ID returned from operation")
            return
            
        print(f"Successfully processed parking session {session_id} for {lane} lane")
        
        # Now create a barrier action record for this session
        barrier_operation_id = self.db_worker.queue_operation(
            DBOperationType.BARRIER_ACTION,
            session_id=session_id,
            action_type=lane,  # 'entry' or 'exit'
            trigger_type=entry_type  # 'auto' or 'manual'
        )
        
        # Track this operation
        self.pending_db_operations[barrier_operation_id] = {
            'operation_type': DBOperationType.BARRIER_ACTION
        }

    def _add_log_entry(self, data):
        """Add a new entry to the log area"""
        try:
            if 'date' in data and 'time' in data:
                # API format
                date_str = data['date']
                time_str = data['time'].split('.')[0]
                lane = data.get('lane', 'N/A')
                plate = data.get('license_plate', 'N/A')
                entry_type = data.get('type', 'N/A')
            elif 'formatted_time' in data:
                # Use pre-formatted timestamp if available
                formatted_time = data['formatted_time']
                date_str, time_str = formatted_time.split(' ')[0], formatted_time.split(' ')[1].split('.')[0]
                lane = data.get('lane', 'N/A')
                plate = data.get('plate', 'N/A')
                entry_type = data.get('type', 'N/A')
            else:
                # Calculate from timestamp
                timestamp = data.get('timestamp', time.time())
                date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
                time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
                lane = data.get('lane', 'N/A')
                plate = data.get('plate', 'N/A')
                entry_type = data.get('type', 'N/A')
            
            # Create log entry widget
            log_widget = QWidget()
            log_layout = QHBoxLayout(log_widget)
            log_layout.setContentsMargins(0, 0, 0, 0)  # Remove container margins
            log_layout.setSpacing(1)  # Minimal spacing between columns
            
            # Create labels for each piece of information
            date_label = QLabel(f"{date_str} {time_str}")
            lane_label = QLabel(lane.capitalize())
            plate_label = QLabel(plate)
            type_label = QLabel(entry_type.capitalize())
            
            # Center align all text
            date_label.setAlignment(Qt.AlignCenter)
            lane_label.setAlignment(Qt.AlignCenter)
            plate_label.setAlignment(Qt.AlignCenter)
            type_label.setAlignment(Qt.AlignCenter)
            
            # Style based on entry/exit
            if lane.lower() == 'entry':
                lane_color = "#27ae60"  # Green
            else:
                lane_color = "#e74c3c"  # Red
                
            # Add labels to layout with the same proportions as headers
            log_layout.addWidget(date_label, 3)  # 30% of space
            log_layout.addWidget(lane_label, 1)  # 10% of space
            log_layout.addWidget(plate_label, 2)  # 20% of space
            log_layout.addWidget(type_label, 1)  # 10% of space
            
            # Add alternating row colors with full-width background
            row_index = self.logs_layout.count()
            if row_index % 2 == 0:
                log_widget.setStyleSheet("background-color: #f5f5f5;")
            else:
                log_widget.setStyleSheet("background-color: white;")
                
            # Apply consistent styling
            cell_style = "padding: 8px; border-bottom: 1px solid #ddd;"
            date_label.setStyleSheet(cell_style)
            lane_label.setStyleSheet(f"color: {lane_color}; font-weight: bold; {cell_style}")
            plate_label.setStyleSheet(cell_style)
            type_label.setStyleSheet(cell_style)
            
            # Add widget to layout
            self.logs_layout.addWidget(log_widget)
            
        except Exception as e:
            print(f"Error adding log entry: {str(e)}")

    def _clear_log_table(self):
        """Clear log table"""
        while self.logs_layout.count():
            item = self.logs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _check_api_connection(self):
        """Regularly check if API server is online with smarter retry logic"""
        try:
            # Check when the last reconnection attempt was made
            current_time = time.time()
            time_since_last_success = current_time - self.last_successful_connection
            
            # Skip check if the API is available and we checked recently (within the last minute)
            if self.api_available and self.consecutive_failures == 0 and time_since_last_success < 60:
                return
                
            # Use a very short timeout for connectivity checks to avoid blocking
            api_check_timeout = (2.0, 3.0)  # 2s connect, 3s read
            
            # Use the dedicated health check endpoint (no auth required)
            success, _ = self.api_client.get('services/health', timeout=api_check_timeout, auth_required=False)
            
            # Update UI based on API status
            if success:
                # Server is reachable
                self.last_successful_connection = current_time
                self.consecutive_failures = 0
                
                if not self.api_available:
                    # Only if we previously thought it was unavailable, check auth
                    print("API server is reachable, checking authentication...")
                    
                    # Check authentication with a lightweight request
                    auth_success, _ = self.api_client.get(
                        'vehicles/blacklisted/', 
                        params={'skip': 0, 'limit': 1},
                        timeout=api_check_timeout
                    )
                    
                    if auth_success:
                        # Auth is valid, update status
                        self.api_available = True
                        self.api_retry_count = 0
                        self._update_api_status(True)
                        print("Authentication is valid, API marked as available")
                        # Try to update occupancy after regaining connectivity
                        self._update_occupancy()
                    else:
                        # Auth failed but server is up - don't auto-reconnect
                        # This requires manual intervention as it might be a token expiry
                        print("Authentication check failed despite server being available")
                        if not self.api_reconnect_button.isVisible():
                            self.api_available = False
                            self._update_api_status(False)
            else:
                # Server not reachable
                self.consecutive_failures += 1
                print(f"API server not reachable, consecutive failures: {self.consecutive_failures}")
                
                # Only mark as unavailable after multiple consecutive failures
                if self.consecutive_failures >= self.max_api_retries and self.api_available:
                    self.api_available = False
                    self._update_api_status(False)
                    print(f"API marked as unavailable after {self.consecutive_failures} consecutive failures")
                
        except Exception as e:
            self.consecutive_failures += 1
            # Only log and change status after multiple failures to avoid noise
            if self.consecutive_failures >= self.max_api_retries:
                if self.api_available:
                    self.api_available = False
                    self._update_api_status(False)
                print(f"API connection check error (attempt {self.consecutive_failures}): {str(e)}")

    def _update_api_status(self, is_connected):
        """Update backend API status indicators"""
        if is_connected:
            self.api_status_indicator.setStyleSheet("background-color: green; border-radius: 7px;")
            self.api_status_label.setText("Server: Connected")
            self.api_reconnect_button.setVisible(False)
        else:
            self.api_status_indicator.setStyleSheet("background-color: red; border-radius: 7px;")
            self.api_status_label.setText("Server: Disconnected")
            self.api_reconnect_button.setVisible(True)

    def _reconnect_api(self):
        """Manually attempt to reconnect to the API"""
        self.api_reconnect_button.setText("Reconnecting...")
        self.api_reconnect_button.setEnabled(False)
        
        # Reset counters
        self.api_retry_count = 0
        self.consecutive_failures = 0
        
        # Check connection
        try:
            print("Attempting to reconnect to the API server...")
            api_check_timeout = (3.0, 5.0)  # Slightly longer timeout for manual reconnect
            
            # First check if the server is available at all using the health endpoint
            success, _ = self.api_client.get('services/health', timeout=api_check_timeout, auth_required=False)
            
            if success:
                print("Server is available, checking authentication...")
                
                # Check if current auth token is still valid with a simple request
                auth_success, auth_response = self.api_client.get('vehicles/blacklisted/', 
                                                               params={'skip': 0, 'limit': 1}, 
                                                               timeout=api_check_timeout,
                                                               retry_on_auth_fail=False)  # Don't auto-retry
                
                if auth_success:
                    # Authentication is valid, just update status
                    print("Authentication is already valid!")
                    self.api_available = True
                    self._update_api_status(True)
                    self.last_successful_connection = time.time()
                    # Update data after reconnection
                    self._update_occupancy()
                    self._fetch_logs()
                    self.api_reconnect_button.setText("Reconnect")
                    self.api_reconnect_button.setEnabled(True)
                    self.api_reconnect_button.setVisible(False)
                    return
                else:
                    # Authentication failed, try to log in again
                    print("Authentication is invalid, attempting to re-login...")
                    auth_manager = AuthManager()
                    
                    if auth_manager.username and auth_manager.password:
                        print(f"Attempting to login as {auth_manager.username}")
                        login_success, login_msg, _ = self.api_client.login(
                            auth_manager.username,
                            auth_manager.password,
                            timeout=api_check_timeout
                        )
                        
                        if login_success:
                            print("Authentication refreshed successfully")
                            self.api_available = True
                            self.last_successful_connection = time.time()
                            self._update_api_status(True)
                            # Update data after reconnection
                            self._update_occupancy()
                            self._fetch_logs()
                            self.api_reconnect_button.setText("Reconnect")
                            self.api_reconnect_button.setEnabled(True)
                            self.api_reconnect_button.setVisible(False)
                            return
                        else:
                            print(f"Login failed: {login_msg}")
                            # Show error message to user
                            QMessageBox.warning(self, "Authentication Error", 
                                               f"Could not reconnect: {login_msg}\nYou may need to restart the application.")
                    else:
                        print("No stored credentials for authentication")
                        QMessageBox.warning(self, "Connection Error", 
                                           "Session expired. Please restart the application to log in again.")
            else:
                self.api_available = False
                self._update_api_status(False)
                QMessageBox.warning(self, "Connection Error", 
                                  "Could not connect to the server. Please check your network connection.")
                
        except Exception as e:
            print(f"Manual reconnect error: {str(e)}")
            self.api_available = False
            self._update_api_status(False)
        
        # If we got here, reconnection failed
        self.api_reconnect_button.setText("Reconnect")
        self.api_reconnect_button.setEnabled(True)

    def _update_occupancy(self):
        """Update the occupancy display with data from API asynchronously"""
        # Set loading state while waiting for API
        self.occupancy_label.setText("Loading occupancy data...")
        self.occupancy_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: white;
            background-color: #7f8c8d;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        """)
        
        # Define the API call function
        def fetch_occupancy():
            from config import LOT_ID
            return self.api_client.get(
                f'services/lot-occupancy/{LOT_ID}',
                timeout=(3.0, 5.0)
            )
        
        # Perform the call asynchronously
        self._perform_async_api_call("occupancy", fetch_occupancy)

    def _process_occupancy_data(self, data):
        """Process occupancy data after async fetch"""
        try:
            # Extract data from response
            lot_name = data.get('lot_name', 'Unknown')
            capacity = data.get('capacity', 0)
            occupied = data.get('occupied', 0)
            available = data.get('available', 0)
            occupancy_rate = data.get('occupancy_rate', 0)
            
            # Update lot name
            self.lot_name_label.setText(f"{lot_name} (ID: {LOT_ID})")
            
            # Update labels with the data
            self.capacity_value.setText(f"{capacity} vehicles")
            
            # Update visual indicator based on occupancy rate
            self._update_occupancy_visual(occupancy_rate, occupied, available)
            
            # Update timestamp
            self.update_time.setText(datetime.now().strftime("%H:%M:%S"))
            
            print(f"Occupancy updated: {occupancy_rate}% ({occupied}/{capacity})")
        except Exception as e:
            print(f"Error processing occupancy data: {str(e)}")
            self.occupancy_label.setText("Error processing data")

    def _fetch_logs(self):
        """Fetch logs for the current lot from the API and add local blacklist entries"""
        try:
            # Get lot_id from config
            from config import LOT_ID
            
            # Use reasonable timeout for log fetching
            logs_timeout = (3.0, 7.0)  # 3s connect, 7s read
            
            # Fetch logs with pagination
            success, response = self.api_client.get(
                'services/logs/', 
                params={'skip': 0, 'limit': 100, 'lot_id': LOT_ID},
                timeout=logs_timeout
            )
            
            # Clear existing log entries
            self._clear_log_table()
            
            # Add fetched log entries to the log area
            if success and response:
                for log_entry in response:
                    self._add_log_entry(log_entry)
            else:
                print(f"Error fetching logs: {response}")
            
            # Add local blacklist entries back to the log table
            for blacklist_entry in self.local_blacklist_logs:
                self._add_log_entry(blacklist_entry)
            
        except Exception as e:
            print(f"Error fetching logs: {str(e)}")

    def refresh_data(self):
        """Refresh all dynamic data from the API"""
        # Update occupancy information
        self._update_occupancy()
        
        # Fetch today's logs for the lot
        self._fetch_logs()
        
        # Show success message temporarily
        status_msg = QLabel("Data refreshed")
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
                # Only restart workers that are not running or in ERROR state
                # IMPORTANT: Do NOT restart workers in PAUSED state (which happens during manual input)
                if not worker.isRunning() or (hasattr(worker, 'state') and worker.state == LaneState.ERROR):
                    # Check if this lane is waiting for manual input
                    if lane in self.lanes_in_manual_mode:
                        # If lane is flagged for manual input, don't restart the worker
                        print(f"Worker for {lane} lane is in manual input mode - not restarting")
                        continue
                    
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
        # Get the occupancy layout
        occupancy_layout = self.occupancy_frame.layout()
        
        # Percentage indicators removed
        
        # Add capacity info
        capacity_layout = QHBoxLayout()
        capacity_label = QLabel("Total capacity:")
        capacity_label.setStyleSheet("color: #7f8c8d;")
        
        last_updated = QLabel("Last updated:")
        last_updated.setStyleSheet("color: #7f8c8d;")
        
        # Arrange capacity info with existing widgets
        capacity_layout.addWidget(capacity_label)
        capacity_layout.addWidget(self.capacity_value)
        capacity_layout.addStretch(1)
        capacity_layout.addWidget(last_updated)
        capacity_layout.addWidget(self.update_time)
        
        # Add capacity info to layout
        occupancy_layout.addLayout(capacity_layout)

    # Enhanced log table with filtering
    def _enhance_log_table(self):
        """Add filtering capabilities to log table"""
        filter_layout = QHBoxLayout()
        
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
        filter_layout.addWidget(lane_label)
        filter_layout.addWidget(self.lane_filter)
        filter_layout.addWidget(type_label)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addStretch()
        filter_layout.addWidget(apply_btn)
        
        # Find the log widget's parent
        try:
            # Get the log frame safely by traversing up from logs_layout
            if hasattr(self, 'logs_layout') and self.logs_layout is not None:
                log_widget = self.logs_layout.parent()
                if log_widget is not None:
                    scroll_area = log_widget.parent()
                    if scroll_area is not None:
                        log_frame = scroll_area.parent()
                        if isinstance(log_frame, QFrame) and log_frame.layout() is not None:
                            log_layout = log_frame.layout()
                            # Insert filter layout after title but before log scroll area
                            log_layout.insertLayout(1, filter_layout)
                            return
        
            # Fallback: Create a new frame for filters if we couldn't find the log frame
            print("Warning: Could not locate log frame layout, creating alternate filter display")
            filter_frame = QFrame()
            filter_frame.setLayout(filter_layout)
            filter_frame.setStyleSheet("""
                QFrame {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    padding: 5px;
                    margin-bottom: 5px;
                }
            """)
            
            # Find main layout to add the filter frame
            main_layout = None
            for i in range(self.layout().count()):
                item = self.layout().itemAt(i)
                if item.widget() and isinstance(item.widget(), QScrollArea):
                    scroll_widget = item.widget().widget()
                    if scroll_widget and scroll_widget.layout():
                        main_layout = scroll_widget.layout()
                        break
            
            if main_layout:
                # Add filter frame just before the log frame
                for i in range(main_layout.count()):
                    item = main_layout.itemAt(i)
                    if item.widget() and isinstance(item.widget(), QFrame) and "Activity Log" in item.widget().findChildren(QLabel)[0].text():
                        main_layout.insertWidget(i, filter_frame)
                        break
        except Exception as e:
            print(f"Error setting up log filters: {str(e)}")

    def _apply_log_filters(self):
        """Apply filters to log table"""
        lane_filter = self.lane_filter.currentText().lower()
        type_filter = self.type_filter.currentText().lower()
        
        # Get lot_id from config
        from config import LOT_ID
        
        # Prepare filter parameters
        params = {'skip': 0, 'limit': 100, 'lot_id': LOT_ID}
        if lane_filter != "all":
            params['lane'] = lane_filter
        if type_filter != "all":
            params['type'] = type_filter
        
        # Fetch filtered logs
        success, response = self.api_client.get('services/logs/', params=params)
        
        # Clear existing log entries
        self._clear_log_table()
        
        # Add filtered log entries
        if success and response:
            for log_entry in response:
                self._add_log_entry(log_entry)
        
        # Add blacklist entries (filtered as needed)
        for blacklist_entry in self.local_blacklist_logs:
            # Apply the same filters to local blacklist entries
            if lane_filter != "all" and blacklist_entry.get("lane") != lane_filter:
                continue
            if type_filter != "all" and blacklist_entry.get("type") != type_filter:
                continue
            self._add_log_entry(blacklist_entry)
        
        # Show applied filters
        filter_msg = "Filters applied: "
        filters = []
        
        if lane_filter != "all":
            filters.append(f"Lane: {lane_filter}")
        if type_filter != "all":
            filters.append(f"Type: {type_filter}")
        
        if filters:
            print(filter_msg + ", ".join(filters))
        else:
            print("No filters applied, showing all logs")

    def _update_blacklist_cache(self):
        """Fetch and update the local blacklist cache asynchronously"""
        # Log current blacklist state before update
        print(f"Updating blacklist cache - current entries: {len(self.blacklisted_plates)}")
        if self.debug_blacklist:
            print(f"Current blacklist before update: {self.blacklisted_plates}")
            
        # Define the API call function to use in the thread
        def fetch_blacklist():
            print("Sending blacklist API request...")
            return self.api_client.get(
                'vehicles/blacklisted/',
                params={'skip': 0, 'limit': 1000},
                timeout=(3.0, 5.0)
            )
        
        # Perform the call asynchronously
        self._perform_async_api_call("blacklist", fetch_blacklist)

    def _is_blacklisted(self, plate):
        """Check if a license plate is blacklisted using local cache"""
        if not plate:
            return False
            
        # Normalize plate format for comparison
        normalized_plate = plate.upper().strip()
        
        # Check if the plate is in the blacklist set
        result = normalized_plate in self.blacklisted_plates
        
        # Add debug logging - only log when plate is actually found to avoid noise
        if result:
            print(f"BLACKLIST CHECK: Plate {normalized_plate} IS blacklisted")
        
        # Print current blacklist when making a check (for debugging purposes)
        if hasattr(self, 'debug_blacklist') and self.debug_blacklist:
            print(f"Current blacklist: {self.blacklisted_plates}")
            
        return result

    def force_refresh_blacklist(self):
        """Force an immediate refresh of the blacklist data"""
        self._update_blacklist_cache()
        self.status_label.setText("Blacklist refreshed")
        QTimer.singleShot(3000, lambda: self.status_label.setText(""))

    def _perform_async_api_call(self, operation_type, api_func, *args, **kwargs):
        """Perform API call in a non-blocking way with visual feedback"""
        # Create operation ID
        operation_id = f"{operation_type}_{time.time()}"
        
        # Show loading indicator if needed
        self._safe_update_ui(lambda: self._show_loading_indicator(operation_type, True))
        
        # Create a worker thread for the API call
        class ApiWorker(QThread):
            finished = pyqtSignal(str, bool, object)
            api_status_changed = pyqtSignal(bool)
            
            def __init__(self, op_id, func, args, kwargs, parent=None):
                super().__init__()
                self.op_id = op_id
                self.func = func
                self.args = args
                self.kwargs = kwargs
                self._running = True
                self._parent = parent
                
            def run(self):
                try:
                    if self._running:
                        result = self.func(*self.args, **self.kwargs)
                        if self._running:  # Check again in case we were terminated
                            # Check for backend API call errors
                            if isinstance(result, tuple) and len(result) >= 2 and result[0] is False:
                                # This is an (success, error_message) tuple indicating API failure
                                error_msg = result[1]
                                
                                # Make sure this is a backend API failure, not PlateRecognizer API
                                if not "PlateRecognizer" in str(error_msg):
                                    print(f"Backend API call failed: {error_msg}")
                                    
                                    # Check if the parent has the API-related attributes
                                    if hasattr(self._parent, 'api_available'):
                                        self._parent.api_available = False
                                        if hasattr(self._parent, '_update_api_status'):
                                            QMetaObject.invokeMethod(
                                                self._parent, 
                                                "_update_api_status", 
                                                Qt.QueuedConnection,
                                                Q_ARG(bool, False)
                                            )
                                else:
                                    print(f"PlateRecognizer API call failed: {error_msg} (not affecting backend API status)")
                            self.finished.emit(self.op_id, True, result)
                except Exception as e:
                    if self._running:
                        # Check if this is a PlateRecognizer API exception
                        if "PlateRecognizer" in str(e):
                            print(f"PlateRecognizer API call exception: {str(e)} (not affecting backend API status)")
                        else:
                            # Backend API is down
                            if hasattr(self._parent, 'api_available'):
                                self._parent.api_available = False
                                if hasattr(self._parent, '_update_api_status'):
                                    QMetaObject.invokeMethod(
                                        self._parent, 
                                        "_update_api_status", 
                                        Qt.QueuedConnection,
                                        Q_ARG(bool, False)
                                    )
                            print(f"Backend API call exception: {str(e)}")
                        self.finished.emit(self.op_id, False, str(e))
                    
            def stop(self):
                self._running = False
        
        # Create and start worker
        worker = ApiWorker(operation_id, api_func, args, kwargs, self)
        
        # Store reference to prevent garbage collection - do this before connecting signal
        if not hasattr(self, '_api_workers'):
            self._api_workers = {}
        
        # Clean up any previous thread with the same operation type
        for old_id in list(self._api_workers.keys()):
            if old_id.startswith(operation_type) and self._api_workers[old_id].isRunning():
                try:
                    old_worker = self._api_workers[old_id]
                    old_worker.stop()
                    old_worker.finished.disconnect()  # Disconnect signals before stopping
                    if not old_worker.wait(300):  # Wait up to 300ms
                        print(f"Warning: Thread {old_id} not responding to stop request")
                    del self._api_workers[old_id]
                except Exception as e:
                    print(f"Error cleaning up thread {old_id}: {str(e)}")
        
        # Connect signal after thread is stored and before starting
        worker.finished.connect(lambda op_id, success, result: 
                               self._handle_async_result(op_id, success, result))
        
        self._api_workers[operation_id] = worker
        
        # Start the worker
        worker.start()
        
        return operation_id

    def _handle_async_result(self, operation_id, success, result):
        """Handle the result from an async API call"""
        # Extract operation type from ID
        operation_type = operation_id.split('_')[0]
        
        # Hide loading indicator
        self._safe_update_ui(lambda: self._show_loading_indicator(operation_type, False))
        
        # Process result based on operation type
        try:
            if operation_type == "blacklist":
                if success:
                    # The result contains a tuple of (success, data)
                    api_success, api_data = result
                    
                    # Log the raw API response for debugging
                    print(f"Blacklist API response - success: {api_success}, data: {api_data}")
                    
                    if api_success:
                        # Only update the cache if we got a valid response
                        if api_data is not None:
                            # Create a new set for blacklisted plates
                            new_blacklist = set()
                            
                            for vehicle in api_data:
                                if vehicle.get('is_blacklisted', False):
                                    plate = vehicle.get('plate_id', '').upper()
                                    new_blacklist.add(plate)
                                    print(f"Adding blacklisted plate: {plate}")
                            
                            # Before updating the blacklist, log the change
                            old_count = len(self.blacklisted_plates)
                            new_count = len(new_blacklist)
                            print(f"Updating blacklist: old count={old_count}, new count={new_count}")
                            
                            # Only replace the cache if we have a confirmed response (empty array or with data)
                            if new_count > 0 or api_data == []:
                                # Replace the cache atomically
                                self.blacklisted_plates = new_blacklist
                                self.last_blacklist_update = time.time()
                                print(f"Blacklist updated: {len(self.blacklisted_plates)} vehicles")
                            else:
                                print("Ignoring empty blacklist response - keeping current blacklist")
                        else:
                            print("Received None for blacklist data - keeping current blacklist")
                    else:
                        print(f"Failed to update blacklist: {api_data}")
                else:
                    print(f"Failed to execute blacklist API call: {result}")
            
            elif operation_type == "logs":
                if success:
                    # The result contains a tuple of (success, data)
                    api_success, api_data = result
                    
                    if api_success:
                        # Clear existing log entries
                        self._clear_log_table()
                        
                        # Add log entries to the log area if there are any
                        if api_data:
                            for log_entry in api_data:
                                self._add_log_entry(log_entry)
                        else:
                            print("No log data available")
                    else:
                        print(f"Failed to fetch logs: {api_data}")
                else:
                    print(f"Failed to execute logs API call: {result}")
            
            elif operation_type == "occupancy":
                if success:
                    # The result contains a tuple of (success, data)
                    api_success, api_data = result
                    
                    if api_success and api_data:
                        self._process_occupancy_data(api_data)
                    else:
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
                else:
                    print(f"Failed to execute occupancy API call: {result}")
        
        except Exception as e:
            print(f"Error processing {operation_type} result: {str(e)}")
        
        # Clean up worker reference - do this in a safe way
        try:
            if hasattr(self, '_api_workers') and operation_id in self._api_workers:
                worker = self._api_workers[operation_id]
                # Only remove if it's no longer running
                if not worker.isRunning():
                    del self._api_workers[operation_id]
        except Exception as e:
            print(f"Error cleaning up thread reference: {str(e)}")

    def _show_loading_indicator(self, operation_type, is_loading):
        """Show or hide loading indicator for specific operation"""
        if operation_type == "blacklist":
            # No UI element for blacklist loading currently
            pass
        elif operation_type == "logs":
            # Could add a loading indicator to log table
            pass
        elif operation_type == "occupancy":
            if is_loading:
                self.occupancy_label.setText("Loading occupancy data...")
                self.occupancy_label.setStyleSheet("""
                    font-size: 24px;
                    font-weight: bold;
                    color: white;
                    background-color: #7f8c8d;
                    padding: 10px;
                    border-radius: 4px;
                    margin: 10px 0;
                """)

    def _update_occupancy_visual(self, occupancy_rate, occupied, available):
        """Update the visual representation of occupancy"""
        # Set color based on occupancy rate
        if occupancy_rate < 60:
            color = "#27ae60"  # Green
        elif occupancy_rate < 85:
            color = "#f1c40f"  # Yellow
        else:
            color = "#e74c3c"  # Red
        
        # Update the occupancy label
        self.occupancy_label.setText(f"{occupancy_rate}% ({occupied} used / {available} free)")
        self.occupancy_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: white;
            background-color: {color};
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        """)

    def closeEvent(self, event):
        """Handle application close properly by cleaning up threads"""
        try:
            # Clear manual input mode flags
            self.lanes_in_manual_mode.clear()
            
            # Stop all API worker threads first
            if hasattr(self, '_api_workers'):
                for thread_id, worker in list(self._api_workers.items()):
                    if worker and worker.isRunning():
                        worker.stop()  # Signal the thread to stop
                        worker.wait(500)  # Wait up to 500ms for clean shutdown
            
            # Stop the DB worker thread
            if hasattr(self, 'db_worker'):
                print("Stopping DB worker thread...")
                self.db_worker.stop()
                self.db_worker.wait(1000)  # Wait up to 1 second for clean shutdown
                print("DB worker thread stopped")
            
            # Now stop camera workers
            with self.worker_guard:
                for lane, worker in list(self.lane_workers.items()):
                    if worker and worker.isRunning():
                        worker.stop()
                        worker.wait(1000)  # Wait up to 1 second for clean shutdown
            
            # Clean GPIO
            try:
                GPIO.cleanup()
            except:
                pass
            
            # Accept the close event
            event.accept()
        except Exception as e:
            print(f"Error during application shutdown: {str(e)}")
            event.accept()  # Accept anyway to ensure the app closes

    def _handle_db_operation_complete(self, operation_id, success, result):
        """Handle completion of asynchronous database operations"""
        if operation_id not in self.pending_db_operations:
            # Operation not tracked or already handled
            return
        
        # Get the original operation data
        operation_data = self.pending_db_operations.pop(operation_id)
        operation_type = operation_data.get('operation_type')
        callback = operation_data.get('callback')
        
        if not success:
            print(f"Database operation {operation_id} failed: {result}")
            if callback:
                callback(False, result)
            return
        
        print(f"Database operation {operation_id} completed successfully")
        
        # Call the callback function if provided
        if callback:
            callback(True, result)
        
        # Process specific operation results if needed
        if operation_type == DBOperationType.LOG_ENTRY:
            # For log entries, we might need to notify sync service
            if operation_data.get('notify_sync', False):
                log_data = operation_data.get('log_data', {}).copy()
                log_data['stored_locally'] = True
                log_data['image_path'] = result.get('image_path')
                self.log_signal.emit(log_data)

    def _check_ui_responsiveness(self):
        """Check UI responsiveness and update status"""
        elapsed_ms = self.last_ui_check.elapsed()
        if elapsed_ms > self.ui_blocked_threshold:
            print(f"UI blocked for {elapsed_ms} ms")
            # Don't try to update UI from here as it could make things worse
        self.last_ui_check.restart()

    def _safe_update_ui(self, update_func):
        """Thread-safe way to update UI elements"""
        if threading.current_thread() is threading.main_thread():
            # If we're already on the main thread, just call the function
            update_func()
        else:
            # Otherwise use invokeMethod to execute on the main thread
            # We'll use a lambda that takes no arguments since we're capturing our function
            QMetaObject.invokeMethod(self, "_execute_ui_update", Qt.QueuedConnection,
                                  Q_ARG(object, update_func))
    
    def _execute_ui_update(self, func):
        """Execute the UI update function on the main thread"""
        try:
            func()
        except Exception as e:
            print(f"Error updating UI: {str(e)}")
