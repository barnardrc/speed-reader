# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 20:42:08 2026

@author: barna
"""
import requests
import uuid
import queue
import markdown
from PyQt6.QtCore import (QThread, pyqtSignal, Qt, QPropertyAnimation, 
                          QEasingCurve, QRect, QMutex)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, 
    QPushButton, QTabWidget, QFrame, QTextBrowser, QProgressBar, 
    QListWidget, QListWidgetItem, QMenu, QSizePolicy
)
from PyQt6.QtGui import QFont


class SequentialAIWorker(QThread):
    result_ready = pyqtSignal(str, dict) 
    error_occurred = pyqtSignal(str)
    
    # UI Signals
    queue_updated = pyqtSignal(list)       
    processing_started = pyqtSignal(str)   
    processing_finished = pyqtSignal()     

    def __init__(self, backend_manager):
        super().__init__()
        self.manager = backend_manager
        self.task_queue = queue.Queue()
        self.is_running = True
        
        self.pending_tasks_ui = [] 
        self.mutex = QMutex()

    def add_task(self, prompt, metadata):
        self.mutex.lock()
        display_name = f"{metadata.get('type', 'Unknown')} - {len(prompt[:20])}..."
        self.pending_tasks_ui.append(display_name)
        
        self.task_queue.put((prompt, metadata, display_name))
        
        self.queue_updated.emit(list(self.pending_tasks_ui))
        self.mutex.unlock()

    def stop(self):
        self.is_running = False
        self.task_queue.put(None)

    def run(self):
        while self.is_running:
            task = self.task_queue.get()
            if task is None: break

            prompt, metadata, display_name = task

            # Update UI Lists
            self.mutex.lock()
            if display_name in self.pending_tasks_ui:
                self.pending_tasks_ui.remove(display_name)
            self.queue_updated.emit(list(self.pending_tasks_ui))
            self.mutex.unlock()
            
            self.processing_started.emit(display_name)

            try:
                payload = {
                    "model": self.manager.selected_model, 
                    "prompt": prompt, 
                    "stream": False,
                    "options": {"num_ctx": 4096}
                }
                
                url = f"{self.manager.ollama_url}/api/generate"
                
                response = requests.post(url, json=payload, timeout=self.manager.timeout)
                
                if response.status_code == 429:
                    raise Exception("Cloud Rate Limit (429). Please switch to a local model.")
                
                elif response.status_code == 503:
                    raise Exception("Service Overloaded (503). Cloud queue is full.")
                
                response.raise_for_status()
                
                answer = response.json().get("response", "No response.")
                self.result_ready.emit(answer, metadata)

            except requests.exceptions.Timeout:
                self.error_occurred.emit(f"Timeout ({self.manager.timeout}s) reached. Model is too slow or offline.")
            
            except requests.exceptions.ConnectionError:
                 self.error_occurred.emit("Connection Failed. Is Ollama running?")

            except Exception as e:
                self.error_occurred.emit(str(e))
            
            self.processing_finished.emit()
            self.task_queue.task_done()

class SubmitTextEdit(QTextEdit):
    submit_pressed = pyqtSignal()
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: super().keyPressEvent(event)
            else: self.submit_pressed.emit()
        else: super().keyPressEvent(event)

class QuestionTab(QWidget):
    closed = pyqtSignal(QWidget)
    validation_requested = pyqtSignal(str, str, str)
    
    def __init__(self, question_text, context_text, parent=None):
        super().__init__(parent)
        self.tab_id = str(uuid.uuid4())
        self.context_text = context_text
        self.question_text = question_text
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.layout)

        self.lbl_q = QLabel(question_text)
        self.lbl_q.setWordWrap(True)
        self.lbl_q.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.lbl_q.setStyleSheet("color: #e0e0e0; margin-bottom: 10px; background: transparent;")
        self.layout.addWidget(self.lbl_q)

        self.txt_answer = SubmitTextEdit() 
        self.txt_answer.setPlaceholderText("Type reflection (Enter to submit)...")
        self.txt_answer.setFixedHeight(100)
        self.txt_answer.setFont(QFont("Arial", 13))
        self.txt_answer.setStyleSheet("QTextEdit { background-color: rgba(43, 43, 43, 200); color: #ffffff; border: 1px solid #555; border-radius: 4px; padding: 5px; }")
        self.txt_answer.submit_pressed.connect(self.on_submit) 
        self.layout.addWidget(self.txt_answer)

        self.loader = QProgressBar()
        self.loader.setRange(0, 0)
        self.loader.setFixedHeight(4)
        self.loader.hide()
        self.layout.addWidget(self.loader)

        self.txt_feedback = QTextBrowser()
        self.txt_feedback.hide()
        self.txt_feedback.setStyleSheet("""
            QTextBrowser { 
                background-color: rgba(34, 34, 34, 200); 
                color: #ccc; 
                border: 1px solid #444; 
                border-radius: 4px; 
                padding: 10px; 
            }
        """)
        self.layout.addWidget(self.txt_feedback)

        self.btn_action = QPushButton("Submit Answer")
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_action.setStyleSheet("QPushButton { background-color: #4a90e2; color: white; border: none; padding: 10px; border-radius: 4px; } QPushButton:hover { background-color: #357abd; } QPushButton:disabled { background-color: #555; color: #888; }")
        self.btn_action.clicked.connect(self.on_submit)
        self.layout.addWidget(self.btn_action)

    def on_submit(self):
        user_ans = self.txt_answer.toPlainText().strip()
        if not user_ans: return

        self.txt_answer.setDisabled(True)
        self.btn_action.setDisabled(True)
        self.btn_action.setText("Waiting for Queue...")
        self.loader.show()
        
        prompt = (
            f"Context: \"{self.context_text}\"\n"
            f"Question: \"{self.question_text}\"\n"
            f"User Answer: \"{user_ans}\"\n\n"
            f"Task: Provide a micro-feedback summary (max 3-4 sentences) on the user's answer.\n"
            f"Constraints: Be concise. No tables. No long paragraphs.\n"
            f"Tone: Direct, encouraging, and brief.\n\n"
            f"Instructions:\n"
            f"1. Verdict First: Immediately validate if the answer is correct, partially correct, or incorrect.\n"
            f"2. The 'One Thing': If they missed something, provide only the single most important missing fact from the context. Do not list everything.\n"
            f"3. No Fluff: Do not use pleasantries like 'Thank you for your answer' or 'That is an interesting thought'. Jump straight to the point.\n"
            f"4. Formatting: Use **bold** for key terms to make it skimmable.\n"
            f"5. Closure: End with a short confirming statement. Do not ask follow-up questions."
        )
        
        self.validation_requested.emit(prompt, self.context_text, self.tab_id)

    def apply_feedback(self, response):
        """Called by parent when worker finishes"""
        self.loader.hide()
        
        if "Error" in response:
             self.btn_action.setText("Error. Try Again")
             self.btn_action.setEnabled(True)
             self.txt_answer.setDisabled(False)
        else:
            html_body = markdown.markdown(response, extensions=['tables'])
            css_style = """
            <style>
                body { 
                    font-family: Arial; 
                    font-size: 16pt; 
                    line-height: 1.6; 
                    color: #ccc; 
                }
                p { margin-bottom: 12px; }
                strong { color: #fff; }
                ul { margin-bottom: 12px; margin-left: -20px; }
            </style>
            """
            
            styled_html = f"{css_style}<div>{html_body}</div>"
            
            self.txt_feedback.setHtml(styled_html)

            self.txt_feedback.show()
            self.btn_action.setText("Dismiss / Done")
            self.btn_action.setEnabled(True)
            try: self.btn_action.clicked.disconnect()
            except: pass
            self.btn_action.clicked.connect(lambda: self.closed.emit(self))
            
class AIQuestionPanel(QFrame):
    submit_task_signal = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(500)
        self.is_resizing = False
        self.resize_margin = 15
        self.min_height = 150
        self.max_height = 1000
        self.current_height = 600
        self.anchor_y = 0
        self.global_anchor_y = 0
        self.collapsed_height = 40
        
        self.is_expanded = False
        
        self.setMouseTracking(True)

        self.default_style = """
            AIQuestionPanel {
                background-color: rgba(30, 30, 30, 0);
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """
        self.setStyleSheet(self.default_style)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, self.resize_margin, 0, 0)
        self.content_area.setLayout(self.content_layout)
        
        self.content_area.setStyleSheet("background-color: rgba(30, 30, 30, 150); border-radius: 5px;")
        
        lbl = QLabel("  Comprehension Stack")
        lbl.setFixedHeight(30)
        lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #aaa; background: transparent; padding-left: 10px; border-bottom: 1px solid #444;")
        self.content_layout.addWidget(lbl)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: transparent; }
            QTabWidget::tab-bar { alignment: left; }
            QTabBar::tab {
                background: rgba(60, 60, 60, 100); 
                color: #aaa;
                padding: 12px 6px;
                margin-bottom: 2px;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
                font-size: 13px;
                min-height: 40px;
            }
            QTabBar::tab:selected { background: rgba(74, 144, 226, 200); color: white; }
        """)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.content_layout.addWidget(self.tabs)
        layout.addWidget(self.content_area, stretch=1)

        self.header_bar = QFrame()
        self.header_bar.setFixedHeight(40)
        self.header_bar.setStyleSheet("background: rgba(30, 30, 30, 180); border-top: 1px solid #444; border-radius: 0px;")
        hb_layout = QVBoxLayout()
        hb_layout.setContentsMargins(0,0,0,0)
        self.header_bar.setLayout(hb_layout)
        self.header_btn = QPushButton("▲ Comprehension Stack")
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.header_btn.setStyleSheet("""
            QPushButton {
                text-align: right;
                padding-right: 15px;
                background: transparent;
                border: none;
                color: #aaa;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        self.header_btn.clicked.connect(self.toggle_expand)
        hb_layout.addWidget(self.header_btn)
        
        layout.addWidget(self.header_bar, stretch=0)
        
        self.question_count = 0
        self.content_area.hide() 

    def place_panel(self, x, bottom_y, global_bottom_y):
        self.anchor_y = bottom_y
        self.global_anchor_y = global_bottom_y
        h = self.current_height if self.is_expanded else self.collapsed_height
        new_y = self.anchor_y - h
        self.setGeometry(x, new_y, self.width(), h)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() <= self.resize_margin and self.is_expanded:
                self.is_resizing = True
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_expanded and event.position().y() <= self.resize_margin:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif event.position().y() >= self.height() - 40:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.is_resizing:
            global_mouse_y = event.globalPosition().y()
            new_h = self.global_anchor_y - global_mouse_y
            new_h = max(self.min_height, min(self.max_height, new_h))
            self.current_height = int(new_h)
            self.setGeometry(self.x(), self.anchor_y - self.current_height, self.width(), self.current_height)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_resizing = False
        super().mouseReleaseEvent(event)

    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        arrow = "▼" if self.is_expanded else "▲"
        
        self.header_btn.setText(f"{arrow} Comprehension Stack")
        
        self.header_btn.setStyleSheet("""
            QPushButton {
                text-align: right;
                padding-right: 15px;
                background: transparent;
                border: none;
                color: #aaa;
            }
            QPushButton:hover { color: #ffffff; }
        """)
        
        target_h = self.current_height if self.is_expanded else self.collapsed_height
        
        start_geo = self.geometry()
        new_y = self.anchor_y - target_h
        end_geo = QRect(start_geo.x(), new_y, start_geo.width(), target_h)
        
        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(300)
        self.geo_anim.setStartValue(start_geo)
        self.geo_anim.setEndValue(end_geo)
        self.geo_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        if self.is_expanded:
            self.content_area.show()
            self.geo_anim.start()
        else:
            self.geo_anim.finished.connect(self.content_area.hide)
            self.geo_anim.start()
            try: self.geo_anim.finished.disconnect(self._hide_finished)
            except: pass
            self.geo_anim.finished.connect(self._hide_finished)

    def _hide_finished(self):
        self.content_area.hide()
        try: self.geo_anim.finished.disconnect(self._hide_finished)
        except: pass

    def add_question(self, question, context):
        self.question_count += 1
        tab = QuestionTab(question, context)
        tab.validation_requested.connect(self.handle_tab_validation)
        tab.closed.connect(self.remove_question)
        self.tabs.addTab(tab, f"Q{self.question_count}")
        self.flash_update()

    def flash_update(self):
        if not self.is_expanded:
            self.header_btn.setStyleSheet("""
                QPushButton {
                    text-align: right;
                    padding-right: 15px;
                    background: transparent;
                    border: none;
                    color: #4a90e2;
                }
                QPushButton:hover { color: #ffffff; }
            """)

    def remove_question(self, widget):
        idx = self.tabs.indexOf(widget)
        if idx != -1: 
            self.tabs.removeTab(idx)
        
        if self.tabs.count() == 0 and self.is_expanded:
            self.toggle_expand()

    def handle_tab_validation(self, prompt, context, tab_id):
        metadata = {
            "type": "CHECK_ANSWER",
            "tab_id": tab_id,
            "context": context
        }
        self.submit_task_signal.emit(prompt, metadata)

    def deliver_feedback(self, tab_id, response):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, QuestionTab) and widget.tab_id == tab_id:
                widget.apply_feedback(response)
                self.flash_update()
                break
            
# --- ENTITY TRACKER ---
class DeletableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace): self.delete_selected()
        else: super().keyPressEvent(event)
    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item:
            menu = QMenu(self)
            del_action = menu.addAction("Delete")
            action = menu.exec(self.mapToGlobal(pos))
            if action == del_action: self.takeItem(self.row(item))
    def delete_selected(self):
        for item in self.selectedItems(): self.takeItem(self.row(item))

class EntityPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(450)
        self.is_expanded = False
        self.expanded_height = 300
        self.collapsed_height = 40 
        self.anchor_y = 0 
        self.setStyleSheet("""
            EntityPanel {
                background-color: rgba(30, 30, 30, 240);
                border: 1px solid #555;
                border-bottom: none; 
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """)
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.content_area = QWidget()
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_area.setLayout(self.content_layout)
        
        self.list_widget = DeletableListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.list_widget.setWordWrap(True)
        self.list_widget.setStyleSheet("""
            QListWidget { background: transparent; border: none; }
            QListWidget::item { background-color: rgba(60, 60, 60, 150); color: #ddd; border-radius: 4px; padding: 8px; margin-bottom: 4px; border-bottom: 1px solid #444; }
            QListWidget::item:selected { background-color: #4a90e2; color: white; }
        """)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.content_layout.addWidget(self.list_widget)
        
        self.layout.addWidget(self.content_area, stretch=1)
        self.content_area.hide()

        self.header = QPushButton("Context Monitor ▲")
        self.header.setFixedHeight(40)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.header.setStyleSheet("""
            QPushButton { background-color: transparent; color: #aaa; border: none; text-align: left; padding-left: 15px; border-top: 1px solid #444; }
            QPushButton:hover { color: #fff; }
        """)
        self.header.clicked.connect(self.toggle)
        self.header.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layout.addWidget(self.header, stretch=0)
        
        self.resize(self.width(), self.collapsed_height)
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    def place_panel(self, x, bottom_y):
        self.anchor_y = bottom_y
        current_h = self.expanded_height if self.is_expanded else self.collapsed_height
        new_y = self.anchor_y - current_h
        self.setGeometry(x, new_y, self.width(), current_h)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        arrow = "▼" if self.is_expanded else "▲"
        self.header.setText(f"Context Monitor {arrow}")
        if self.is_expanded:
            style = self.header.styleSheet()
            self.header.setStyleSheet(style.replace("color: #4a90e2;", "color: #aaa;"))
        self.animate_resize()

    def animate_resize(self):
        try: self.anim.finished.disconnect(self._hide_finished)
        except: pass

        target_h = self.expanded_height if self.is_expanded else self.collapsed_height
        bottom = self.anchor_y if self.anchor_y != 0 else (self.geometry().y() + self.geometry().height())
        new_y = bottom - target_h
        curr_geo = self.geometry()
        
        self.anim.setStartValue(curr_geo)
        self.anim.setEndValue(QRect(curr_geo.x(), new_y, curr_geo.width(), target_h))
        
        if self.is_expanded:
            self.content_area.show()
            self.anim.start()
        else:
            self.anim.finished.connect(self._hide_finished)
            self.anim.start()

    def _hide_finished(self):
        self.content_area.hide()
        try: self.anim.finished.disconnect(self._hide_finished)
        except: pass

    def add_entities(self, entity_text_block):
        lines = entity_text_block.strip().split('\n')
        added_count = 0
        existing = set()
        
        for i in range(self.list_widget.count()):
            t = self.list_widget.item(i).text()
            if " - " in t: 
                existing.add(t.split(" - ")[0].strip().lower())

        # Blacklist for common false positives
        blacklist = ["chapter", "section", "part", "page", "title"]

        for line in lines:
            clean = line.strip().lstrip('-• ').strip()
            
            if not clean: continue
            if clean.lower().startswith("none"): continue
            
            if " - " not in clean: continue
            
            name_part = clean.split(" - ")[0].strip()
            name_lower = name_part.lower()
            
            if any(x in name_lower for x in blacklist): continue
            
            if name_lower not in existing:
                self.list_widget.addItem(QListWidgetItem(clean))
                existing.add(name_lower)
                added_count += 1
            
        if added_count > 0:
            self.list_widget.scrollToBottom()
            if not self.is_expanded:
                style = self.header.styleSheet()
                if "color: #4a90e2;" not in style:
                    self.header.setStyleSheet(style.replace("color: #aaa;", "color: #4a90e2;"))