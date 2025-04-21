from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                            QPushButton, QLabel, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal

class LoginScreen(QWidget):
    login_success = pyqtSignal()
    login_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_styles()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(50, 20, 50, 20)
        main_layout.setSpacing(20)

        # Title
        title = QLabel("Parking Control System")
        title.setAlignment(Qt.AlignCenter)

        # Form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)
        
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignCenter)

        # Buttons
        button_layout = QHBoxLayout()
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.attempt_login)
        button_layout.addStretch()
        button_layout.addWidget(login_btn)
        button_layout.addStretch()

        # Assemble form
        form_layout.addWidget(title)
        form_layout.addItem(QSpacerItem(20, 40))
        form_layout.addWidget(self.username)
        form_layout.addWidget(self.password)
        form_layout.addItem(QSpacerItem(20, 20))
        form_layout.addLayout(button_layout)
        form_layout.addWidget(self.status_label)

        # Main layout
        main_layout.addStretch()
        main_layout.addLayout(form_layout)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def setup_styles(self):
        self.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #333;
            }
            QLineEdit {
                font-size: 16px;
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                padding: 10px 25px;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        title = self.findChild(QLabel)
        if title:
            title.setStyleSheet("""
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 30px;
            """)

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
            self.status_label.setStyleSheet("color: #dc3545;")