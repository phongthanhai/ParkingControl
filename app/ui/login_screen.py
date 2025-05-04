from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                            QPushButton, QLabel, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPalette, QBrush

class LoginScreen(QWidget):
    login_success = pyqtSignal()
    login_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_styles()

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
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setProperty("class", "loginInput")
        
        # Login button
        login_btn = QPushButton("Log in")
        login_btn.setObjectName("loginButton")
        login_btn.clicked.connect(self.attempt_login)
        
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
        # Replace with actual API call
        username = self.username.text()
        password = self.password.text()
        
        # Mock authentication
        if username == "admin" and password == "password":
            self.login_success.emit()
        else:
            self.login_failed.emit("Invalid credentials")
            self.status_label.setText("Invalid username or password")
