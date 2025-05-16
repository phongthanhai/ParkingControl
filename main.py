import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from app.ui.login_screen import LoginScreen
from app.ui.control_screen import ControlScreen
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage
from app.controllers.sync_service import SyncService

# Initialize database folder
def initialize_local_storage():
    """Create necessary folders for local storage"""
    try:
        # Create DB directory if it doesn't exist
        db_path = os.path.join(os.path.dirname(__file__), 'local_data.db')
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir) and db_dir:
            os.makedirs(db_dir)
            
        # Initialize image storage
        image_storage = ImageStorage()
        
        # Initialize database
        db_manager = DBManager()
        
        # Clean up old images
        image_storage.cleanup_old_images()
        
        return True
    except Exception as e:
        print(f"Error initializing local storage: {str(e)}")
        return False

class ParkingSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parking Control System")
        self.resize(1920, 1080)  # Set initial window size
        
        # Initialize local storage before setting up UI
        if not initialize_local_storage():
            QMessageBox.critical(
                self,
                "Initialization Error",
                "Failed to initialize local storage. The application may not work correctly."
            )
        
        # Initialize sync service
        self.sync_service = SyncService()
            
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
            
            # Connect sync service to control screen if it has a sync widget
            if hasattr(self.control_screen, 'sync_status_widget'):
                # Connect signals
                self.sync_service.api_status_changed.connect(
                    self.control_screen.sync_status_widget.set_connection_status)
                self.sync_service.sync_progress.connect(
                    self.control_screen.sync_status_widget.set_sync_progress)
                self.control_screen.sync_status_widget.sync_requested.connect(
                    lambda: self.sync_service.sync_now())
                self.control_screen.sync_status_widget.refresh_requested.connect(
                    self.update_sync_counts)
                
                # Initial status update
                self.control_screen.sync_status_widget.set_connection_status(
                    self.sync_service.api_available)
                self.update_sync_counts()
            
            self.stack.addWidget(self.control_screen)
        
        self.stack.setCurrentWidget(self.control_screen)
    
    def update_sync_counts(self):
        """Update the sync counts in the UI"""
        if self.control_screen and hasattr(self.control_screen, 'sync_status_widget'):
            counts = self.sync_service.get_pending_sync_counts()
            self.control_screen.sync_status_widget.update_pending_counts(counts)
        
    def closeEvent(self, event):
        """Handle application close properly"""
        try:
            # Stop sync service
            if hasattr(self, 'sync_service'):
                self.sync_service.stop()
            
            # Close database connection
            db_manager = DBManager()
            db_manager.close()
        except Exception as e:
            print(f"Error during application shutdown: {str(e)}")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParkingSystem()
    sys.exit(app.exec_())
