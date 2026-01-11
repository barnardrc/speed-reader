# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 20:42:08 2026

@author: barna
"""

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath

class TutorialOverlay(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent, steps):
        super().__init__(parent)
        self.parent_widget = parent
        self.steps = steps
        self.current_step = 0
        
        # Overlay settings
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.resize(parent.size())
        
        # Message Box UI
        self.msg_container = QFrame(self)
        self.msg_container.setFixedSize(400, 200)
        self.msg_container.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 2px solid #4a90e2;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                border: none;
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.lbl_title = QLabel("Tutorial")
        self.lbl_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)
        
        self.lbl_msg = QLabel()
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setFont(QFont("Arial", 11))
        self.lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_msg)
        
        # Button Layout
        btn_layout = QHBoxLayout()
        
        self.btn_skip = QPushButton("Skip")
        self.btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_skip.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaa;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #444; color: white; }
        """)
        self.btn_skip.clicked.connect(self.close_tutorial)
        btn_layout.addWidget(self.btn_skip)

        self.btn_next = QPushButton("Next")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #357abd; }
        """)
        self.btn_next.clicked.connect(self.next_step)
        btn_layout.addWidget(self.btn_next)
        
        layout.addLayout(btn_layout)
        self.msg_container.setLayout(layout)
        
        self.center_msg_box()
        self.update_content()
        self.show()
        self.setFocus()

    def center_msg_box(self):
        center_x = (self.width() - self.msg_container.width()) // 2
        center_y = (self.height() - self.msg_container.height()) // 2
        self.msg_container.move(center_x, center_y)

    def update_content(self):
        if self.current_step < len(self.steps):
            _, msg = self.steps[self.current_step]
            step_num = self.current_step + 1
            total = len(self.steps)
            self.lbl_title.setText(f"Tutorial {step_num}/{total}")
            self.lbl_msg.setText(msg)
            if self.current_step == len(self.steps) - 1:
                self.btn_next.setText("Finish")
            else:
                self.btn_next.setText("Next")
            self.update() 

    def next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.close_tutorial()
        else:
            self.update_content()

    def close_tutorial(self):
        self.close()
        self.finished.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        
        target_rect = None

        if self.current_step < len(self.steps):
            target_widget, _ = self.steps[self.current_step]
            if target_widget and target_widget.isVisible():
                global_pos = target_widget.mapToGlobal(QPoint(0, 0))
                local_pos = self.mapFromGlobal(global_pos)
                
                # Fix: Create integer QRect first, then convert to QRectF
                rect_int = QRect(local_pos, target_widget.size())
                target_rect = QRectF(rect_int)

                cutout = QPainterPath()
                cutout.addRoundedRect(target_rect, 5, 5)
                path = path.subtracted(cutout)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
        painter.drawPath(path)

        if target_rect:
            painter.setPen(QPen(QColor("#4a90e2"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(target_rect, 5, 5)

    def resizeEvent(self, event):
        if self.parent_widget:
            self.resize(self.parent_widget.size())
        self.center_msg_box()
        super().resizeEvent(event)