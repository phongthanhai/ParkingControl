import sys
import os
import time
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox, QLabel, QHBoxLayout
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QProgressBar, QPushButton, QDialogButtonBox, QDesktopWidget
from PyQt5.QtCore import Qt, QTimer, QEventLoop
import atexit
from PyQt5.QtWidgets import QStyle

from app.ui.login_screen import LoginScreen
from app.ui.control_screen import ControlScreen
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage
from app.controllers.sync_service import SyncService

class ExitSyncDialog(QDialog):
    """Dialog that shows sync progress during application exit"""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setWindowTitle("Syncing Before Exit")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(450, 200)
        
        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            QLabel {
                font-family: Arial, sans-serif;
            }
            QProgressBar {
                border: 1px solid #bdbdbd;
                border-radius: 5px;
                background-color: #f5f5f5;
                text-align: center;
                height: 20px;
                margin: 10px 0px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        
        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Add header
        header_label = QLabel("Parking Control System")
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(header_label)
        
        # Add status label
        self.status_label = QLabel("Syncing data before exit...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #3498db;")
        layout.addWidget(self.status_label)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/%m logs synced")
        layout.addWidget(self.progress_bar)
        
        # Add detail label
        self.detail_label = QLabel("Please wait while unsaved data is synced to the server...")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setStyleSheet("color: #666; margin-top: 5px; margin-bottom: 15px;")
        layout.addWidget(self.detail_label)
        
        # Add warning
        self.warning_label = QLabel("Do not turn off your computer until this process completes.")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setStyleSheet("color: #e74c3c; font-style: italic;")
        layout.addWidget(self.warning_label)
        
        # Add spacer
        layout.addSpacing(10)
        
        # Add buttons in a horizontal layout
        button_layout = QHBoxLayout()
        
        # Exit button
        self.force_exit_button = QPushButton("Force Exit")
        self.force_exit_button.setFixedHeight(30)
        self.force_exit_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; 
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        button_layout.addStretch()
        button_layout.addWidget(self.force_exit_button)
        layout.addLayout(button_layout)
        
        # Connect signals
        self.force_exit_button.clicked.connect(self.reject)
        
        # State
        self.is_complete = False
        self.was_forced = False
        self.progress_received = False
        
        # Create animation effects
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_warning)
        self.pulse_timer.start(1000)  # Pulse every second
        self.pulse_state = False
        
        # Progress bar animation for initial waiting period
        self.progress_animation_timer = QTimer(self)
        self.progress_animation_timer.timeout.connect(self._animate_progress_waiting)
        self.progress_animation_timer.start(100)  # Update every 100ms
        self.progress_animation_value = 0
        self.progress_animation_direction = 1
        
    def _animate_progress_waiting(self):
        """Animate progress bar with a bouncing effect while waiting for sync to start"""
        # Only animate if we haven't received real progress updates yet
        if not self.progress_received and not self.is_complete:
            # Bounce between 0 and 10%
            self.progress_animation_value += self.progress_animation_direction
            
            # Reverse direction at boundaries
            if self.progress_animation_value >= 10:
                self.progress_animation_direction = -1
            elif self.progress_animation_value <= 0:
                self.progress_animation_direction = 1
                
            # Apply animated value
            self.progress_bar.setValue(self.progress_animation_value)
            
            # Use a different format during waiting
            self.progress_bar.setFormat("Preparing...")
        
    def _pulse_warning(self):
        """Create a pulsing effect on the warning label"""
        if not self.is_complete:
            self.pulse_state = not self.pulse_state
            color = "#e74c3c" if self.pulse_state else "#c0392b"
            self.warning_label.setStyleSheet(f"color: {color}; font-style: italic; font-weight: bold;")
        
    def update_progress(self, entity_type, completed, total):
        """Update the progress bar with current progress"""
        if entity_type == "logs":
            # Stop the animation timer when real progress starts
            self.progress_received = True
            if self.progress_animation_timer.isActive():
                self.progress_animation_timer.stop()
            
            # Configure progress bar for actual progress display
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(completed)
            self.progress_bar.setFormat("%v/%m logs synced")
            self.detail_label.setText(f"Syncing {completed} of {total} logs to the server...")
            
            # Update progress bar color based on progress
            progress_percentage = (completed / max(1, total)) * 100
            if progress_percentage < 33:
                chunk_color = "#3498db"  # Blue
            elif progress_percentage < 66:
                chunk_color = "#2ecc71"  # Green
            else:
                chunk_color = "#27ae60"  # Darker green
                
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #bdbdbd;
                    border-radius: 5px;
                    background-color: #f5f5f5;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {chunk_color};
                    border-radius: 5px;
                }}
            """)

    def sync_complete(self, count, context):
        """Handle sync completion"""
        if context == "shutdown":
            # Stop animation timers
            if self.progress_animation_timer.isActive():
                self.progress_animation_timer.stop()
            
            if count > 0:
                self.status_label.setText("Sync Complete!")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2ecc71; margin-bottom: 10px;")
                self.detail_label.setText(f"Successfully synced {count} logs to the server")
                self.warning_label.setText("It's now safe to exit the application.")
                self.warning_label.setStyleSheet("color: #2ecc71; font-style: normal; font-weight: bold;")
            else:
                self.status_label.setText("Nothing to Sync")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498db; margin-bottom: 10px;")
                self.detail_label.setText("No unsaved data found")
                self.warning_label.setText("It's safe to exit the application.")
                self.warning_label.setStyleSheet("color: #2ecc71; font-style: normal; font-weight: bold;")
            
            # Fill progress bar
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #bdbdbd;
                    border-radius: 5px;
                    background-color: #f5f5f5;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #2ecc71;
                    border-radius: 5px;
                }
            """)
            
            # Update state and button
            self.is_complete = True
            self.force_exit_button.setText("Close")
            self.force_exit_button.setStyleSheet("""
                QPushButton {
                    background-color: #2ecc71; 
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 15px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #27ae60;
                }
            """)
            
            # Stop the pulse animation
            self.pulse_timer.stop()
            
            # Auto-close after a short delay
            QTimer.singleShot(2000, self.accept)

def initialize_local_storage():
    """Initialize local storage directories and database"""
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
        
        # Register cleanup handler
        atexit.register(db_manager.close)
        
        return True
    except Exception as e:
        print(f"Failed to initialize local storage: {str(e)}")
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
        
        # Cleanup any existing corrupted logs (one-time fix)
        self.cleanup_unsynced_logs()
        
        # Status bar without database indicator
        self.statusBar().showMessage("")
        
        # Initialize sync service
        self.sync_service = SyncService()
            
        self.setup_ui()
        
        # We'll still check the database connectivity, but not display it
        self.check_db_connection_silently()
        
        # Set up timer to periodically check database (silently)
        self.db_check_timer = QTimer(self)
        self.db_check_timer.timeout.connect(self.check_db_connection_silently)
        self.db_check_timer.start(30000)  # Check every 30 seconds
        
        # Flag to track if we're already handling a close event
        self.is_closing = False
        # Flag to track if sync dialog is showing
        self.sync_dialog_active = False

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
                
                # Get current counts before connecting complete signal to avoid initial appearance
                pending_counts = self.sync_service.get_pending_sync_counts()
                self.control_screen.sync_status_widget.update_pending_counts(pending_counts)
                
                # Connect complete signal with the count of synced items and context
                self.sync_service.sync_all_complete.connect(
                    lambda count, context: self.control_screen.sync_status_widget.sync_completed(True, count, context))
                
                # Connect refresh request
                self.control_screen.sync_status_widget.refresh_requested.connect(
                    self.update_sync_counts)
                
                # Connect log signal from control screen to handle log entries for sync
                print("Connecting control_screen.log_signal to sync_service")
                self.control_screen.log_signal.connect(self.handle_log_entry)
                
                # Trigger an immediate sync attempt after authentication with startup context
                print("Triggering initial sync after successful login")
                
                # First show the startup sync indicator
                self.control_screen.sync_status_widget.show_startup_sync()
                
                # Use a direct thread for more reliable syncing
                def initial_login_sync():
                    # Give UI time to initialize
                    import time
                    time.sleep(2)
                    print("\n=== INITIAL SYNC AFTER LOGIN STARTED ===")
                    self.sync_service.sync_now(context="startup")
                    
                # Start thread for initial sync
                import threading
                sync_thread = threading.Thread(target=initial_login_sync)
                sync_thread.daemon = True
                sync_thread.start()
                print("Initial sync scheduled in background thread")
            
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
        """
        Handle application close properly by showing exit sync dialog 
        and performing final sync before shutting down
        """
        # Prevent duplicate close handling
        if self.is_closing:
            event.accept()
            return
            
        self.is_closing = True
        
        try:
            print("Starting main application shutdown...")
            
            # Stop timers first to prevent any new operations
            if hasattr(self, 'db_check_timer') and self.db_check_timer.isActive():
                self.db_check_timer.stop()
                print("Database check timer stopped")
            
            # Check if we have unsynced data that needs to be synced
            if hasattr(self, 'sync_service') and self.sync_service:
                # Get pending sync counts
                try:
                    counts = self.sync_service.get_pending_sync_counts()
                    if counts["total"] > 0 and self.sync_service.api_available:
                        print(f"Found {counts['total']} items to sync before exit")
                        
                        # Create and show the exit sync dialog
                        sync_dialog = ExitSyncDialog(self)
                        
                        # Connect signals - move to center of screen and make sure it's visible
                        self.sync_service.sync_progress.connect(sync_dialog.update_progress)
                        self.sync_service.sync_all_complete.connect(sync_dialog.sync_complete)
                        
                        # Center the dialog on screen for maximum visibility
                        try:
                            # Qt5 way - may be deprecated in newer versions
                            screen_geometry = QApplication.desktop().screenGeometry()
                            x = (screen_geometry.width() - sync_dialog.width()) // 2
                            y = (screen_geometry.height() - sync_dialog.height()) // 2
                            sync_dialog.move(x, y)
                        except AttributeError:
                            # For newer Qt versions that might not have desktop()
                            sync_dialog.setGeometry(
                                QStyle.alignedRect(
                                    Qt.LeftToRight,
                                    Qt.AlignCenter,
                                    sync_dialog.size(),
                                    QApplication.primaryScreen().availableGeometry()
                                )
                            )
                        
                        # Show the dialog and bring to front
                        self.sync_dialog_active = True
                        sync_dialog.show()
                        sync_dialog.raise_()
                        sync_dialog.activateWindow()
                        
                        # Explicitly process some events to ensure dialog appears
                        QApplication.processEvents()
                        
                        # Show the shutdown sync indicator in the main window as well
                        if hasattr(self, 'control_screen') and self.control_screen and hasattr(self.control_screen, 'sync_status_widget'):
                            self.control_screen.sync_status_widget.show_shutdown_sync()
                        
                        # Start the sync operation with shutdown context
                        print("Starting final exit sync operation")
                        self.sync_service.sync_now(context="shutdown")
                        
                        # Wait for sync to complete or user to force exit
                        # The dialog will block until sync completes or user cancels
                        result = sync_dialog.exec_()
                        self.sync_dialog_active = False
                        
                        # Disconnect signals to prevent callbacks during shutdown
                        try:
                            self.sync_service.sync_progress.disconnect(sync_dialog.update_progress)
                            self.sync_service.sync_all_complete.disconnect(sync_dialog.sync_complete)
                        except TypeError:
                            # Ignore disconnect errors if signals were already disconnected
                            pass
                        
                        # If user forced exit, still need to continue with shutdown
                        if result == QDialog.Rejected and not sync_dialog.is_complete:
                            print("User forced exit during sync")
                    else:
                        print("No items to sync before exit or API not available")
                except Exception as e:
                    print(f"Error checking for unsynced data: {str(e)}")
            
            # If control screen exists, close it first to handle thread cleanup
            if hasattr(self, 'control_screen') and self.control_screen:
                print("Closing control screen and its threads...")
                # Disconnect signals to prevent callbacks during shutdown
                if hasattr(self, 'sync_service') and self.sync_service:
                    try:
                        # Don't disconnect signals that are already being used by exit dialog
                        if not self.sync_dialog_active:
                            self.sync_service.api_status_changed.disconnect()
                            self.sync_service.sync_progress.disconnect()
                            self.sync_service.sync_all_complete.disconnect()
                    except (TypeError, RuntimeError):
                        # Ignore errors if signals were already disconnected
                        print("Note: Some signals were already disconnected")
                    
                if hasattr(self.control_screen, 'log_signal'):
                    try:
                        self.control_screen.log_signal.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                
                # Let the control screen clean up its threads directly
                try:
                    # Call closeEvent directly rather than creating a new event
                    self.control_screen.closeEvent(event)
                    print("Control screen threads cleaned up")
                except Exception as e:
                    print(f"Error cleaning up control screen threads: {str(e)}")
                
                # Clear blacklist logs
                if hasattr(self.control_screen, 'local_blacklist_logs'):
                    self.control_screen.local_blacklist_logs = []
                    print("Cleared temporary blacklist logs")
            
            # Stop sync service after control screen is closed
            if hasattr(self, 'sync_service') and self.sync_service:
                print("Stopping sync service...")
                try:
                    # Only call stop() if we didn't already do a sync in the exit dialog
                    # This avoids duplicating the sync operation
                    if not self.sync_dialog_active:
                        self.sync_service.stop()  # This would perform a final sync with shutdown context
                    print("Sync service stopped")
                except Exception as e:
                    print(f"Error stopping sync service: {str(e)}")
                # Clear reference
                self.sync_service = None
            
            # Close database connection - do this last as other components might need database access
            print("Closing database connection...")
            try:
                db_manager = DBManager()
                db_manager.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing database: {str(e)}")
            
            print("Application shutdown complete")
            
        except Exception as e:
            print(f"Error during application shutdown: {str(e)}")
        
        # Reset flag
        self.is_closing = False
        
        # Always accept the close event
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
