import sys
import os
import time
import sqlite3
import signal
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from app.ui.login_screen import LoginScreen
from app.ui.control_screen import ControlScreen
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage
from app.controllers.sync_service import SyncService

# Define signal handler for clean shutdown
def signal_handler(sig, frame):
    print(f"Received signal {sig}, initiating clean shutdown...")
    if 'window' in globals():
        window._force_close()
    else:
        print("Application window not initialized, forcing exit")
        os._exit(0)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

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
        
        # Status bar with database indicator
        self.statusBar().showMessage("")
        self.db_status_layout = QHBoxLayout()
        self.db_status_layout.setContentsMargins(5, 0, 5, 0)
        self.db_status_layout.setSpacing(5)
        
        self.db_indicator = QLabel()
        self.db_indicator.setFixedSize(12, 12)
        self.db_indicator.setStyleSheet("background-color: gray; border-radius: 6px;")
        self.db_status_text = QLabel("Database: Not checked")
        
        self.db_status_layout.addWidget(self.db_indicator)
        self.db_status_layout.addWidget(self.db_status_text)
        self.db_status_layout.addStretch()
        
        db_status_widget = QLabel()
        db_status_widget.setLayout(self.db_status_layout)
        self.statusBar().addPermanentWidget(db_status_widget)
        
        # Initialize sync service
        self.sync_service = SyncService()
            
        self.setup_ui()
        
        # Check database connectivity
        self.check_db_connection()
        
        # Set up timer to periodically check database
        self.db_check_timer = QTimer(self)
        self.db_check_timer.timeout.connect(self.check_db_connection)
        self.db_check_timer.start(30000)  # Check every 30 seconds

    def check_db_connection(self):
        """Check if the SQLite database is accessible"""
        try:
            db_manager = DBManager()
            # Try to execute a simple query
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            # Database is connected
            self.db_indicator.setStyleSheet("background-color: #a0d468; border-radius: 6px; border: 1px solid #8cc152;")
            self.db_status_text.setText("Database: Connected")
            self.db_status_text.setStyleSheet("color: #8cc152;")
            return True
        except (sqlite3.Error, Exception) as e:
            # Database connection failed
            self.db_indicator.setStyleSheet("background-color: #ed5565; border-radius: 6px; border: 1px solid #da4453;")
            self.db_status_text.setText("Database: Error")
            self.db_status_text.setStyleSheet("color: #ed5565;")
            print(f"Database error: {str(e)}")
            return False

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
                self.sync_service.sync_all_complete.connect(
                    lambda: self.control_screen.sync_status_widget.sync_completed(True))
                
                # Connect manual reconnect
                self.control_screen.sync_status_widget.reconnect_requested.connect(
                    self.handle_reconnect_request)
                
                # Connect sync button
                self.control_screen.sync_status_widget.sync_requested.connect(
                    lambda: self.sync_service.sync_now())
                
                # Connect refresh request
                self.control_screen.sync_status_widget.refresh_requested.connect(
                    self.update_sync_counts)
                
                # Initial status update
                self.control_screen.sync_status_widget.set_connection_status(
                    self.sync_service.api_available)
                self.update_sync_counts()
            
            self.stack.addWidget(self.control_screen)
        
        self.stack.setCurrentWidget(self.control_screen)
    
    def handle_reconnect_request(self):
        """Handle manual reconnection request from sync widget"""
        success = self.sync_service.reconnect()
        if hasattr(self.control_screen, 'sync_status_widget'):
            self.control_screen.sync_status_widget.reconnect_result(success)
    
    def update_sync_counts(self):
        """Update the sync counts in the UI"""
        if self.control_screen and hasattr(self.control_screen, 'sync_status_widget'):
            counts = self.sync_service.get_pending_sync_counts()
            self.control_screen.sync_status_widget.update_pending_counts(counts)
        
    def closeEvent(self, event):
        """Handle application close properly"""
        # Flag to prevent multiple close attempts
        if hasattr(self, '_closing') and self._closing:
            print("Already in closing process, accepting event...")
            event.accept()
            return
            
        self._closing = True
        print("Starting application shutdown sequence...")
        
        try:
            # If control screen exists, stop its threads first
            if self.control_screen:
                print("Stopping control screen...")
                self.control_screen.cleanup()
                
            # Stop sync service (this will handle its threads)
            if hasattr(self, 'sync_service'):
                print("Stopping sync service...")
                self.sync_service.stop()
                
            # Stop timers
            if hasattr(self, 'db_check_timer'):
                print("Stopping database check timer...")
                self.db_check_timer.stop()
            
            # Close database connection last
            print("Closing database connection...")
            db_manager = DBManager()
            db_manager.close()
            
            # Wait a brief moment for threads to clean up
            print("Starting final cleanup timer...")
            QTimer.singleShot(1000, self._force_close)
            event.ignore()  # Temporarily ignore the close event until everything is cleaned up
            
        except Exception as e:
            print(f"Error during application shutdown: {str(e)}")
            # Don't wait, just exit
            self._force_close()
    
    def _force_close(self):
        """Force close the application after cleanup"""
        print("Final cleanup complete, forcing application quit...")
        
        try:
            # Get any remaining threads before exit
            import threading
            active_threads = threading.enumerate()
            if len(active_threads) > 1:  # More than main thread
                print(f"WARNING: {len(active_threads)-1} threads still active at exit:")
                for thread in active_threads:
                    if thread != threading.current_thread():
                        print(f"  - {thread.name}")
            
            # Ensure PyQt exits properly
            import sys
            print("Calling QApplication.quit()...")
            QApplication.quit()
            print("Setting exit code to 0...")
            sys.exit(0)  # Force the Python interpreter to exit
        except Exception as e:
            print(f"Error during force close: {str(e)}")
            import os
            os._exit(0)  # Absolute last resort

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Create global window for signal handler
    global window
    window = ParkingSystem()
    
    # Proper exception handling to ensure clean exit
    try:
        exit_code = app.exec_()
        print(f"Application exited with code {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        print(f"Unhandled exception in main: {str(e)}")
        sys.exit(1)
