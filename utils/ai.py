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
    QListWidget, QListWidgetItem, QMenu, QSizePolicy, QStackedWidget,
    QHBoxLayout
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
        
        # Main layout
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.layout)

        # Question Label
        self.lbl_q = QLabel(question_text)
        self.lbl_q.setWordWrap(True)
        self.lbl_q.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.lbl_q.setStyleSheet("color: #e0e0e0; background: transparent;")
        self.layout.addWidget(self.lbl_q)

        # Answer Input
        self.txt_answer = SubmitTextEdit() 
        self.txt_answer.setPlaceholderText("Type reflection...")
        self.txt_answer.setFixedHeight(80) # Slightly shorter for RPi
        self.txt_answer.setFont(QFont("Arial", 12))
        self.txt_answer.setStyleSheet("QTextEdit { background-color: rgba(43, 43, 43, 200); color: #ffffff; border: 1px solid #555; border-radius: 4px; padding: 5px; }")
        self.txt_answer.submit_pressed.connect(self.on_submit) 
        self.layout.addWidget(self.txt_answer)

        # Loader
        self.loader = QProgressBar()
        self.loader.setFixedHeight(4)
        self.loader.setTextVisible(False)
        self.loader.hide()
        self.layout.addWidget(self.loader)

        # Feedback Area
        self.txt_feedback = QTextBrowser()
        self.txt_feedback.hide()
        self.txt_feedback.setStyleSheet("background-color: rgba(34, 34, 34, 200); color: #ccc; border: 1px solid #444; border-radius: 4px; padding: 5px;")
        self.layout.addWidget(self.txt_feedback)

        # Action Button
        self.btn_action = QPushButton("Submit")
        self.btn_action.setFixedHeight(40)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setStyleSheet("""
            QPushButton { background-color: #4a90e2; color: white; border: none; border-radius: 4px; font-weight: bold; font-size: 14px; } 
            QPushButton:hover { background-color: #357abd; } 
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_action.clicked.connect(self.on_submit)
        self.layout.addWidget(self.btn_action)

    def on_submit(self):
        user_ans = self.txt_answer.toPlainText().strip()
        if not user_ans: return

        self.txt_answer.setDisabled(True)
        self.btn_action.setDisabled(True)
        self.btn_action.setText("Analyzing...")
        self.loader.show()
        
        prompt = (
            f"Context: \"{self.context_text}\"\nQuestion: \"{self.question_text}\"\nUser Answer: \"{user_ans}\"\n\n"
            f"Task: Micro-feedback (max 3 sentences). 1. Verdict (Correct/Incorrect). 2. Missing Key Fact. 3. Closure.\n"
            f"Format: Use **bold** for key terms."
        )
        self.validation_requested.emit(prompt, self.context_text, self.tab_id)

    def apply_feedback(self, response):
        self.loader.hide()
        if "Error" in response:
             self.btn_action.setText("Retry")
             self.btn_action.setEnabled(True)
             self.txt_answer.setDisabled(False)
        else:
            html_body = markdown.markdown(response)
            styled_html = f"<style>body {{ font-family: Arial; font-size: 14px; color: #ccc; }} strong {{ color: #fff; }}</style><div>{html_body}</div>"
            self.txt_feedback.setHtml(styled_html)
            self.txt_feedback.show()
            self.btn_action.setText("Done")
            self.btn_action.setEnabled(True)
            try: self.btn_action.clicked.disconnect()
            except: pass
            self.btn_action.clicked.connect(lambda: self.closed.emit(self))
            
class AIQuestionPanel(QFrame):
    submit_task_signal = pyqtSignal(str, dict)
    panel_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(500) # Default, but user can resize
        self.current_height = 500
        self.collapsed_height = 40
        self.is_expanded = False
        
        # Resize logic variables
        self.is_resizing_h = False
        self.is_resizing_w = False
        self.resize_margin = 15

        self.setMouseTracking(True)
        self.setStyleSheet("background-color: rgba(30, 30, 30, 0); border: 1px solid #555; border-radius: 8px;")

        # --- Master Layout ---
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)

        # --- Content Container (Hidden when collapsed) ---
        self.content_container = QWidget()
        self.content_container.setStyleSheet("background-color: rgba(30, 30, 30, 240); border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        
        # Horizontal layout: [Sidebar] | [Stacked Pages]
        self.h_layout = QHBoxLayout()
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(0)
        self.content_container.setLayout(self.h_layout)

        # 1. Sidebar (Custom Buttons)
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(120) # Starts wide
        self.sidebar.setStyleSheet("background-color: rgba(45, 45, 45, 255); border-right: 1px solid #555;")
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setContentsMargins(5, 10, 5, 10)
        self.sidebar_layout.setSpacing(5)
        self.sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sidebar.setLayout(self.sidebar_layout)
        
        self.h_layout.addWidget(self.sidebar)

        # 2. Stacked Widget (The Content)
        self.stack = QStackedWidget()
        self.h_layout.addWidget(self.stack)

        self.main_layout.addWidget(self.content_container)

        # --- Header Bar (Always Visible) ---
        self.header_bar = QFrame()
        self.header_bar.setFixedHeight(40)
        self.header_bar.setStyleSheet("background: rgba(40, 40, 40, 255); border-top: 1px solid #666; border-radius: 0px;")
        hb_layout = QHBoxLayout()
        hb_layout.setContentsMargins(10, 0, 10, 0)
        self.header_bar.setLayout(hb_layout)

        self.header_btn = QPushButton("▲ Comprehension Stack")
        self.header_btn.setStyleSheet("border: none; color: #aaa; font-weight: bold; text-align: right;")
        self.header_btn.clicked.connect(self.toggle_expand)
        hb_layout.addWidget(self.header_btn)
        
        self.main_layout.addWidget(self.header_bar)

        self.content_container.hide()
        self.question_count = 0
        self.buttons = [] # Store references to sidebar buttons
        
        self.max_width = 500
        self.button_width = 80
        self.button_mode = False
        self.anchor_y = 0
        self.global_anchor_y = 0
        self.closed_x = 0
    
    def collapse(self):
        """Helper to force close from outside"""
        if self.is_expanded:
            self.toggle_expand()
    
    def place_panel(self, x, bottom_y, global_bottom_y):
        self.anchor_y = bottom_y
        self.global_anchor_y = global_bottom_y
        self.closed_x = x # Save anchor
        
        h = self.current_height if self.is_expanded else self.collapsed_height
        
        if self.is_expanded and self.button_mode:
            w = self.parent().width() - 20
            actual_x = 10
        else:
            w = self.max_width if self.is_expanded else (self.button_width if self.button_mode else self.max_width)
            actual_x = x
            
        self.setGeometry(actual_x, self.anchor_y - h, w, h)
    
    def set_button_mode(self, enabled):
        if self.button_mode == enabled: return
        self.button_mode = enabled
        
        # Force Sidebar to match
        self.set_compact_mode(enabled)
        
        if not self.is_expanded:
            w = self.button_width if enabled else self.max_width
            txt = "AI" if enabled else "▲ Comprehension Stack"
            self.setFixedWidth(w)
            self.header_btn.setText(txt)
            
    def add_question(self, question, context):
        self.question_count += 1
        
        # Create Content Page
        page = QuestionTab(question, context)
        page.validation_requested.connect(self.handle_tab_validation)
        page.closed.connect(self.remove_question)
        
        # Create Sidebar Button
        btn_text = f"Q{self.question_count}"
        btn = QPushButton(btn_text)
        btn.setCheckable(True)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Store metadata on button
        btn.setProperty("page_widget", page) 
        btn.setProperty("full_text", f"Question {self.question_count}")
        btn.setProperty("short_text", f"Q{self.question_count}")
        
        btn.clicked.connect(lambda: self.switch_to_page(btn))
        
        self.sidebar_layout.addWidget(btn)
        self.stack.addWidget(page)
        self.buttons.append(btn)
        
        # Auto-select if first
        if len(self.buttons) == 1:
            btn.setChecked(True)
            self.switch_to_page(btn)

        self.update_sidebar_style()
        self.flash_update()

    def switch_to_page(self, clicked_btn):
        # Enforce radio behavior
        for btn in self.buttons:
            btn.setChecked(False)
        clicked_btn.setChecked(True)
        
        page = clicked_btn.property("page_widget")
        self.stack.setCurrentWidget(page)

    def remove_question(self, widget):
        # Find button associated with this widget
        btn_to_remove = None
        for btn in self.buttons:
            if btn.property("page_widget") == widget:
                btn_to_remove = btn
                break
        
        if btn_to_remove:
            self.sidebar_layout.removeWidget(btn_to_remove)
            btn_to_remove.deleteLater()
            self.buttons.remove(btn_to_remove)

        self.stack.removeWidget(widget)
        widget.deleteLater()

        # Select previous if exists
        if self.buttons:
            self.buttons[-1].click()
        elif self.is_expanded:
            self.toggle_expand()

    def set_compact_mode(self, is_compact):
        """Called by parent window to force layout mode"""
        # Only update if state actually changes to avoid flicker
        if getattr(self, '_current_compact_state', None) == is_compact:
            return
            
        self._current_compact_state = is_compact
        self.update_sidebar_style(is_compact)

    def update_sidebar_style(self, is_compact=False):
        """Dynamic styling based on compact flag"""
        # Adjust Sidebar Width
        new_width = 50 if is_compact else 140
        self.sidebar.setFixedWidth(new_width)

        # Update Buttons
        for btn in self.buttons:
            txt = btn.property("short_text") if is_compact else btn.property("full_text")
            btn.setText(txt)
            
        # CSS for buttons
        pad = "0px" if is_compact else "10px"
        align = "center" if is_compact else "left"
        
        self.sidebar.setStyleSheet(f"""
            QWidget {{ background-color: #2d2d2d; border-right: 1px solid #444; }}
            QPushButton {{
                color: #aaa;
                border: none;
                border-left: 3px solid transparent;
                text-align: {align};
                padding-left: {pad};
                background: transparent;
                font-size: 13px;
            }}
            QPushButton:checked {{
                background-color: #383838;
                color: #4a90e2;
                border-left: 3px solid #4a90e2;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #383838; color: white; }}
        """)

    def resizeEvent(self, event):
        # Auto-collapse sidebar if panel gets too narrow
        if self.is_expanded:
            self.update_sidebar_style()
        super().resizeEvent(event)

    # --- Passthroughs ---
    def handle_tab_validation(self, p, c, t):
        self.submit_task_signal.emit(p, {"type": "CHECK_ANSWER", "tab_id": t, "context": c})

    def deliver_feedback(self, tab_id, response):
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            if isinstance(w, QuestionTab) and w.tab_id == tab_id:
                w.apply_feedback(response)
                break

    def toggle_expand(self):
        if self.anchor_y == 0: return
        self.is_expanded = not self.is_expanded
        self.panel_toggled.emit(self.is_expanded)

        # Text Logic
        if self.button_mode and not self.is_expanded:
            self.header_btn.setText("AI")
        else:
            arrow = "▼" if self.is_expanded else "▲"
            self.header_btn.setText(f"{arrow} Comprehension Stack")

        self.content_container.setVisible(self.is_expanded)
        
        # Geometry Logic
        target_h = self.current_height if self.is_expanded else self.collapsed_height
        
        if self.is_expanded and self.button_mode:
            target_w = self.parent().width() - 20
            target_x = 10
        elif self.is_expanded:
            target_w = self.max_width
            target_x = self.closed_x
        else:
            # COLLAPSED STATE
            target_w = self.button_width if self.button_mode else self.max_width
            
            # --- FIX: Force Right Alignment in Button Mode ---
            if self.button_mode:
                # Calculate X dynamically to ensure it stays on the right
                # (Parent Width - Button Width - 10px Margin)
                target_x = self.parent().width() - target_w - 10
            else:
                target_x = self.closed_x

        start_geo = self.geometry()
        new_y = self.anchor_y - target_h
        
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215) 

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(300)
        self.geo_anim.setStartValue(start_geo)
        self.geo_anim.setEndValue(QRect(target_x, new_y, target_w, target_h))
        self.geo_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        if self.is_expanded:
             self.update_sidebar_style(self.button_mode)
             
        self.geo_anim.start()

    def flash_update(self):
        if not self.is_expanded:
            self.header_btn.setStyleSheet("border: none; color: #4a90e2; font-weight: bold; text-align: right;")
            
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
    panel_toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_width = 450 # Standard width
        self.button_width = 80 # Width when collapsed in button mode
        self.setFixedWidth(self.max_width)
        
        self.is_expanded = False
        self.button_mode = False # State flag
        
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
        
        self.list_widget = DeletableListWidget() # Assuming DeletableListWidget is defined
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
        
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anchor_y = 0
        self.closed_x = 0

    def set_button_mode(self, enabled):
        """Called by main window resize event"""
        if self.button_mode == enabled: return
        self.button_mode = enabled
        
        # Immediate update if currently collapsed
        if not self.is_expanded:
            w = self.button_width if enabled else self.max_width
            txt = "Ctx" if enabled else "Context Monitor ▲"
            self.setFixedWidth(w)
            self.header.setText(txt)

    def place_panel(self, x, bottom_y):
        self.anchor_y = bottom_y
        self.closed_x = x # Save the anchor position
        
        h = self.expanded_height if self.is_expanded else self.collapsed_height
        
        # If we are expanded in button mode, we force full width
        if self.is_expanded and self.button_mode:
            parent_w = self.parent().width()
            w = parent_w - 20
            actual_x = 10
        else:
            w = self.max_width if self.is_expanded else (self.button_width if self.button_mode else self.max_width)
            actual_x = x

        self.setGeometry(actual_x, self.anchor_y - h, w, h)

    def toggle(self):
        if self.anchor_y == 0: return
        self.is_expanded = not self.is_expanded
        self.panel_toggled.emit(self.is_expanded) # Emit signal
        
        # Text Logic
        if self.button_mode and not self.is_expanded:
            txt = "Ctx"
        else:
            arrow = "▼" if self.is_expanded else "▲"
            txt = f"Context Monitor {arrow}"
        self.header.setText(txt)

        if self.is_expanded:
            style = self.header.styleSheet()
            self.header.setStyleSheet(style.replace("color: #4a90e2;", "color: #aaa;"))
            
        self.animate_resize()
        
    def animate_resize(self):
        try: self.anim.finished.disconnect(self._hide_finished)
        except: pass

        target_h = self.expanded_height if self.is_expanded else self.collapsed_height
        
        # EXPANSION LOGIC
        if self.is_expanded and self.button_mode:
            target_w = self.parent().width() - 20
            target_x = 10
        elif self.is_expanded:
            target_w = self.max_width
            target_x = self.closed_x
        else:
            target_w = self.button_width if self.button_mode else self.max_width
            target_x = self.closed_x
            
        curr_geo = self.geometry()
        bottom = self.anchor_y 
        new_y = bottom - target_h

        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)

        self.anim.setStartValue(curr_geo)
        self.anim.setEndValue(QRect(target_x, new_y, target_w, target_h))
        
        if self.is_expanded:
            self.content_area.show()
            self.list_widget.scrollToBottom()
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