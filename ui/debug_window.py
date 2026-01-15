# -*- coding: utf-8 -*-
"""
Created on Thu Jan 15 00:52:02 2026

@author: barna
"""

import cv2
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class CameraDebugWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool) # Tool window floats on top
        self.setWindowTitle("Camera Debug")
        self.resize(320, 240)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000;")
        self.layout.addWidget(self.video_label)

    def update_frame(self, cv_frame, avg_y, baseline_y, threshold):
        """
        Converts OpenCV BGR frame to QPixmap and displays it.
        Also draws the threshold line for visual verification.
        """
        if cv_frame is None: return

        # Draw the Threshold Line (Blue)
        if baseline_y is not None:
            limit = int(baseline_y - threshold)
            cv2.line(cv_frame, (0, limit), (cv_frame.shape[1], limit), (255, 0, 0), 1)
            cv2.putText(cv_frame, "Limit", (5, limit - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

        # Draw Current Gaze Y (Yellow line)
        if avg_y is not None:
             cv2.line(cv_frame, (0, int(avg_y)), (cv_frame.shape[1], int(avg_y)), (0, 255, 255), 1)

        # Convert BGR -> RGB
        rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale to fit window
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), 
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.video_label.setPixmap(pixmap)