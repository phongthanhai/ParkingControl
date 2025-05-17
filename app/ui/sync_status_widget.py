from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLabel, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QMovie, QPixmap

class SyncStatusWidget(QWidget):
    """Compact widget that displays synchronization status using icons"""
    sync_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    reconnect_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # Initialize counters
        self.pending_counts = {
            "logs": 0,
            "total": 0
        }
        
        # Auto hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_widget)
        
        # Hide widget initially
        self.setVisible(False)
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        # Loading spinner
        self.loading_label = QLabel()
        self.loading_label.setFixedSize(16, 16)
        self.movie = QMovie("app/resources/loading.gif")
        self.movie.setScaledSize(QSize(16, 16))
        self.loading_label.setMovie(self.movie)
        
        # Status message
        self.status_label = QLabel("Syncing...")
        self.status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        # Success/check icon (hidden by default)
        self.check_icon = QLabel()
        self.check_icon.setFixedSize(16, 16)
        # Will load this pixmap when needed
        
        # Add widgets to layout
        layout.addWidget(self.loading_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.check_icon)
        
        # Set fixed height but flexible width
        self.setFixedHeight(20)
        
        # Initially hide the check icon
        self.check_icon.setVisible(False)
    
    def start_sync_animation(self):
        """Start the loading animation and show the widget"""
        self.loading_label.setVisible(True)
        self.check_icon.setVisible(False)
        self.status_label.setText("Syncing...")
        self.movie.start()
        self.setVisible(True)
        
        # Cancel any pending hide timer
        if self.hide_timer.isActive():
            self.hide_timer.stop()
    
    def show_sync_complete(self, count):
        """Show completion message with count of synced items"""
        self.movie.stop()
        self.loading_label.setVisible(False)
        
        # Load and show the check icon
        check_pixmap = QPixmap("app/resources/check.png")
        if not check_pixmap.isNull():
            scaled_pixmap = check_pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.check_icon.setPixmap(scaled_pixmap)
            self.check_icon.setVisible(True)
        
        # Show completion message
        self.status_label.setText(f"Synced {count} logs")
        
        # Start auto-hide timer
        self.hide_timer.start(5000)  # Hide after 5 seconds
    
    def show_sync_failed(self):
        """Show failure message"""
        self.movie.stop()
        self.loading_label.setVisible(False)
        
        # Load and show an error icon (X mark)
        error_pixmap = QPixmap("app/resources/error.png")
        if not error_pixmap.isNull():
            scaled_pixmap = error_pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.check_icon.setPixmap(scaled_pixmap)
            self.check_icon.setVisible(True)
        
        # Show error message
        self.status_label.setText("Sync failed")
        
        # Start auto-hide timer
        self.hide_timer.start(5000)  # Hide after 5 seconds
    
    def set_connection_status(self, is_connected):
        """Called when API connection status changes"""
        # This method remains for compatibility but doesn't do anything visible
        pass
    
    def set_sync_progress(self, entity_type, completed, total):
        """Update progress display during sync"""
        if total > 0:
            self.status_label.setText(f"Syncing {completed}/{total}...")
            self.start_sync_animation()
    
    def sync_completed(self, success=True, count=None):
        """Show completion status"""
        if success:
            if count is None:
                count = self.pending_counts.get("total", 0)
            self.show_sync_complete(count)
        else:
            self.show_sync_failed()
        
        # Emit refresh request to update pending counts
        self.refresh_requested.emit()
    
    def update_pending_counts(self, counts):
        """Update the pending counts (not displayed but tracked)"""
        self.pending_counts = counts
    
    def hide_widget(self):
        """Hide the widget after a delay"""
        self.setVisible(False)
    
    # These methods are kept for compatibility with existing code
    def reconnect_result(self, success):
        pass
    
    def request_sync(self):
        self.sync_requested.emit()
        self.start_sync_animation() 