import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from app.ui.login_screen import LoginScreen
from app.ui.control_screen import ControlScreen

class ParkingSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parking Control System")
        self.resize(1920, 1080)  # Set initial window size
        self.setup_ui()

    def setup_ui(self):
        self.stack = QStackedWidget()
        
        # Login Screen
        self.login_screen = LoginScreen()
        self.login_screen.login_success.connect(self.show_control)
        self.stack.addWidget(self.login_screen)
        
        # Control Screen (created on demand)
        self.control_screen = None
        
        self.setCentralWidget(self.stack)
        self.show()

    def show_control(self):
        if self.control_screen is None:
            self.control_screen = ControlScreen()
            self.stack.addWidget(self.control_screen)
        self.stack.setCurrentWidget(self.control_screen)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParkingSystem()
    sys.exit(app.exec_())
