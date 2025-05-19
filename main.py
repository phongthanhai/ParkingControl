import sys
import os
import time
import sqlite3
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox, QLabel, QHBoxLayout, QVBoxLayout, QDialog, QTextEdit, QPushButton
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from app.ui.login_screen import LoginScreen
from app.ui.control_screen import ControlScreen
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage
from app.utils.error_manager import ErrorManager, ErrorResponse, ErrorSeverity
from app.controllers.sync_service import SyncService
from app.utils.connection_manager import ConnectionManager

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

class ErrorDialog(QDialog):
    """Dialog window for displaying error details"""
    
    def __init__(self, error_response, parent=None):
        super().__init__(parent)
        self.error = error_response
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        self.setWindowTitle(f"Error - {self.error.category.value}")
        self.setMinimumSize(500, 300)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Error message
        message_label = QLabel(self.error.message)
        message_label.setStyleSheet("font-weight: bold; color: red;")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        
        # Error details section
        if self.error.error or self.error.details:
            # Create details text
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            
            details_content = ""
            if self.error.error:
                details_content += f"Error: {str(self.error.error)}\n\n"
                
            if self.error.details:
                details_content += "Details:\n"
                for key, value in self.error.details.items():
                    details_content += f"- {key}: {value}\n"
            
            details_text.setPlainText(details_content)
            layout.addWidget(details_text)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)

class ParkingSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parking Control System")
        self.resize(1920, 1080)  # Set initial window size
        
        # Initialize error manager
        self.error_manager = ErrorManager()
        self.error_manager.error_occurred.connect(self.handle_error)
        
        # Initialize local storage before setting up UI
        if not initialize_local_storage():
            QMessageBox.critical(
                self,
                "Initialization Error",
                "Failed to initialize local storage. The application may not work correctly."
            )
        
        # Cleanup any existing corrupted logs (one-time fix)
        self.cleanup_unsynced_logs()
        
        # Status bar without database indicator
        self.statusBar().showMessage("")
        
        # Initialize connection manager
        self.connection_manager = ConnectionManager()
        
        # Initialize sync service with the connection manager
        self.sync_service = SyncService()
            
        self.setup_ui()
        
        # We'll still check the database connectivity, but not display it
        self.check_db_connection_silently()
        
        # Set up timer to periodically check database (silently)
        self.db_check_timer = QTimer(self)
        self.db_check_timer.timeout.connect(self.check_db_connection_silently)
        self.db_check_timer.start(30000)  # Check every 30 seconds

    def check_db_connection(self):
        """Check if the SQLite database is accessible - DEPRECATED (KEPT FOR COMPATIBILITY)"""
        return self.check_db_connection_silently()

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

    def handle_error(self, error_response):
        """
        Handle errors based on severity
        
        Args:
            error_response (ErrorResponse): The error that occurred
        """
        # Show in status bar for low severity errors
        if error_response.severity == ErrorSeverity.LOW:
            self.statusBar().showMessage(
                f"{error_response.category.value}: {error_response.message}", 
                5000  # Show for 5 seconds
            )
            
        # Show dialog for medium to critical errors
        elif error_response.severity.value >= ErrorSeverity.MEDIUM.value:
            # For critical errors, show immediately
            if error_response.severity == ErrorSeverity.CRITICAL:
                self.show_error_dialog(error_response)
            # For other errors, only show dialog if it's not a duplicate within the last minute
            else:
                # Get recent errors of the same category
                recent_errors = self.error_manager.get_recent_errors(
                    category=error_response.category,
                    limit=5
                )
                
                # Check if we've shown a similar error recently
                show_dialog = True
                if len(recent_errors) > 1:  # More than just this error
                    for err in recent_errors[:-1]:  # Exclude the current error
                        # Check if it's a similar message in the last minute
                        time_diff = (error_response.timestamp - err.timestamp).total_seconds()
                        if time_diff < 60 and err.message == error_response.message:
                            show_dialog = False
                            break
                
                if show_dialog:
                    self.show_error_dialog(error_response)
    
    def show_error_dialog(self, error_response):
        """Show an error dialog with details"""
        dialog = ErrorDialog(error_response, self)
        dialog.exec_()
    
    def show_control(self):
        if self.control_screen is None:
            self.control_screen = ControlScreen()
            
            # Connect sync service to control screen
            if hasattr(self.control_screen, 'sync_status_widget'):
                # Connect signals
                self.sync_service.api_status_changed.connect(
                    self.control_screen.sync_status_widget.set_connection_status)
                self.sync_service.sync_progress.connect(
                    self.control_screen.sync_status_widget.set_sync_progress)
                
                # Also connect connection manager message signal
                self.connection_manager.connection_state_message.connect(
                    self.control_screen.sync_status_widget.show_message)
                
                # Get current counts before connecting complete signal to avoid initial appearance
                pending_counts = self.sync_service.get_pending_sync_counts()
                self.control_screen.sync_status_widget.update_pending_counts(pending_counts)
                
                # Connect complete signal with the count of synced items
                self.sync_service.sync_all_complete.connect(
                    lambda count: self.control_screen.sync_status_widget.sync_completed(True, count))
                
                # Connect refresh request
                self.control_screen.sync_status_widget.refresh_requested.connect(
                    self.update_sync_counts)
                
                # Connect reconnect request to connection manager
                self.control_screen.sync_status_widget.reconnect_requested.connect(
                    self.handle_reconnect_request)
                
                # Connect log signal from control screen to handle log entries for sync
                print("Connecting control_screen.log_signal to sync_service")
                self.control_screen.log_signal.connect(self.handle_log_entry)
            
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
        
    def handle_log_entry(self, log_data):
        """Handle log entries sent from control screen for synchronization"""
        print(f"Received log entry for sync: {log_data.get('plate')} - {log_data.get('type')}")
        
        # Check if this log entry already indicates it was sent to API
        if log_data.get('already_synced', False):
            print(f"Skipping duplicate processing - log for {log_data.get('plate')} was already sent to API")
            return
        
        # Check if this entry has already been stored locally
        if log_data.get('stored_locally', False):
            print(f"Entry for {log_data.get('plate')} already stored in database, only updating sync service")
            # In this case, the control screen already stored it in the database,
            # so we just need to ensure the sync service knows about it 
            self.update_sync_counts()
            return
            
        # Store in local DB for sync later
        try:
            # Only store auto and manual entries (not blacklist or skipped)
            entry_type = log_data.get('type')
            if entry_type in ('auto', 'manual'):
                db_manager = DBManager()
                # Store in the database with a transaction to prevent duplication
                db_manager.add_log_entry(
                    lane=log_data.get('lane'),
                    plate_id=log_data.get('plate', 'N/A'),
                    confidence=log_data.get('confidence', 0.0), 
                    entry_type=entry_type,
                    image_path=log_data.get('image_path')
                )
                print(f"Stored log entry in local DB for sync: {log_data.get('plate')}")
                
                # Update sync counts in UI if available
                self.update_sync_counts()
        except Exception as e:
            print(f"Error handling log entry for sync: {str(e)}")
    
    def closeEvent(self, event):
        """Handle application close properly"""
        try:
            # Stop sync service
            if hasattr(self, 'sync_service'):
                self.sync_service.stop()
            
            # Stop connection manager 
            if hasattr(self, 'connection_manager'):
                self.connection_manager.stop()
            
            # Close database connection
            db_manager = DBManager()
            db_manager.close()
            
            # Clear blacklist logs if control screen exists
            if hasattr(self, 'control_screen') and self.control_screen:
                if hasattr(self.control_screen, 'local_blacklist_logs'):
                    self.control_screen.local_blacklist_logs = []
                    print("Cleared temporary blacklist logs on application close")
            
            # Stop timers
            if hasattr(self, 'db_check_timer'):
                self.db_check_timer.stop()
        except Exception as e:
            print(f"Error during application shutdown: {str(e)}")
        event.accept()

    def cleanup_unsynced_logs(self):
        """One-time cleanup of potentially corrupted unsynced logs"""
        try:
            db_manager = DBManager()
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            
            # Check if there are any unsynced logs
            cursor.execute("SELECT COUNT(*) FROM local_log WHERE synced = 0")
            unsynced_count = cursor.fetchone()[0]
            
            if unsynced_count > 0:
                print(f"Found {unsynced_count} potentially corrupted unsynced logs, cleaning up...")
                
                # Mark all existing unsynced logs as synced
                cursor.execute("UPDATE local_log SET synced = 1 WHERE synced = 0")
                conn.commit()
                
                print(f"Marked {unsynced_count} unsynced logs as synced")
                
                # Show confirmation in status bar briefly
                self.statusBar().showMessage(f"Fixed {unsynced_count} corrupted log entries", 5000)
            else:
                print("No unsynced logs found, no cleanup needed")
                
        except Exception as e:
            print(f"Error during log cleanup: {str(e)}")
            # Show error in status bar
            self.statusBar().showMessage(f"Error fixing corrupted logs: {str(e)}", 5000)

    def check_db_connection_silently(self):
        """Check if the SQLite database is accessible without displaying status"""
        try:
            db_manager = DBManager()
            # Try to execute a simple query
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            # Database is connected
            return True
        except (sqlite3.Error, Exception) as e:
            # Database connection failed
            print(f"Database error: {str(e)}")
            return False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParkingSystem()
    sys.exit(app.exec_())
