# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 08:13:09 2026

@author: barna
"""
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QWidget, QProgressBar, QPushButton, QListWidget,
    QFrame, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,  
    QSpinBox, QSlider
)

from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen, QLinearGradient
from PyQt6.QtCore import QRectF, QPointF, QPoint, QEvent
from utils.text_utils import is_header

from PyQt6.QtGui import QBrush
from PyQt6.QtCore import QTimer

class CameraIndicator(QWidget):
    clicked = pyqtSignal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20) 
        self.active = False
        self.setStyleSheet("background: transparent;")
        
        self.timer = QTimer()
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.turn_off)
        self.timer.start()

    def mousePressEvent(self, event):
        """Detect touch/click to toggle debug"""
        self.clicked.emit()
        super().mousePressEvent(event)

    def ping(self):
        if not self.active:
            self.active = True
            self.update()
        self.timer.start()

    def turn_off(self):
        if self.active:
            self.active = False
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.active:
            color = QColor("#00e676")
        else:
            color = QColor("#555")

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        # Centered dot
        painter.drawEllipse(5, 5, 10, 10)

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
        
        self.max_font_size = 24
        self.font_ctx = QFont("Georgia", self.max_font_size)
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

    def resizeEvent(self, event):
        """Dynamically scales context font based on widget height."""
        h = self.height()

        target_size = int(h * 0.04) 
        new_size = max(12, min(self.max_font_size, target_size))
        
        if self.font_ctx.pointSize() != new_size:
            self.font_ctx.setPointSize(new_size)
            self.metrics = QFontMetrics(self.font_ctx)
            
        super().resizeEvent(event)

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
        
        # Use updated metrics
        line_height = self.metrics.height() + 5 
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
        
        self.max_font_size = 48
        self.font = QFont("Consolas", self.max_font_size, QFont.Weight.Bold)
        self.metrics = QFontMetrics(self.font)
        
        self.setMinimumHeight(80)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_word(self, word, prev_word="", next_word=""):
        self.text = word
        self.prev_text = prev_word
        self.next_text = next_word
        self.update() 

    def set_flank_opacity(self, value):
        self.flank_opacity = max(0, min(255, int(value)))
        self.update()
        
    def set_status(self, status_code):
        """
        Updates the peripheral status bar.
        0 = Red (Stopped)
        1 = Green (Flowing)
        2 = Orange (Gaze Paused)
        """
        self.status_code = status_code
        self.update()

    def resizeEvent(self, event):
        """Dynamically scales font based on widget dimensions."""
        h = self.height()
        w = self.width()
        
        target_h = int(h * 0.4)
        target_w = int(w / 15)
        
        new_size = min(self.max_font_size, target_h, target_w)
        new_size = max(14, new_size)
        
        if self.font.pointSize() != new_size:
            self.font.setPointSize(new_size)
            self.metrics = QFontMetrics(self.font)
            
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font)

        # Scale bar dimensions
        bar_height = max(4, int(self.height() * 0.05))
        bar_width = min(300, int(self.width() * 0.8))
        radius = bar_height // 2
        margin_bottom = 10    

        x_bar = (self.width() - bar_width) // 2
        y_bar = self.height() - bar_height - margin_bottom

        gradient = QLinearGradient(x_bar, y_bar, x_bar + bar_width, y_bar)

        # STATUS COLOR LOGIC
        if getattr(self, 'status_code', 0) == 1: 
            c_center = QColor("#4caf50")
            c_edge = QColor("#2e7d32")
        elif getattr(self, 'status_code', 0) == 2: 
            c_center = QColor("#ff9800")
            c_edge = QColor("#f57c00")
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
        
        # Font-relative measurements
        f_ascent = self.metrics.ascent()
        f_height = self.metrics.height()

        cx = self.width() // 2
        cy = (self.height() + f_ascent - self.metrics.descent()) // 2
        pivot_draw_x = cx - (pivot_w // 2)

        painter.setPen(QColor("#ff5555"))
        painter.drawText(pivot_draw_x, cy, pivot_char)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(pivot_draw_x - left_w, cy, left_part)
        painter.drawText(pivot_draw_x + pivot_w, cy, right_part)

        # Dynamic Pivot Lines
        painter.setPen(QPen(QColor("#444"), max(1, f_height // 20)))
        
        top_line_y = cy - f_ascent - (f_height // 4)
        top_line_len = f_height // 3
        painter.drawLine(cx, top_line_y, cx, top_line_y - top_line_len)
        
        bot_line_y = cy + (f_height // 4)
        bot_line_len = f_height // 3
        painter.drawLine(cx, bot_line_y, cx, bot_line_y + bot_line_len)
        
        # Calculate Wall Offsets dynamically
        base_offset = min(250, int(self.width() * 0.35)) 
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

        # --- STATE TRACKING (Prevents UI Race Conditions) ---
        self.is_active = False 
        self.pending_count = 0

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
        
        # Initialize Popup
        from ui.widgets import QueueMonitorPopup # Ensure import is here or at top
        self.popup = QueueMonitorPopup(self)
        self.popup.hide()

        self.filter_installed = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self.filter_installed:
            window = self.window()
            if window:
                window.installEventFilter(self)
                self.filter_installed = True

    def eventFilter(self, obj, event):
        if obj == self.window():
            if event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
                if self.popup.isVisible():
                    self.update_popup_position()
        return super().eventFilter(obj, event)

    def update_popup_position(self):
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

    def update_button_text(self):
        """Centralized text updater to prevent conflicts."""
        if self.pending_count > 0:
            self.btn_toggle.setText(f"AI Queue: {self.pending_count} pending")
        else:
            status = "Busy" if self.is_active else "Idle"
            self.btn_toggle.setText(f"AI Queue: {status}")

    def update_queue_list(self, task_names):
        # --- SAFETY GUARD ---
        # Prevents the C++ Assertion '!this->empty()' failure
        if task_names is None:
            task_names = []
            
        self.pending_count = len(task_names)
        self.update_button_text()
            
        if hasattr(self, 'popup'):
            self.popup.update_list(task_names)

    def set_processing(self, task_name):
        self.is_active = True
        self.update_button_text()
        if hasattr(self, 'popup'):
            self.popup.update_status(f"Active: {task_name}", True)

    def set_idle(self):
        self.is_active = False
        self.update_button_text()
        if hasattr(self, 'popup'):
            self.popup.update_status("Active: None", False)

class ControlBar(QWidget):
    # Signals to communicate with Main Window
    wpm_changed = pyqtSignal(int)
    opacity_changed = pyqtSignal(int)
    flank_changed = pyqtSignal(int)
    ctx_range_changed = pyqtSignal(int)
    pause_settings_clicked = pyqtSignal()
    ai_settings_clicked = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.compact_threshold = 750
        
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.layout.setSpacing(5)
        self.setLayout(self.layout)

        # --- Primary Controls ---
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        
        row1.addWidget(QLabel("Speed:"))
        
        # WPM Spinbox
        self.wpm_spin = QSpinBox()
        self.wpm_spin.setRange(60, 1000)
        self.wpm_spin.setValue(self.settings.get("wpm", 300))
        self.wpm_spin.setFixedWidth(60)
        self.wpm_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.wpm_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wpm_spin.valueChanged.connect(self.on_spin_change)
        row1.addWidget(self.wpm_spin)

        # WPM Slider
        self.wpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.wpm_slider.setRange(60, 1000)
        self.wpm_slider.setValue(self.settings.get("wpm", 300))
        self.wpm_slider.valueChanged.connect(self.on_slider_change)
        row1.addWidget(self.wpm_slider)

        row1.addSpacing(10)

        # Buttons
        self.btn_pauses = QPushButton("Pauses")
        self.btn_pauses.clicked.connect(self.pause_settings_clicked.emit)
        row1.addWidget(self.btn_pauses)

        self.btn_ai = QPushButton("AI Settings")
        self.btn_ai.clicked.connect(self.ai_settings_clicked.emit)
        row1.addWidget(self.btn_ai)
        
        # Toggle Button
        self.btn_visuals = QPushButton("Visuals ▼")
        self.btn_visuals.setCheckable(True)
        self.btn_visuals.setFixedWidth(80)
        self.btn_visuals.clicked.connect(self.toggle_visual_row)
        self.btn_visuals.hide() 
        row1.addWidget(self.btn_visuals)

        self.layout.addLayout(row1)

        # --- Row 2: Visual Sliders ---
        self.visual_frame = QFrame()
        self.visual_layout = QHBoxLayout()
        self.visual_layout.setContentsMargins(0, 5, 0, 0)
        self.visual_frame.setLayout(self.visual_layout)

        def add_slider(label, key, min_v, max_v, default, signal):
            self.visual_layout.addWidget(QLabel(label))
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(min_v, max_v)
            val = self.settings.get(key, default)
            sl.setValue(val)
            sl.valueChanged.connect(signal.emit)
            self.visual_layout.addWidget(sl)
            self.visual_layout.addSpacing(10)
            return sl

        self.op_slider = add_slider("Context:", "opacity", 0, 100, 50, self.opacity_changed)
        self.flank_slider = add_slider("Flank:", "flank_opacity", 0, 255, 60, self.flank_changed)
        self.ctx_slider = add_slider("Range:", "context_range", 5, 100, 20, self.ctx_range_changed)

        self.layout.addWidget(self.visual_frame)

    # --- Sync Logic ---
    def on_spin_change(self, val):
        self.wpm_slider.blockSignals(True)
        self.wpm_slider.setValue(val)
        self.wpm_slider.blockSignals(False)
        self.wpm_changed.emit(val)

    def on_slider_change(self, val):
        self.wpm_spin.blockSignals(True)
        self.wpm_spin.setValue(val)
        self.wpm_spin.blockSignals(False)
        self.wpm_changed.emit(val)

    def update_wpm(self, val):
        """External update"""
        self.wpm_spin.setValue(val)

    # --- Responsive Logic ---
    def toggle_visual_row(self, checked):
        self.visual_frame.setVisible(checked)
        arrow = "▲" if checked else "▼"
        self.btn_visuals.setText(f"Visuals {arrow}")

    def resizeEvent(self, event):
        is_compact = self.width() < self.compact_threshold
        
        if is_compact:
            # Compact Mode
            self.btn_visuals.show()
            if not self.btn_visuals.isChecked():
                self.visual_frame.hide()
        else:
            # Full Mode
            self.btn_visuals.hide()
            self.visual_frame.show()
            
        super().resizeEvent(event)