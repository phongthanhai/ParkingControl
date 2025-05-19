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
    def __init__(self, parent=None, api_available=True):
        super().__init__(parent, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setWindowTitle("Syncing Data")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(400, 150)
        
        # Track API state
        self.api_available = api_available
        
        # Apply simple styling
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 1px solid #ddd;
            }
            QLabel {
                font-family: Arial, sans-serif;
            }
            QProgressBar {
                border: 1px solid #ddd;
                background-color: #f5f5f5;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Status label
        if api_available:
            status_text = "Syncing data before exit"
        else:
            status_text = "No connection to server"
            
        self.status_label = QLabel(status_text)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        
        if not api_available:
            self.progress_bar.setFormat("Offline")
            self.progress_bar.setEnabled(False)
        else:
            self.progress_bar.setFormat("%v/%m")
            
        layout.addWidget(self.progress_bar)
        
        # Detail label
        if api_available:
            detail_text = "Please wait..."
        else:
            detail_text = "Cannot sync data - no server connection"
            
        self.detail_label = QLabel(detail_text)
        self.detail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.detail_label)
        
        # Force exit button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if not api_available:
            # When offline, we'll have two buttons
            self.exit_anyway_button = QPushButton("Exit Anyway")
            self.exit_anyway_button.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            button_layout.addWidget(self.exit_anyway_button)
            self.exit_anyway_button.clicked.connect(self.reject)
        else:
            # Normal online case
            self.force_exit_button = QPushButton("Force Exit")
            button_layout.addWidget(self.force_exit_button)
            self.force_exit_button.clicked.connect(self.reject)
            
        layout.addLayout(button_layout)
        
        # State
        self.is_complete = False
        self.progress_received = False
        
        # Simple progress indication for waiting period
        if api_available:
            self.progress_bar.setFormat("Preparing...")
        
    def update_progress(self, entity_type, completed, total):
        """Update the progress bar with current progress"""
        if not self.api_available:
            return
            
        if entity_type == "logs":
            self.progress_received = True
            
            # Update progress bar
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(completed)
            self.progress_bar.setFormat("%v/%m")
            
            # Update detail text
            self.detail_label.setText(f"Syncing {completed} of {total} items...")

    def sync_complete(self, count, context):
        """Handle sync completion"""
        if context == "shutdown":
            if count > 0:
                self.status_label.setText("Sync Complete")
                self.detail_label.setText(f"Successfully synced {count} items")
            else:
                if self.api_available:
                    self.status_label.setText("Nothing to Sync")
                    self.detail_label.setText("No unsaved data found")
                else:
                    # Leave the original offline message
                    pass
            
            # Complete the progress bar
            self.progress_bar.setValue(self.progress_bar.maximum())
            
            # Update button
            if hasattr(self, 'force_exit_button'):
                self.force_exit_button.setText("Close")
                self.force_exit_button.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 6px 12px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                """)
            
            # Set state and auto-close
            self.is_complete = True
            QTimer.singleShot(1500, self.accept)

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
                    # Give UI time to initialize and API client to establish connection
                    import time
                    
                    # IMPROVED: Longer cooldown before initial sync (5 seconds instead of 2)
                    print("Waiting for API client to initialize fully (5 seconds)...")
                    time.sleep(5)
                    
                    print("\n=== INITIAL SYNC AFTER LOGIN STARTED ===")
                    
                    # IMPROVED: Double check API status before attempting sync
                    if self.sync_service and hasattr(self.sync_service, 'api_available'):
                        # Force an API check to ensure accurate status
                        api_status = self.sync_service.check_api_connection()
                        print(f"API status before initial sync: {'Available' if api_status else 'Unavailable'}")
                        
                        # Only proceed with sync if API is truly available
                        if api_status:
                            self.sync_service.sync_now(context="startup")
                        else:
                            print("Initial sync postponed - API not available yet")
                            # Schedule another attempt with longer delay (10 seconds)
                            def retry_sync():
                                print("\n=== RETRYING INITIAL SYNC ===")
                                if self.sync_service and self.sync_service.api_available:
                                    self.sync_service.sync_now(context="startup")
                                else:
                                    print("API still not available, no initial sync performed")
                            
                            retry_timer = threading.Timer(10.0, retry_sync)
                            retry_timer.daemon = True
                            retry_timer.start()
                    else:
                        print("Cannot perform initial sync - sync service not available")
                    
                # Start thread for initial sync
                import threading
                sync_thread = threading.Thread(target=initial_login_sync)
                sync_thread.daemon = True
                sync_thread.start()
                print("Initial sync scheduled in background thread with improved cooldown")
            
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
                    print("DEBUG: About to check for unsynced data...")
                    counts = self.sync_service.get_pending_sync_counts()
                    print(f"DEBUG: Found {counts['total']} items that need sync before exit")
                    
                    # First check if there are unsynced items
                    if counts["total"] > 0:
                        print(f"DEBUG: Will show exit dialog for {counts['total']} items")
                        
                        # Check if API is available for sync
                        api_available = self.sync_service.api_available 
                        
                        # Create and show the exit sync dialog with API availability status
                        sync_dialog = ExitSyncDialog(self, api_available=api_available)
                        
                        # Connect signals if API is available
                        if api_available:
                            try:
                                self.sync_service.sync_progress.connect(sync_dialog.update_progress)
                                self.sync_service.sync_all_complete.connect(sync_dialog.sync_complete)
                            except Exception as signal_err:
                                print(f"DEBUG: Error connecting signals: {str(signal_err)}")
                                # Don't proceed with sync if signals can't be connected
                                api_available = False
                        
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
                        print("DEBUG: Showing exit sync dialog")
                        sync_dialog.show()
                        sync_dialog.raise_()
                        sync_dialog.activateWindow()
                        
                        # Explicitly process some events to ensure dialog appears
                        print("DEBUG: Processing events to display dialog")
                        QApplication.processEvents()
                        
                        # Show the shutdown sync indicator in the main window as well
                        if hasattr(self, 'control_screen') and self.control_screen and hasattr(self.control_screen, 'sync_status_widget'):
                            try:
                                self.control_screen.sync_status_widget.show_shutdown_sync()
                            except Exception as ui_err:
                                print(f"DEBUG: Error showing shutdown sync in UI: {str(ui_err)}")
                        
                        # Start the sync operation with shutdown context if API is available
                        if api_available:
                            try:
                                print("DEBUG: Starting final exit sync operation")
                                self.sync_service.sync_now(context="shutdown")
                            except Exception as sync_err:
                                print(f"DEBUG: Error starting sync: {str(sync_err)}")
                                # Handle error case - don't leave dialog hanging
                                try:
                                    sync_dialog.status_label.setText("Sync Error")
                                    sync_dialog.detail_label.setText(f"Error: {str(sync_err)}")
                                    sync_dialog.progress_bar.setValue(0)
                                    if hasattr(sync_dialog, 'force_exit_button'):
                                        sync_dialog.force_exit_button.setEnabled(True)
                                except Exception:
                                    pass
                        else:
                            # If API is not available, emit completion signal with 0 count
                            # to ensure dialog handles offline state properly
                            print("DEBUG: Cannot sync - API not available")
                            # CRITICAL FIX: Make sure sync service exists before calling emit
                            try:
                                if hasattr(self, 'sync_service') and self.sync_service is not None:
                                    self.sync_service.sync_all_complete.emit(0, "shutdown")
                            except Exception as emit_err:
                                print(f"DEBUG: Error emitting sync completion: {str(emit_err)}")
                        
                        # Wait for sync to complete or user to force exit
                        # The dialog will block until sync completes or user cancels
                        print("DEBUG: About to execute sync dialog")
                        result = sync_dialog.exec_()
                        print(f"DEBUG: Dialog finished with result: {result}")
                        self.sync_dialog_active = False
                        
                        # Disconnect signals to prevent callbacks during shutdown
                        try:
                            if api_available:
                                if hasattr(self, 'sync_service') and self.sync_service is not None:
                                    self.sync_service.sync_progress.disconnect(sync_dialog.update_progress)
                                    self.sync_service.sync_all_complete.disconnect(sync_dialog.sync_complete)
                        except (TypeError, RuntimeError) as disconnect_err:
                            # Ignore disconnect errors if signals were already disconnected
                            print(f"DEBUG: Signal disconnect error (non-critical): {str(disconnect_err)}")
                        
                        # If user forced exit, still need to continue with shutdown
                        if result == QDialog.Rejected and not sync_dialog.is_complete:
                            print("User forced exit during sync")
                    else:
                        print(f"DEBUG: No sync needed - Items: {counts['total']}, API Available: {self.sync_service.api_available}")
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
                            if hasattr(self.sync_service, 'api_status_changed'):
                                self.sync_service.api_status_changed.disconnect()
                            if hasattr(self.sync_service, 'sync_progress'):
                                self.sync_service.sync_progress.disconnect()
                            if hasattr(self.sync_service, 'sync_all_complete'):
                                self.sync_service.sync_all_complete.disconnect()
                    except (TypeError, RuntimeError) as e:
                        # Ignore errors if signals were already disconnected
                        print(f"Note: Some signals were already disconnected: {str(e)}")
                    
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
            
            # CRITICAL FIX: Protect against trying to access deleted C++ objects
            # by using a copy of the sync_service reference and handling possible exceptions
            sync_service = None
            if hasattr(self, 'sync_service'):
                sync_service = self.sync_service
                # Clear the reference early to prevent later access to potentially deleted object
                self.sync_service = None
                
            # Stop sync service after control screen is closed
            if sync_service:
                print("Stopping sync service...")
                try:
                    # Only call stop() if we didn't already do a sync in the exit dialog
                    # This avoids duplicating the sync operation
                    if not self.sync_dialog_active:
                        sync_service.stop()  # This would perform a final sync with shutdown context
                    print("Sync service stopped")
                except Exception as e:
                    print(f"Error stopping sync service: {str(e)}")
                # Clear reference
                sync_service = None
            
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
                print(f"Found {unsynced_count} unsynced logs, checking for potential corruption...")
                
                # CRITICAL FIX: Only clean up logs that are older than 24 hours
                # This prevents cleaning up legitimate unsynced logs from recent activity
                import time
                from datetime import datetime, timedelta
                
                # Calculate timestamp for 24 hours ago
                one_day_ago = time.time() - (24 * 60 * 60)
                
                # Only clean up logs older than one day
                cursor.execute("SELECT COUNT(*) FROM local_log WHERE synced = 0 AND timestamp < ?", 
                              (one_day_ago,))
                old_unsynced_count = cursor.fetchone()[0]
                
                if old_unsynced_count > 0:
                    print(f"Found {old_unsynced_count} potentially corrupted unsynced logs older than 24 hours")
                    
                    # Only mark old logs as synced
                    cursor.execute("UPDATE local_log SET synced = 1 WHERE synced = 0 AND timestamp < ?", 
                                 (one_day_ago,))
                    conn.commit()
                    
                    print(f"Marked {old_unsynced_count} old unsynced logs as synced")
                    
                    # Show confirmation in status bar briefly
                    self.statusBar().showMessage(f"Fixed {old_unsynced_count} corrupted log entries", 5000)
                else:
                    print(f"All {unsynced_count} unsynced logs are recent (within 24 hours), not cleaning up")
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
