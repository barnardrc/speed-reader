# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 08:13:09 2026

@author: barna
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen
from PyQt6.QtCore import Qt, QRectF, QPointF
from utils.text_utils import is_header

class ContextFlowWidget(QWidget):
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
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_data(self, words, index, ctx_range, opacity, s_start, s_end):
        self.words = words
        self.index = index
        self.ctx_range = ctx_range
        self.opacity = opacity
        self.s_start = s_start
        self.s_end = s_end
        self.update() 

    def paintEvent(self, event):
        if not self.words: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font_ctx)

        # Basic setup
        base_alpha_val = int(255 * (self.opacity / 100.0))
        hl_color = QColor("#ffd700")
        
        # Layout metrics
        margin_x = 40
        line_height = self.metrics.height() + 10
        space_width = self.metrics.horizontalAdvance(" ")
        ascent = self.metrics.ascent()
        
        w_height = self.height()
        center_x = self.width() / 2
        center_y = w_height / 2
        
        screen_fade_zone = w_height * 0.15 
        
        left_bound = margin_x
        right_bound = self.width() - margin_x

        # --- Fade Logic ---
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

        # --- 1. Draw Active Word (CENTERED) ---
        active_word = self.words[self.index]
        
        # FIX: Calculate width using BOLD metrics
        painter.save() # Save current state
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

        # Draw Background
        if self.s_start <= self.index <= self.s_end:
             painter.fillRect(aw_rect, QColor(255, 255, 255, 30))

        # Draw Text
        painter.setPen(hl_color)
        text_y = aw_rect.top() + ((aw_rect.height() - bold_metrics.height()) / 2) + bold_metrics.ascent()
        painter.drawText(QPointF(aw_rect.left(), text_y), active_word)
        
        painter.restore() # Restore to standard font for neighbors

        # --- 2. Draw Forwards (Right/Down) ---
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

        # --- 3. Draw Backwards (Left/Up) ---
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
        self.font = QFont("Consolas", 48, QFont.Weight.Bold)
        self.metrics = QFontMetrics(self.font)
        self.setMinimumHeight(150)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_word(self, word):
        self.text = word
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font)

        # --- HEADER LOGIC ---
        if is_header(self.text): # <--- Use the helper
            painter.setPen(QColor("#ffffff"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)
            return
        
        # --- STANDARD OVP LOGIC ---
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

        cx = self.width() // 2
        cy = (self.height() + self.metrics.ascent() - self.metrics.descent()) // 2
        
        pivot_width = self.metrics.horizontalAdvance(pivot_char)
        pivot_x = cx - (pivot_width // 2)

        # Draw Guide Lines
        painter.setPen(QPen(QColor("#444"), 2))
        painter.drawLine(cx, cy - 60, cx, cy - 75)
        painter.drawLine(cx, cy + 20, cx, cy + 35)

        # Draw Pivot (Red)
        painter.setPen(QColor("#ff5555"))
        painter.drawText(pivot_x, cy, pivot_char)

        # Draw Left & Right (White)
        painter.setPen(QColor("#ffffff"))
        left_width = self.metrics.horizontalAdvance(left_part)
        painter.drawText(pivot_x - left_width, cy, left_part)
        painter.drawText(pivot_x + pivot_width, cy, right_part)