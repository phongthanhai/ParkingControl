import sys
import os
import time
import sqlite3
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from app.ui.login_screen import LoginScreen
from app.ui.control_screen import ControlScreen
from app.utils.db_manager import DBManager
from app.utils.image_storage import ImageStorage
from app.controllers.sync_service import SyncService

def initialize_local_storage():
    try:
        db_path = os.path.join(os.path.dirname(__file__), 'local_data.db')
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir) and db_dir:
            os.makedirs(db_dir)
            
        image_storage = ImageStorage()
        db_manager = DBManager()
        image_storage.cleanup_old_images()
        
        return True
    except Exception as e:
        return False

class ParkingSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parking Control System")
        self.resize(1920, 1080)
        
        if not initialize_local_storage():
            QMessageBox.critical(
                self,
                "Initialization Error",
                "Failed to initialize local storage. The application may not work correctly."
            )
        
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
        
        self.sync_service = SyncService()
            
        self.setup_ui()
        
        self.check_db_connection()
        
        self.db_check_timer = QTimer(self)
        self.db_check_timer.timeout.connect(self.check_db_connection)
        self.db_check_timer.start(30000)

    def check_db_connection(self):
        try:
            db_manager = DBManager()
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            self.db_indicator.setStyleSheet("background-color: #a0d468; border-radius: 6px; border: 1px solid #8cc152;")
            self.db_status_text.setText("Database: Connected")
            self.db_status_text.setStyleSheet("color: #8cc152;")
            return True
        except (sqlite3.Error, Exception) as e:
            self.db_indicator.setStyleSheet("background-color: #ed5565; border-radius: 6px; border: 1px solid #da4453;")
            self.db_status_text.setText("Database: Error")
            self.db_status_text.setStyleSheet("color: #ed5565;")
            return False

    def setup_ui(self):
        self.stack = QStackedWidget()
        
        self.login_screen = LoginScreen()
        self.login_screen.login_success.connect(self.show_control)
        self.stack.addWidget(self.login_screen)
        
        self.control_screen = None
        
        self.setCentralWidget(self.stack)
        self.show()

    def show_control(self):
        if self.control_screen is None:
            self.control_screen = ControlScreen()
            
            if hasattr(self.control_screen, 'sync_status_widget'):
                self.sync_service.api_status_changed.connect(
                    self.control_screen.sync_status_widget.set_connection_status)
                self.sync_service.sync_progress.connect(
                    self.control_screen.sync_status_widget.set_sync_progress)
                self.sync_service.sync_all_complete.connect(
                    lambda: self.control_screen.sync_status_widget.sync_completed(True))
                
                self.control_screen.sync_status_widget.reconnect_requested.connect(
                    self.handle_reconnect_request)
                
                self.control_screen.sync_status_widget.sync_requested.connect(
                    lambda: self.sync_service.sync_now())
                
                self.control_screen.sync_status_widget.refresh_requested.connect(
                    self.update_sync_counts)
                
                self.control_screen.log_signal.connect(self.handle_log_entry)
                
                self.control_screen.sync_status_widget.set_connection_status(
                    self.sync_service.api_available)
                self.update_sync_counts()
            
            self.stack.addWidget(self.control_screen)
        
        self.stack.setCurrentWidget(self.control_screen)
    
    def handle_reconnect_request(self):
        success = self.sync_service.reconnect()
        if hasattr(self.control_screen, 'sync_status_widget'):
            self.control_screen.sync_status_widget.reconnect_result(success)
    
    def update_sync_counts(self):
        if self.control_screen and hasattr(self.control_screen, 'sync_status_widget'):
            counts = self.sync_service.get_pending_sync_counts()
            self.control_screen.sync_status_widget.update_pending_counts(counts)
        
    def handle_log_entry(self, log_data):
        if log_data.get('already_synced', False):
            return
        
        if log_data.get('stored_locally', False):
            self.update_sync_counts()
            return
            
        try:
            entry_type = log_data.get('type')
            if entry_type in ('auto', 'manual'):
                db_manager = DBManager()
                db_manager.add_log_entry(
                    lane=log_data.get('lane'),
                    plate_id=log_data.get('plate', 'N/A'),
                    confidence=log_data.get('confidence', 0.0), 
                    entry_type=entry_type,
                    image_path=log_data.get('image_path')
                )
                
                self.update_sync_counts()
        except Exception as e:
            pass
    
    def closeEvent(self, event):
        try:
            if hasattr(self, 'sync_service'):
                self.sync_service.stop()
            
            db_manager = DBManager()
            db_manager.close()
            
            if hasattr(self, 'control_screen') and self.control_screen:
                if hasattr(self.control_screen, 'local_blacklist_logs'):
                    self.control_screen.local_blacklist_logs = []
            
            if hasattr(self, 'db_check_timer'):
                self.db_check_timer.stop()
        except Exception as e:
            pass
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParkingSystem()
    sys.exit(app.exec_())
