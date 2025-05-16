from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QProgressBar, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont, QColor

class SyncStatusWidget(QWidget):
    """Widget that displays synchronization status and controls for offline mode."""
    sync_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # Initialize counters
        self.pending_counts = {
            "logs": 0,
            "total": 0
        }
        
        # Set up refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update_requested)
        self.refresh_timer.start(30000)  # Update every 30 seconds
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Container frame with border
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(10)
        
        # Title
        title_label = QLabel("Synchronization Status")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(title_label)
        
        # Connection status
        status_layout = QHBoxLayout()
        status_label = QLabel("Backend Connection:")
        self.connection_indicator = QLabel()
        self.connection_indicator.setFixedSize(15, 15)
        self.connection_indicator.setStyleSheet("background-color: red; border-radius: 7px;")
        self.connection_status = QLabel("Disconnected")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.connection_indicator)
        status_layout.addWidget(self.connection_status)
        status_layout.addStretch()
        
        container_layout.addLayout(status_layout)
        
        # Sync info
        sync_info_layout = QVBoxLayout()
        
        # Pending items
        pending_label = QLabel("Pending Items:")
        pending_label.setStyleSheet("font-weight: bold;")
        sync_info_layout.addWidget(pending_label)
        
        # Display total pending items
        self.pending_items_label = QLabel("Pending Records: 0")
        self.pending_items_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        sync_info_layout.addWidget(self.pending_items_label)
        
        # Last sync time
        self.last_sync_label = QLabel("Last Sync: Never")
        sync_info_layout.addWidget(self.last_sync_label)
        
        container_layout.addLayout(sync_info_layout)
        
        # Sync progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        container_layout.addWidget(self.progress_bar)
        
        # Sync button
        self.sync_button = QPushButton("Sync Now")
        self.sync_button.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 8px;
            border: none;
            border-radius: 4px;
            font-weight: bold;
        """)
        self.sync_button.clicked.connect(self.request_sync)
        container_layout.addWidget(self.sync_button)
        
        layout.addWidget(container)
        
        # Set fixed width for the widget
        self.setFixedWidth(300)
    
    def set_connection_status(self, is_connected):
        """Update the connection status display."""
        if is_connected:
            self.connection_indicator.setStyleSheet("background-color: green; border-radius: 7px;")
            self.connection_status.setText("Connected")
            self.sync_button.setEnabled(True)
        else:
            self.connection_indicator.setStyleSheet("background-color: red; border-radius: 7px;")
            self.connection_status.setText("Disconnected")
            self.sync_button.setEnabled(False)
    
    def update_pending_counts(self, counts):
        """Update the pending counts display."""
        self.pending_counts = counts
        
        total_pending = counts.get("total", 0)
        self.pending_items_label.setText(f"Pending Records: {total_pending}")
        
        # Highlight if needed
        if total_pending > 0:
            self.pending_items_label.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
        else:
            self.pending_items_label.setStyleSheet("color: #2c3e50; font-size: 16px; font-weight: bold;")
    
    def set_last_sync_time(self, timestamp=None):
        """Update the last sync time display."""
        if timestamp:
            from datetime import datetime
            formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            self.last_sync_label.setText(f"Last Sync: {formatted_time}")
        else:
            self.last_sync_label.setText("Last Sync: Never")
    
    def set_sync_progress(self, entity_type, completed, total):
        """Update the sync progress display."""
        if total > 0:
            progress = int((completed / total) * 100)
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
            
            # Update button text
            self.sync_button.setText(f"Syncing... {progress}%")
            self.sync_button.setEnabled(False)
        else:
            self.progress_bar.setVisible(False)
    
    def sync_completed(self):
        """Reset the UI after sync completes."""
        self.progress_bar.setVisible(False)
        self.sync_button.setText("Sync Now")
        self.sync_button.setEnabled(True)
        
        # Update last sync time
        import time
        self.set_last_sync_time(time.time())
    
    def request_sync(self):
        """Emit the sync_requested signal when the button is clicked."""
        self.sync_requested.emit()
        self.sync_button.setText("Syncing...")
        self.sync_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
    
    def update_requested(self):
        """Signal that we need updated counts."""
        self.refresh_requested.emit()

# Connect a signal after defining it
SyncStatusWidget.refresh_requested = pyqtSignal() 