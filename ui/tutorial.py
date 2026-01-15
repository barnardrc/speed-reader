# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 20:42:08 2026

@author: barna
"""

from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QFrame, 
                             QHBoxLayout, QGridLayout)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath

class TutorialOverlay(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent, steps):
        super().__init__(parent)
        self.parent_widget = parent
        self.steps = steps
        self.current_step = 0
        
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        # Note: We do not call self.resize() here; main.py sets geometry
        
        # Main Message Container
        self.msg_container = QFrame(self)
        self.msg_container.setMinimumWidth(420)
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
        
        self.main_layout = QVBoxLayout(self.msg_container)
        
        self.lbl_title = QLabel("Tutorial")
        self.lbl_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.lbl_title)
        
        # Standard Text Message
        self.lbl_msg = QLabel()
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setFont(QFont("Arial", 11))
        self.lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.lbl_msg)

        # Graphical Area (Hotkeys)
        self.graphic_area = QWidget()
        self.graphic_layout = QVBoxLayout(self.graphic_area)
        self.graphic_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.graphic_area)
        self.graphic_area.hide()
        
        # Navigation Buttons
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
        
        self.main_layout.addLayout(btn_layout)
        
        self.update_content()
        self.show()
        self.setFocus()

    def create_key_widget(self, key_text, desc_text):
        """Helper to create a visual key representation"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        key_lbl = QLabel(key_text)
        key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_lbl.setFixedSize(50, 40)
        key_lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        
        key_lbl.setStyleSheet("""
            background-color: #444;
            border: 1px solid #888;
            border-bottom: 3px solid #666;
            border-radius: 6px;
            color: white;
        """)
        
        if key_text == "SPACE":
            key_lbl.setFixedWidth(160) 

        desc_lbl = QLabel(desc_text)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setFont(QFont("Arial", 8))
        desc_lbl.setStyleSheet("color: #bbb; border: none;")

        layout.addWidget(key_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_lbl)
        return container

    def build_hotkey_layout(self):
        """Builds the graphical keyboard layout"""
        if self.graphic_area.layout():
            QWidget().setLayout(self.graphic_area.layout())
            self.graphic_layout = QVBoxLayout(self.graphic_area)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(self.create_key_widget("↑", "WPM +"), 0, 1)
        grid.addWidget(self.create_key_widget("←", "-10 Words"), 1, 0)
        grid.addWidget(self.create_key_widget("↓", "WPM -"), 1, 1)
        grid.addWidget(self.create_key_widget("→", "+10 Words"), 1, 2)
        space_container = self.create_key_widget("SPACE", "Play / Pause")
        grid.addWidget(space_container, 2, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        self.graphic_layout.addLayout(grid)

    def center_msg_box(self):
        """Centers message, but jumps out of the way of highlighted widgets"""
        self.msg_container.adjustSize()
        
        # Default Center
        center_x = (self.width() - self.msg_container.width()) // 2
        center_y = (self.height() - self.msg_container.height()) // 2
        
        # Smart Positioning: Check for overlap with current target
        if self.current_step < len(self.steps):
            target_widget, _ = self.steps[self.current_step]
            if target_widget and target_widget.isVisible():
                global_pos = target_widget.mapToGlobal(QPoint(0, 0))
                local_pos = self.mapFromGlobal(global_pos)
                target_rect = QRect(local_pos, target_widget.size())
                
                msg_rect = QRect(center_x, center_y, self.msg_container.width(), self.msg_container.height())
                
                if msg_rect.intersects(target_rect):
                    # Overlap detected. Move box to top or bottom depending on target Y
                    if target_rect.center().y() > self.height() // 2:
                        center_y = 50 # Move to top
                    else:
                        center_y = self.height() - self.msg_container.height() - 50 # Move to bottom
                        
        self.msg_container.move(center_x, center_y)

    def update_content(self):
        if self.current_step < len(self.steps):
            _, msg = self.steps[self.current_step]
            step_num = self.current_step + 1
            total = len(self.steps)
            self.lbl_title.setText(f"Tutorial {step_num}/{total}")
            
            if msg == "HOTKEYS":
                self.lbl_msg.hide()
                self.build_hotkey_layout()
                self.graphic_area.show()
            else:
                self.graphic_area.hide()
                self.lbl_msg.setText(msg)
                self.lbl_msg.show()

            if self.current_step == len(self.steps) - 1:
                self.btn_next.setText("Finish")
            else:
                self.btn_next.setText("Next")
            
            self.center_msg_box()
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
        # FIX: Do NOT call self.resize(parent.size()) here. 
        # The parent (main.py) manages our geometry via its own resizeEvent.
        self.center_msg_box()
        super().resizeEvent(event)