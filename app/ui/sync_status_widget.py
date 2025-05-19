from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLabel, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QMovie, QPixmap, QColor

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
        
        # Ensure icons are ready
        self.ensure_icons()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        # Loading spinner (using a colored circle for simplicity)
        self.loading_label = QLabel()
        self.loading_label.setFixedSize(16, 16)
        
        # Create a custom loading animation
        self.spinner_pixmap = QPixmap(16, 16)
        self.spinner_pixmap.fill(Qt.transparent)
        self.loading_label.setPixmap(self.spinner_pixmap)
        
        # Status message
        self.status_label = QLabel("Syncing...")
        self.status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        # Success/check icon (hidden by default)
        self.check_icon = QLabel()
        self.check_icon.setFixedSize(16, 16)
        
        # Add widgets to layout
        layout.addWidget(self.loading_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.check_icon)
        
        # Set fixed height but flexible width
        self.setFixedHeight(20)
        
        # Initially hide the check icon
        self.check_icon.setVisible(False)
        
        # Create the spinner timer for animation
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._update_spinner)
        self.spinner_angle = 0
    
    def _update_spinner(self):
        """Update the spinner animation - creates a simple rotating dot"""
        self.spinner_angle = (self.spinner_angle + 30) % 360
        
        # Create a new pixmap for the spinner
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        # Draw a blue dot in the position determined by the angle
        import math
        from PyQt5.QtGui import QPainter, QPen, QBrush
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw circle outline
        painter.setPen(QPen(QColor("#e4e8f0"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(1, 1, 14, 14)
        
        # Calculate position of the dot
        radius = 6
        center_x, center_y = 8, 8
        angle_rad = math.radians(self.spinner_angle)
        dot_x = center_x + radius * math.cos(angle_rad)
        dot_y = center_y + radius * math.sin(angle_rad)
        
        # Draw the dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#3498db")))
        painter.drawEllipse(int(dot_x - 3), int(dot_y - 3), 6, 6)
        
        painter.end()
        
        # Update the label
        self.loading_label.setPixmap(pixmap)
    
    def start_sync_animation(self):
        """Start the loading animation and show the widget"""
        self.loading_label.setVisible(True)
        self.check_icon.setVisible(False)
        self.status_label.setText("Syncing...")
        self.spinner_timer.start(100)  # Update every 100ms
        self.setVisible(True)
        
        # Cancel any pending hide timer
        if self.hide_timer.isActive():
            self.hide_timer.stop()
    
    def show_sync_complete(self, message):
        """Show completion message"""
        self.spinner_timer.stop()
        self.loading_label.setVisible(False)
        
        # Use the pre-generated check mark pixmap
        self.check_icon.setPixmap(self.check_pixmap)
        self.check_icon.setVisible(True)
        
        # Show completion message
        self.status_label.setText(message)
        
        # Start auto-hide timer
        self.hide_timer.start(5000)  # Hide after 5 seconds
    
    def show_sync_failed(self):
        """Show failure message"""
        self.spinner_timer.stop()
        self.loading_label.setVisible(False)
        
        # Use the pre-generated error mark pixmap
        self.check_icon.setPixmap(self.error_pixmap)
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
            if count is None or count == 0:
                # If no count is provided, or it's zero, just show "Synced" without a count
                self.show_sync_complete("Synced")
            else:
                # Show the count of synced logs
                self.show_sync_complete(f"Synced {count} logs")
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
        
    def __del__(self):
        # Clean up timers
        if hasattr(self, 'spinner_timer') and self.spinner_timer.isActive():
            self.spinner_timer.stop()
        if hasattr(self, 'hide_timer') and self.hide_timer.isActive():
            self.hide_timer.stop()

    def ensure_icons(self):
        """Ensure that all icons are available by drawing them if necessary"""
        # Create the initial spinner pixmap
        self.spinner_pixmap = QPixmap(16, 16)
        self.spinner_pixmap.fill(Qt.transparent)
        
        from PyQt5.QtGui import QPainter, QPen, QBrush
        
        # Draw initial spinner
        painter = QPainter(self.spinner_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw circle outline
        painter.setPen(QPen(QColor("#e4e8f0"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(1, 1, 14, 14)
        
        # Draw initial dot position
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#3498db")))
        painter.drawEllipse(8, 2, 6, 6)
        
        painter.end()
        self.loading_label.setPixmap(self.spinner_pixmap)
        
        # Create check pixmap
        self.check_pixmap = QPixmap(16, 16)
        self.check_pixmap.fill(Qt.transparent)
        
        painter = QPainter(self.check_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw green circle
        painter.setPen(QPen(QColor("#4CAF50"), 1))
        painter.setBrush(QBrush(QColor("#4CAF50")))
        painter.drawEllipse(1, 1, 14, 14)
        
        # Draw check mark
        painter.setPen(QPen(Qt.white, 2))
        painter.drawLine(4, 8, 7, 11)
        painter.drawLine(7, 11, 12, 5)
        
        painter.end()
        
        # Create error pixmap
        self.error_pixmap = QPixmap(16, 16)
        self.error_pixmap.fill(Qt.transparent)
        
        painter = QPainter(self.error_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw red circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#E74C3C")))
        painter.drawEllipse(1, 1, 14, 14)
        
        # Draw X mark
        painter.setPen(QPen(Qt.white, 2))
        painter.drawLine(5, 5, 11, 11)
        painter.drawLine(11, 5, 5, 11)
        
        painter.end() 