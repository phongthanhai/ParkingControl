from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QProgressBar, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont, QColor, QMovie

class SyncStatusWidget(QWidget):
    """Widget that displays synchronization status and controls for offline mode."""
    refresh_requested = pyqtSignal()  # Define the signal inside the class
    reconnect_requested = pyqtSignal()  # Signal for manual reconnection
    
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
        
        # Completion timer for success message
        self.completion_timer = QTimer(self)
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self.hide_completion_message)
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Container frame with border and gradient background
        container = QFrame()
        container.setFrameShape(QFrame.StyledPanel)
        container.setStyleSheet("""
            QFrame {
                border: 1px solid #ccd1d9;
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #f5f7fa, stop:1 #e4e8f0);
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.setSpacing(12)
        
        # Title with icon
        title_layout = QHBoxLayout()
        title_label = QLabel("Synchronization Status")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        title_layout.addStretch(1)
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        container_layout.addLayout(title_layout)
        
        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #ccd1d9;")
        container_layout.addWidget(line)
        
        # Connection status with indicator
        status_layout = QHBoxLayout()
        status_label = QLabel("Backend API:")
        status_label.setStyleSheet("font-weight: bold; color: #656d78;")
        
        self.connection_indicator = QLabel()
        self.connection_indicator.setFixedSize(16, 16)
        self.connection_indicator.setStyleSheet("""
            background-color: #ed5565; 
            border-radius: 8px;
            border: 1px solid #da4453;
        """)
        
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: #ed5565; font-weight: bold;")
        
        # Reconnect button (initially hidden)
        self.reconnect_button = QPushButton("Reconnect")
        self.reconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #4a89dc;
                color: white;
                padding: 4px 8px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5d9cec;
            }
            QPushButton:pressed {
                background-color: #3b7dd8;
            }
        """)
        self.reconnect_button.setVisible(False)
        self.reconnect_button.clicked.connect(self.request_reconnect)
        
        # Add sync status indicator next to connection status
        self.sync_spinner_label = QLabel()
        try:
            self.spinner_movie = QMovie("app/resources/loading_spinner.gif")
            self.spinner_movie.setScaledSize(QSize(16, 16))
            self.sync_spinner_label.setMovie(self.spinner_movie)
        except Exception as e:
            print(f"Failed to load spinner GIF: {str(e)}")
            # Fallback to a colored indicator
            self.sync_spinner_label.setFixedSize(16, 16)
            self.sync_spinner_label.setStyleSheet("background-color: #3bafda; border-radius: 8px;")
        self.sync_spinner_label.setVisible(False)
        
        self.sync_status_indicator = QLabel()
        self.sync_status_indicator.setFixedSize(16, 16)
        self.sync_status_indicator.setStyleSheet("""
            background-color: #a0d468; 
            border-radius: 8px;
            border: 1px solid #8cc152;
        """)
        self.sync_status_indicator.setVisible(False)
        
        self.sync_status_text = QLabel("Syncing...")
        self.sync_status_text.setStyleSheet("color: #3bafda; font-weight: bold;")
        self.sync_status_text.setVisible(False)
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.connection_indicator)
        status_layout.addWidget(self.connection_status)
        status_layout.addWidget(self.reconnect_button)
        
        status_layout.addSpacing(10)
        status_layout.addWidget(self.sync_spinner_label)
        status_layout.addWidget(self.sync_status_indicator)
        status_layout.addWidget(self.sync_status_text)
        status_layout.addStretch()
        
        container_layout.addLayout(status_layout)
        
        # Sync info with improved layout
        self.pending_items_label = QLabel("Pending Items: 0")
        self.pending_items_label.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold;
            color: #656d78;
            padding: 8px;
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 4px;
        """)
        self.pending_items_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.pending_items_label)
        
        # Last sync time
        self.last_sync_label = QLabel("Last Sync: Never")
        self.last_sync_label.setStyleSheet("color: #656d78; font-style: italic;")
        self.last_sync_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.last_sync_label)
        
        # Sync progress with completion status
        progress_layout = QVBoxLayout()
        
        self.sync_status_label = QLabel("")
        self.sync_status_label.setStyleSheet("""
            color: #3bafda;
            font-weight: bold;
            font-size: 14px;
        """)
        self.sync_status_label.setAlignment(Qt.AlignCenter)
        self.sync_status_label.setVisible(False)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccd1d9;
                border-radius: 4px;
                background-color: #f5f7fa;
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4fc1e9;
                border-radius: 3px;
            }
        """)
        
        progress_layout.addWidget(self.sync_status_label)
        progress_layout.addWidget(self.progress_bar)
        container_layout.addLayout(progress_layout)
        
        # Completion message (success/failure)
        self.completion_frame = QFrame()
        self.completion_frame.setStyleSheet("""
            background-color: #a0d468;
            border-radius: 4px;
            padding: 4px;
        """)
        self.completion_frame.setVisible(False)
        
        completion_layout = QHBoxLayout(self.completion_frame)
        completion_layout.setContentsMargins(8, 4, 8, 4)
        
        self.completion_label = QLabel("Sync completed successfully!")
        self.completion_label.setStyleSheet("color: white; font-weight: bold;")
        completion_layout.addWidget(self.completion_label)
        
        container_layout.addWidget(self.completion_frame)
        
        layout.addWidget(container)
        
        # Set fixed width for the widget
        self.setFixedWidth(320)
    
    def set_connection_status(self, is_connected):
        """Update the connection status display."""
        if is_connected:
            self.connection_indicator.setStyleSheet("""
                background-color: #a0d468; 
                border-radius: 8px;
                border: 1px solid #8cc152;
            """)
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: #8cc152; font-weight: bold;")
            self.reconnect_button.setVisible(False)
            
            # Hide sync indicators when connected
            self.hide_sync_indicators()
        else:
            self.connection_indicator.setStyleSheet("""
                background-color: #ed5565; 
                border-radius: 8px;
                border: 1px solid #da4453;
            """)
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: #ed5565; font-weight: bold;")
            self.reconnect_button.setVisible(True)
            
            # Hide sync indicators when disconnected
            self.hide_sync_indicators()
    
    def update_pending_counts(self, counts):
        """Update the pending counts display."""
        self.pending_counts = counts
        
        total_pending = counts.get("total", 0)
        self.pending_items_label.setText(f"Pending Records: {total_pending}")
        
        # Highlight if needed
        if total_pending > 0:
            self.pending_items_label.setStyleSheet("""
                font-size: 16px; 
                font-weight: bold;
                color: #ed5565;
                padding: 8px;
                background-color: rgba(255, 255, 255, 0.7);
                border-radius: 4px;
            """)
        else:
            self.pending_items_label.setStyleSheet("""
                font-size: 16px; 
                font-weight: bold;
                color: #656d78;
                padding: 8px;
                background-color: rgba(255, 255, 255, 0.7);
                border-radius: 4px;
            """)
    
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
            # Show spinner and status text
            if not self.sync_spinner_label.isVisible():
                self.sync_spinner_label.setVisible(True)
                try:
                    if hasattr(self, 'spinner_movie'):
                        self.spinner_movie.start()
                except Exception as e:
                    print(f"Failed to start spinner animation: {str(e)}")
            
            self.sync_status_text.setText("Syncing...")
            self.sync_status_text.setVisible(True)
            self.sync_status_indicator.setVisible(False)
            
            # Update progress bar
            progress = int((completed / total) * 100)
            self.progress_bar.setValue(progress)
            self.progress_bar.setVisible(True)
            
            # Clear completion frame
            self.completion_frame.setVisible(False)
        else:
            self.hide_sync_indicators()
    
    def sync_completed(self, success=True):
        """Reset the UI after sync completes."""
        # Hide progress indicators
        self.progress_bar.setVisible(False)
        self.sync_status_label.setVisible(False)
        
        # Stop loading spinner
        try:
            if hasattr(self, 'spinner_movie') and self.spinner_movie.state() == QMovie.Running:
                self.spinner_movie.stop()
        except Exception as e:
            print(f"Failed to stop spinner animation: {str(e)}")
        self.sync_spinner_label.setVisible(False)
        
        # Show completion message
        if success:
            # Get the count of synced records
            synced_count = self.pending_counts.get("total", 0)
            self.sync_status_text.setText(f"Synced {synced_count} logs")
            self.sync_status_text.setVisible(True)
            self.sync_status_indicator.setVisible(True)
            
            self.completion_frame.setStyleSheet("""
                background-color: #a0d468;
                border-radius: 4px;
                padding: 4px;
            """)
            self.completion_label.setText(f"Synced {synced_count} logs")
        else:
            self.sync_status_text.setText("Sync failed")
            self.sync_status_text.setStyleSheet("color: #ed5565; font-weight: bold;")
            self.sync_status_text.setVisible(True)
            self.sync_status_indicator.setVisible(False)
            
            self.completion_frame.setStyleSheet("""
                background-color: #ed5565;
                border-radius: 4px;
                padding: 4px;
            """)
            self.completion_label.setText("Sync completed with errors")
        
        self.completion_frame.setVisible(True)
        
        # Auto-hide completion message after 5 seconds
        self.completion_timer.start(5000)
        
        # Update last sync time
        import time
        self.set_last_sync_time(time.time())
        
        # Emit refresh request to update pending counts
        print("Sync completed, requesting refresh of pending counts")
        self.refresh_requested.emit()
    
    def hide_completion_message(self):
        """Hide the completion message."""
        self.completion_frame.setVisible(False)
    
    def hide_sync_indicators(self):
        """Hide all sync-related indicators."""
        try:
            if hasattr(self, 'spinner_movie') and self.spinner_movie.state() == QMovie.Running:
                self.spinner_movie.stop()
        except Exception as e:
            print(f"Failed to stop spinner animation: {str(e)}")
        self.sync_spinner_label.setVisible(False)
        self.sync_status_text.setVisible(False)
        self.sync_status_indicator.setVisible(False)
        self.progress_bar.setVisible(False)
        
        # Reset styles
        self.sync_status_text.setStyleSheet("color: #3bafda; font-weight: bold;")
    
    def request_reconnect(self):
        """Emit the reconnect_requested signal when the button is clicked."""
        self.reconnect_requested.emit()
        self.reconnect_button.setEnabled(False)
        self.reconnect_button.setText("Reconnecting...")
    
    def reconnect_result(self, success):
        """Handle the result of a reconnection attempt."""
        self.reconnect_button.setEnabled(True)
        self.reconnect_button.setText("Reconnect")
        
        if not success:
            # Show temporary error message
            self.sync_status_text.setText("Reconnect failed")
            self.sync_status_text.setStyleSheet("color: #ed5565; font-weight: bold;")
            self.sync_status_text.setVisible(True)
            
            # Auto-hide after 3 seconds
            QTimer.singleShot(3000, self.hide_sync_indicators)
    
    def update_requested(self):
        """Emit the refresh_requested signal."""
        self.refresh_requested.emit() 