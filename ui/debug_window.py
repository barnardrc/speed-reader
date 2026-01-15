import cv2
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class CameraDebugWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle("Camera Debug")
        self.resize(320, 240)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000;")
        self.layout.addWidget(self.video_label)

    def update_frame(self, cv_frame, avg_ratio, limit_ratio, eyes_off):
        """
        Draws the Gaze Meter sidebar and status text.
        """
        if cv_frame is None: return

        h, w = cv_frame.shape[:2]

        # 2. Draw Gaze Meter (Vertical Bar on Right Side)
        bar_width = 20
        bar_height = int(h * 0.6)
        bar_top = int(h * 0.2)
        bar_x = w - bar_width - 10
        
        # Background
        cv2.rectangle(cv_frame, (bar_x, bar_top), (bar_x + bar_width, bar_top + bar_height), (100, 100, 100), -1)

        # Draw Limit Line (Red)
        if limit_ratio is not None:
            limit_y = int(bar_top + (limit_ratio * bar_height))
            cv2.line(cv_frame, (bar_x - 10, limit_y), (bar_x + 30, limit_y), (0, 0, 255), 2)
            cv2.putText(cv_frame, "Limit", (bar_x - 45, limit_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Draw Current Eye Position (Yellow Dot)
        if avg_ratio is not None:
            # Clamp ratio 0.0-1.0
            safe_ratio = max(0.0, min(1.0, avg_ratio))
            current_y = int(bar_top + (safe_ratio * bar_height))
            
            color = (0, 255, 255) # Yellow
            if eyes_off: color = (0, 0, 255) # Red if looking away
            
            cv2.circle(cv_frame, (bar_x + 10, current_y), 6, color, -1)

        # 3. Status Text
        status_text = "Looking Down"
        text_color = (0, 255, 0) # Green
        
        if eyes_off:
            status_text = "EYES OFF"
            text_color = (0, 0, 255) # Red
        elif limit_ratio is None:
            status_text = "UNCALIBRATED"
            text_color = (255, 255, 255) # White

        cv2.putText(cv_frame, status_text, (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

        # 4. Convert to Qt
        rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), 
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.video_label.setPixmap(pixmap)