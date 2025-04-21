from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QFrame, QSizePolicy)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer
from app.controllers.lane_controller import LaneWorker
import cv2

class ControlScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.lane_workers = {
            'entry': LaneWorker('entry'),
            'exit': LaneWorker('exit')
        }
        self.setup_ui()
        self.setup_camera_connections()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Camera Views
        camera_layout = QHBoxLayout()
        self.entry_view = self.create_lane_view("ENTRY LANE")
        self.exit_view = self.create_lane_view("EXIT LANE")
        
        camera_layout.addLayout(self.entry_view)
        camera_layout.addWidget(self.create_separator())
        camera_layout.addLayout(self.exit_view)
        main_layout.addLayout(camera_layout)
        
        self.setLayout(main_layout)

    def create_lane_view(self, title):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 18px;
            color: #2c3e50;
            padding-bottom: 5px;
            border-bottom: 2px solid #3498db;
        """)
        
        # Image Display
        image_label = QLabel()
        image_label.setFixedSize(500, 300)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("""
            border: 2px solid #95a5a6;
            background: #ecf0f1;
        """)
        
        # Plate Text
        plate_label = QLabel("Scanning...")
        plate_label.setAlignment(Qt.AlignCenter)
        plate_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 500;
            color: #2c3e50;
            padding: 8px;
            background: #f5f6fa;
            border-radius: 4px;
        """)
        
        layout.addWidget(title_label)
        layout.addWidget(image_label)
        layout.addWidget(plate_label)
        return layout

    def create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background: #ced4da;")
        separator.setFixedHeight(300)
        return separator

    def setup_camera_connections(self):
        for lane, worker in self.lane_workers.items():
            worker.detection_signal.connect(self.update_lane_view)
            worker.start()

    def update_lane_view(self, lane, frame, plate_text):
        """Convert OpenCV frame to QPixmap and update UI"""
        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
        else:
            # Fallback if no frame
            pixmap = QPixmap(500, 300)
            pixmap.fill(Qt.white)
        
        if lane == 'entry':
            self.entry_view.itemAt(1).widget().setPixmap(pixmap)
            self.entry_view.itemAt(2).widget().setText(plate_text)
        else:
            self.exit_view.itemAt(1).widget().setPixmap(pixmap)
            self.exit_view.itemAt(2).widget().setText(plate_text)

    def closeEvent(self, event):
        for worker in self.lane_workers.values():
            worker.stop()
        super().closeEvent(event)