# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 08:13:09 2026

@author: barna
"""
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QWidget, QProgressBar, QPushButton, QListWidget,
    QFrame, QDialog
)
from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen, QLinearGradient
from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, pyqtSignal, QEvent
from utils.text_utils import is_header

class ContextFlowWidget(QWidget):
    scrolled = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []
        self.index = 0
        self.ctx_range = 20
        self.opacity = 50
        self.s_start = 0
        self.s_end = 0
        
        self.font_ctx = QFont("Georgia", 20)
        self.metrics = QFontMetrics(self.font_ctx)
    
    def set_data(self, words, index, ctx_range, opacity, s_start, s_end):
        self.words = words
        self.index = index
        self.ctx_range = ctx_range
        self.opacity = opacity
        self.s_start = s_start
        self.s_end = s_end
        self.update() 
    
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0: return

        step = -1 if delta > 0 else 1
        
        self.scrolled.emit(step)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font_ctx)

        w_height = self.height()
        w_width = self.width()
        
        border_padding = 20
        border_rect = QRectF(
            border_padding, 
            10, 
            w_width - (border_padding * 2), 
            w_height - 20
        )

        grad_border = QLinearGradient(0, 0, 0, w_height)
        c_trans = QColor(150, 150, 150, 0)
        c_vis = QColor(150, 150, 150, 100)

        grad_border.setColorAt(0.0, c_trans)
        grad_border.setColorAt(0.2, c_trans)
        grad_border.setColorAt(0.5, c_vis)
        grad_border.setColorAt(0.8, c_trans)
        grad_border.setColorAt(1.0, c_trans)

        border_pen = QPen(Qt.PenStyle.SolidLine)
        border_pen.setBrush(grad_border)
        border_pen.setWidth(2)
        border_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, 15, 15)
        center_y = w_height / 2
        line_height = self.metrics.height() + 10
        separator_y = center_y + (line_height * 3.5) + 5 

        grad_sep = QLinearGradient(0, 0, w_width, 0)
        grad_sep.setColorAt(0.0, c_trans)
        grad_sep.setColorAt(0.3, c_trans)
        grad_sep.setColorAt(0.5, QColor(150, 150, 150, 80))
        grad_sep.setColorAt(0.7, c_trans)
        grad_sep.setColorAt(1.0, c_trans)

        sep_pen = QPen()
        sep_pen.setBrush(grad_sep)
        sep_pen.setWidth(1)
        
        painter.setPen(sep_pen)
        painter.drawLine(
            QPointF(border_padding + 10, separator_y), 
            QPointF(w_width - border_padding - 10, separator_y)
        )

        if not self.words: return

        base_alpha_val = int(255 * (self.opacity / 100.0))
        hl_color = QColor("#ffd700")
        
        margin_x = 40
        space_width = self.metrics.horizontalAdvance(" ")
        center_x = w_width / 2
        screen_fade_zone = w_height * 0.15 
        left_bound = margin_x
        right_bound = w_width - margin_x

        def get_combined_alpha(rect_y_center, current_step, max_steps):
            screen_factor = 1.0
            if rect_y_center < screen_fade_zone:
                screen_factor = max(0.0, rect_y_center / screen_fade_zone)
            elif rect_y_center > (w_height - screen_fade_zone):
                dist = w_height - rect_y_center
                screen_factor = max(0.0, dist / screen_fade_zone)
            screen_factor = screen_factor * screen_factor 

            index_factor = 1.0
            fade_start_step = max_steps * 0.7 
            if current_step > fade_start_step:
                progress = (current_step - fade_start_step) / (max_steps - fade_start_step)
                index_factor = max(0.0, 1.0 - progress)
            
            final_factor = min(screen_factor, index_factor)
            return int(base_alpha_val * final_factor)

        active_word = self.words[self.index]
        painter.save() 
        f = painter.font()
        f.setBold(True)
        painter.setFont(f)
        bold_metrics = painter.fontMetrics()
        aw_width = bold_metrics.horizontalAdvance(active_word)
        
        aw_rect = QRectF(
            center_x - (aw_width / 2),
            center_y - (line_height / 2),
            aw_width,
            line_height
        )

        if self.s_start <= self.index <= self.s_end:
             painter.fillRect(aw_rect, QColor(255, 255, 255, 30))

        painter.setPen(hl_color)
        text_y = aw_rect.top() + ((aw_rect.height() - bold_metrics.height()) / 2) + bold_metrics.ascent()
        painter.drawText(QPointF(aw_rect.left(), text_y), active_word)
        painter.restore() 

        cursor_x = aw_rect.right() + space_width
        cursor_y = aw_rect.top()
        actual_end_idx = min(len(self.words), self.index + self.ctx_range)
        steps_total = actual_end_idx - (self.index + 1)

        for step, i in enumerate(range(self.index + 1, actual_end_idx)):
            word = self.words[i]
            w = self.metrics.horizontalAdvance(word)
            if cursor_x + w > right_bound:
                cursor_x = left_bound
                cursor_y += line_height
            if cursor_y > w_height: break
            
            rect = QRectF(cursor_x, cursor_y, w, line_height)
            alpha = get_combined_alpha(rect.center().y(), step, steps_total)
            if alpha > 5: 
                painter.setPen(QColor(255, 255, 255, alpha))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, word)
                if self.s_start <= i <= self.s_end:
                    bg_alpha = int(30 * (alpha / 255.0))
                    painter.fillRect(rect, QColor(255, 255, 255, bg_alpha))
            cursor_x += w + space_width

        cursor_x = aw_rect.left() - space_width
        cursor_y = aw_rect.top()
        actual_start_idx = max(-1, self.index - self.ctx_range)
        steps_total = (self.index - 1) - actual_start_idx

        for step, i in enumerate(range(self.index - 1, actual_start_idx, -1)):
            word = self.words[i]
            w = self.metrics.horizontalAdvance(word)
            if cursor_x - w < left_bound:
                cursor_x = right_bound
                cursor_y -= line_height
            if cursor_y + line_height < 0: break
            
            rect = QRectF(cursor_x - w, cursor_y, w, line_height)
            alpha = get_combined_alpha(rect.center().y(), step, steps_total)
            if alpha > 5:
                painter.setPen(QColor(255, 255, 255, alpha))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, word)
                if self.s_start <= i <= self.s_end:
                    bg_alpha = int(30 * (alpha / 255.0))
                    painter.fillRect(rect, QColor(255, 255, 255, bg_alpha))
            cursor_x -= (w + space_width)
            
class RSVPWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = "Ready"
        self.prev_text = ""
        self.next_text = ""
        self.flank_opacity = 60
        self.is_active = False
        
        self.font = QFont("Consolas", 48, QFont.Weight.Bold)
        self.metrics = QFontMetrics(self.font)
        self.setMinimumHeight(150)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_word(self, word, prev_word="", next_word=""):
        self.text = word
        self.prev_text = prev_word
        self.next_text = next_word
        self.update() 

    def set_flank_opacity(self, value):
        self.flank_opacity = max(0, min(255, int(value)))
        self.update()
        
    def set_status(self, is_active):
        """
        Updates the peripheral status bar.
        True = Green (Flowing)
        False = Red (Stopped)
        """
        self.is_active = is_active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font)

        bar_width = 300      
        bar_height = 6       
        radius = 3           
        margin_bottom = 10   

        x_bar = (self.width() - bar_width) // 2
        y_bar = self.height() - bar_height - margin_bottom

        gradient = QLinearGradient(x_bar, y_bar, x_bar + bar_width, y_bar)

        if self.is_active:
            c_center = QColor("#4caf50")
            c_edge = QColor("#2e7d32") 
            c_edge.setAlpha(180)   
        else:
            c_center = QColor("#e57373")
            c_edge = QColor("#c62828")
            c_edge.setAlpha(180)

        gradient.setColorAt(0.0, c_edge)
        gradient.setColorAt(0.5, c_center)
        gradient.setColorAt(1.0, c_edge)

        painter.save()
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x_bar, y_bar, bar_width, bar_height, radius, radius)
        painter.restore()

        if is_header(self.text):
            painter.setPen(QColor("#ffffff"))
            draw_rect = self.rect().adjusted(0, 0, 0, -(bar_height + margin_bottom + 5))
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, self.text)
            return

        length = len(self.text)
        if length <= 1: orp = 0
        elif length <= 5: orp = 1
        elif length <= 9: orp = 2
        elif length <= 13: orp = 3
        else: orp = 4
        if orp >= length: orp = 0

        left_part = self.text[:orp]
        pivot_char = self.text[orp]
        right_part = self.text[orp+1:]

        left_w = self.metrics.horizontalAdvance(left_part)
        pivot_w = self.metrics.horizontalAdvance(pivot_char)
        right_w = self.metrics.horizontalAdvance(right_part)

        cx = self.width() // 2
        cy = (self.height() + self.metrics.ascent() - self.metrics.descent()) // 2
        pivot_draw_x = cx - (pivot_w // 2)

        painter.setPen(QColor("#ff5555"))
        painter.drawText(pivot_draw_x, cy, pivot_char)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(pivot_draw_x - left_w, cy, left_part)
        painter.drawText(pivot_draw_x + pivot_w, cy, right_part)

        painter.setPen(QPen(QColor("#444"), 2))
        painter.drawLine(cx, cy - 60, cx, cy - 75)
        painter.drawLine(cx, cy + 20, cx, cy + 35)
        base_offset = 250 
        padding = 40
        
        actual_left_reach = (pivot_w // 2) + left_w
        actual_right_reach = (pivot_w // 2) + right_w
        
        dist_left = max(base_offset, actual_left_reach + padding)
        dist_right = max(base_offset, actual_right_reach + padding)
        
        left_wall_x = cx - dist_left
        right_wall_x = cx + dist_right
        
        if self.prev_text:
            prev_w = self.metrics.horizontalAdvance(self.prev_text)
            draw_x = left_wall_x - prev_w
            
            painter.setPen(QColor(255, 255, 255, self.flank_opacity))
            painter.drawText(draw_x, cy, self.prev_text)

        if self.next_text:
            draw_x = right_wall_x
            
            painter.setPen(QColor(255, 255, 255, self.flank_opacity))
            painter.drawText(draw_x, cy, self.next_text)

class QueueMonitorPopup(QDialog):
    """The floating overlay for queue details."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 30, 230);
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(10, 10, 10, 10)
        self.frame.setLayout(frame_layout)
        
        self.lbl_current = QLabel("Active: None")
        self.lbl_current.setStyleSheet("color: #4a90e2; font-size: 11px; margin-bottom: 5px; font-weight: bold; background: transparent;")
        self.lbl_current.setWordWrap(True)
        frame_layout.addWidget(self.lbl_current)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar { border: none; background-color: #444; height: 4px; border-radius: 2px; }
            QProgressBar::chunk { background-color: #4a90e2; border-radius: 2px; }
        """)
        frame_layout.addWidget(self.progress)

        lbl_pending = QLabel("Pending Tasks:")
        lbl_pending.setStyleSheet("color: #aaa; font-size: 11px; margin-top: 8px; background: transparent;")
        frame_layout.addWidget(lbl_pending)

        self.list_pending = QListWidget()
        self.list_pending.setFixedHeight(150)
        self.list_pending.setStyleSheet("""
            QListWidget { background: rgba(0,0,0,50); border: 1px solid #444; border-radius: 2px; }
            QListWidget::item { color: #ccc; font-size: 11px; padding: 4px; border-bottom: 1px solid #444; }
        """)
        frame_layout.addWidget(self.list_pending)
        
        layout.addWidget(self.frame)
        
    def update_list(self, task_names):
        self.list_pending.clear()
        for name in task_names:
            self.list_pending.addItem(name)

    def update_status(self, text, is_busy):
        self.lbl_current.setText(text)
        if is_busy:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

class QueueMonitorWidget(QWidget):
    """The toggle button that sits in the toolbar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.btn_toggle = QPushButton("AI Queue: Idle")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #aaa;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                text-align: left;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:checked { background-color: #4a90e2; color: white; border-color: #4a90e2; }
        """)
        self.btn_toggle.clicked.connect(self.toggle_popup)
        self.layout.addWidget(self.btn_toggle)
        
        self.popup = QueueMonitorPopup(self)
        self.popup.hide()

        self.filter_installed = False

    def showEvent(self, event):
        """
        When this widget is first shown, find the Main Window
        and attach an event listener to it.
        """
        super().showEvent(event)
        if not self.filter_installed:
            window = self.window()
            if window:
                window.installEventFilter(self)
                self.filter_installed = True

    def eventFilter(self, obj, event):
        """
        Detect if the Main Window moves or resizes.
        If so, snap the popup back to the button.
        """
        if obj == self.window():
            if event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
                if self.popup.isVisible():
                    self.update_popup_position()
        
        return super().eventFilter(obj, event)

    def update_popup_position(self):
        """Calculates the global position and moves the popup there."""
        global_pos = self.btn_toggle.mapToGlobal(QPoint(0, self.btn_toggle.height()))
        
        x_pos = global_pos.x() - (250 - self.btn_toggle.width())
        self.popup.move(x_pos, global_pos.y() + 5)

    def toggle_popup(self):
        if self.btn_toggle.isChecked():
            self.popup.resize(250, 220) 
            self.update_popup_position()
            self.popup.show()
        else:
            self.popup.hide()

    def update_queue_list(self, task_names):
        count = len(task_names)
        current_text = self.popup.lbl_current.text()
        base_text = "AI Queue: Busy" if "Active" in current_text and "None" not in current_text else "AI Queue: Idle"
        
        if count > 0:
            self.btn_toggle.setText(f"AI Queue: {count} pending")
        else:
            self.btn_toggle.setText(base_text)
            
        self.popup.update_list(task_names)

    def set_processing(self, task_name):
        self.btn_toggle.setText("AI Queue: Busy")
        self.popup.update_status(f"Active: {task_name}", True)

    def set_idle(self):
        self.btn_toggle.setText("AI Queue: Idle")
        self.popup.update_status("Active: None", False)