from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                            QPushButton, QLabel, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QPalette, QBrush
from app.controllers.api_client import ApiClient
from app.utils.auth_manager import AuthManager

class LoginScreen(QWidget):
    login_success = pyqtSignal()  # Signal for screen navigation
    login_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_styles()
        self.api_client = ApiClient()
        self.auth_manager = AuthManager()

    def setup_ui(self):
        # Set up main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create a container widget for the login form
        login_container = QWidget()
        login_container.setFixedSize(420, 380)
        login_container.setObjectName("loginContainer")
        
        # Create login form layout
        form_layout = QVBoxLayout(login_container)
        form_layout.setContentsMargins(30, 30, 30, 30)
        form_layout.setSpacing(20)
        
        # Title
        title = QLabel("Smart Parking System")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("title")
        
        # Login header
        login_header = QLabel("Log in")
        login_header.setObjectName("loginHeader")
        
        # Form fields
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setProperty("class", "loginInput")
        self.username.setMinimumHeight(45)  # Increased height
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setProperty("class", "loginInput")
        self.password.setMinimumHeight(45)  # Increased height
        
        # Login button
        login_btn = QPushButton("Log in")
        login_btn.setObjectName("loginButton")
        login_btn.clicked.connect(self.attempt_login)
        login_btn.setMinimumHeight(45)  # Match the height of input fields
        
        # Status label for error messages
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setObjectName("statusLabel")
        
        # Assemble form
        form_layout.addWidget(title)
        form_layout.addSpacerItem(QSpacerItem(20, 20))
        form_layout.addWidget(login_header)
        form_layout.addWidget(self.username)
        form_layout.addWidget(self.password)
        form_layout.addWidget(login_btn)
        form_layout.addWidget(self.status_label)
        form_layout.addStretch()
        
        # Center the login container
        main_layout.addStretch(1)
        center_layout = QHBoxLayout()
        center_layout.addStretch(1)
        center_layout.addWidget(login_container)
        center_layout.addStretch(1)
        main_layout.addLayout(center_layout)
        main_layout.addStretch(1)
        
        self.setLayout(main_layout)

        self.setAutoFillBackground(True)
        
        # Set background image
        self.set_background_image("/home/raspberrypi/Documents/ParkingControl/app/resources/parking.jpg")  # Update path as needed

    def set_background_image(self, image_path):
        try:
            # Set background for the main window using QPalette
            background = QPixmap(image_path)
            palette = QPalette()
            palette.setBrush(QPalette.Background, QBrush(background))
            self.setPalette(palette)
            
            # Style the login container and controls with supported properties
            self.setStyleSheet(f"""
                #loginContainer {{
                    background-color: white;
                    border-radius: 8px;
                    border: 1px solid #cccccc;
                }}
                
                #title {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2c3e50;
                }}
                
                #loginHeader {{
                    font-size: 20px;
                    font-weight: bold;
                    color: #333;
                }}
                
                .loginInput {{
                    font-size: 16px;
                    padding: 12px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }}
                
                #loginButton {{
                    background-color: #00b8d4;
                    color: white;
                    padding: 12px;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: bold;
                }}
                
                #loginButton:hover {{
                    background-color: #0095b3;
                }}
                
                #statusLabel {{
                    color: #dc3545;
                    font-size: 14px;
                }}
            """)
        except Exception as e:
            print(f"Failed to set background image: {str(e)}")
            # Fallback to a color background
            self.setStyleSheet("""
                QWidget {
                    background-color: #0a2a3b;
                }
            """)

    def setup_styles(self):
        # Additional styles are now handled in set_background_image method
        pass

    def attempt_login(self):
        # Show loading state
        self.status_label.setText("Logging in...")
        self.status_label.setStyleSheet("color: #007bff") # Blue color for loading
        self.update_ui_state(is_loading=True)
        
        # Create a timer to handle potential timeouts visually
        timeout_timer = QTimer(self)
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(self.handle_login_timeout)
        timeout_timer.start(8000)  # 8 second visual timeout
        
        username = self.username.text()
        password = self.password.text()
        
        # Validate input
        if not username or not password:
            self.status_label.setText("Username and password are required")
            self.status_label.setStyleSheet("color: #dc3545") # Red color for error
            self.update_ui_state(is_loading=False)
            timeout_timer.stop()
            return
        
        # Import LOT_ID from config
        from config import LOT_ID
        
        # Use a more aggressive timeout for login to avoid UI freezing
        login_timeout = (5, 10)  # 5s connect, 10s read
        
        # Use the ApiClient to handle login
        success, message, user_data = self.api_client.login(username, password, timeout=login_timeout)
        
        # Stop the visual timeout timer
        timeout_timer.stop()
        
        if success:
            # Debug log the assigned lots
            print(f"User assigned lots: {self.api_client.assigned_lots}")
            print(f"Configured lot ID: {LOT_ID}")
            
            # Check if the user has access to this parking lot
            if not self.api_client.is_lot_assigned(LOT_ID):
                self.status_label.setText(f"You are not assigned to Lot #{LOT_ID}")
                self.status_label.setStyleSheet("color: #dc3545") # Red color for error
                self.api_client.auth_manager.clear()  # Clear auth since user can't use this lot
                self.login_failed.emit(f"Not assigned to Lot #{LOT_ID}")
                self.update_ui_state(is_loading=False)
                return
            
            # Login successful, emit signal for navigation
            self.login_success.emit()
        else:
            # Login failed, display error message
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #dc3545") # Red color for error
            self.login_failed.emit(message)
            self.update_ui_state(is_loading=False)
    
    def handle_login_timeout(self):
        """Visual indication that login is taking longer than expected"""
        self.status_label.setText("Login is taking longer than expected...")
        self.status_label.setStyleSheet("color: #f39c12")  # Orange color for warning
    
    def update_ui_state(self, is_loading=False):
        """Update UI elements based on loading state"""
        login_button = self.findChild(QPushButton, "loginButton")
        if login_button:
            login_button.setEnabled(not is_loading)
            if is_loading:
                login_button.setText("Logging in...")
            else:
                login_button.setText("Log in")
