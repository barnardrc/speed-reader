# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 20:42:08 2026

@author: barna
"""
import sys
import os
import bisect
import socket
from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, 
    QSlider, QHBoxLayout, QProgressBar, QFileDialog,
    QSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QFrame, QMainWindow, QMessageBox
)

# Utils
from utils.dependents import is_raspberry_pi
from utils.style_sheet import DARK_THEME
from utils.text_utils import is_header
from utils.ai import SequentialAIWorker, AIQuestionPanel, EntityPanel
from utils.ai_backend import AIBackendManager
from utils.settings import load_settings, save_settings, PAUSE_CONFIG, complete_first_run
from utils.book_loader import BookLoader

# UI Components
from ui.dialogs import PauseSettingsDialog, AISettingsDialog, FootnoteDialog
from ui.widgets import RSVPWidget, ContextFlowWidget, QueueMonitorWidget
from ui.tutorial import TutorialOverlay # <--- NEW IMPORT

class WordDisplay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.words = []
        self.chapters = []
        self.file_path = ""
        self.is_running = False
        self.index = 0
        self.read_buffer = [] 
        self.entity_buffer = [] 
        self.footnotes = {}

        self.setStyleSheet(DARK_THEME)
        self.settings = load_settings()
        
        # AI
        self.ai_backend = AIBackendManager(self.settings)
        
        # Check Connection
        self.ai_enabled = self.settings.get("ai_enabled", False)
        self.ai_frequency = self.settings.get("ai_frequency", 500) 
        
        self.entity_enabled = self.settings.get("entity_enabled", True)
        self.entity_frequency = self.settings.get("entity_frequency", 300)
    
        is_connected, status_msg = self.ai_backend.check_status()
        
        if (self.ai_enabled or self.entity_enabled) and not is_connected:
            QMessageBox.warning(
                None, 
                "AI Unavailable", 
                f"{status_msg}\n\nAI features will be disabled for this session."
            )
            self.ai_enabled = False
            self.entity_enabled = False
            
        self.wpm = self.settings.get("wpm", 300)
        self.opacity = self.settings.get("opacity", 50)
        self.ctx_range = self.settings.get("context_range", 20)
        self.flank_opacity = self.settings.get("flank_opacity", 60)

        self.delays = {}
        for key in PAUSE_CONFIG: 
            self.delays[key] = self.settings.get(f"{key}_delay", PAUSE_CONFIG[key][0])

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.central_widget.setLayout(self.main_layout)

        # --- Sidebar ---
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.addWidget(QLabel("  Chapters"))
        self.chapter_list = QListWidget()
        self.chapter_list.setFrameShape(QFrame.Shape.NoFrame)
        self.chapter_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chapter_list.itemClicked.connect(self.on_chapter_clicked)
        self.sidebar_layout.addWidget(self.chapter_list)
        self.sidebar.setLayout(self.sidebar_layout)
        self.main_layout.addWidget(self.sidebar)

        # --- Content Area ---
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        
        self.loading_container = QWidget()
        self.loading_layout = QHBoxLayout()
        self.loading_layout.setContentsMargins(0, 0, 0, 0)
        self.loading_label = QLabel("Parsing Book...")
        self.loading_bar = QProgressBar()
        self.loading_bar.setTextVisible(True)
        self.loading_layout.addWidget(self.loading_label)
        self.loading_layout.addWidget(self.loading_bar)
        self.loading_container.setLayout(self.loading_layout)
        self.loading_container.setVisible(False)
        self.content_layout.addWidget(self.loading_container)
        
        # --- Top Bar ---
        top = QHBoxLayout()
        self.btn_open = QPushButton("Open Book")
        self.btn_open.setFixedSize(100, 30)
        self.btn_open.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_open.clicked.connect(self.open_file_dialog)
        top.addWidget(self.btn_open)
        
        self.btn_menu = QPushButton("☰ List")
        self.btn_menu.setFixedSize(80, 30)
        self.btn_menu.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_menu.clicked.connect(self.toggle_sidebar)
        top.addWidget(self.btn_menu)
        
        # Tutorial
        self.btn_help = QPushButton("?")
        self.btn_help.setFixedSize(30, 30)
        self.btn_help.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_help.setToolTip("Replay Tutorial")
        self.btn_help.clicked.connect(self.start_tutorial)
        top.addWidget(self.btn_help)
        top.addStretch()
        
        # Queue Monitor
        self.queue_monitor = QueueMonitorWidget()
        top.addWidget(self.queue_monitor)
        self.content_layout.addLayout(top)
        self.content_layout.addStretch()
        
        # --- RSVP Display ---
        self.display_container = QWidget()
        self.display_layout = QVBoxLayout()
        self.context_display = ContextFlowWidget()
        self.context_display.scrolled.connect(self.on_context_scroll)
        self.display_layout.addWidget(self.context_display, stretch=1)
        self.rsvp_display = RSVPWidget()
        self.rsvp_display.set_flank_opacity(self.flank_opacity)
        self.display_layout.addWidget(self.rsvp_display, stretch=1)
        self.display_container.setLayout(self.display_layout)
        self.content_layout.addWidget(self.display_container, stretch=2) 
        self.content_layout.addStretch()

        self.h_line = QFrame()
        self.h_line.setFrameShape(QFrame.Shape.HLine)
        self.h_line.setFrameShadow(QFrame.Shadow.Sunken)
        self.h_line.setStyleSheet("background-color: #555;")
        self.content_layout.addWidget(self.h_line)

        self.progress_bar = QProgressBar()
        self.content_layout.addWidget(self.progress_bar)

        # --- Navigation Bar ---
        nav = QHBoxLayout()
        nav.addWidget(QLabel("Page:"))
        self.page_spin = QSpinBox()
        self.page_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page_spin.setRange(1, 1)
        self.page_spin.setFixedWidth(60)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.page_spin.editingFinished.connect(self.jump_to_page_input) 
        nav.addWidget(self.page_spin)
        self.lbl_total_pages = QLabel("/ --")
        nav.addWidget(self.lbl_total_pages)
        nav.addSpacing(20)
        nav.addWidget(QLabel("Jump %:"))
        self.pct_spin = QSpinBox()
        self.pct_spin.setRange(0, 100)
        self.pct_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.pct_btn = QPushButton("Go")
        self.pct_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pct_btn.clicked.connect(self.jump_to_percentage)
        nav.addWidget(self.pct_spin)
        nav.addWidget(self.pct_btn)
        nav.addStretch()
        
        # Footnotes Button
        self.btn_footnote = QPushButton("Footnotes")
        self.btn_footnote.setCheckable(True)
        self.btn_footnote.setFixedWidth(80)
        self.btn_footnote.setStyleSheet("""
            QPushButton { color: #555; border: 1px solid #444; border-radius: 3px; }
            QPushButton:checked { background-color: #4a90e2; color: white; border-color: #4a90e2; }
            QPushButton:disabled { background-color: transparent; border-color: #333; color: #333; }
        """)
        self.btn_footnote.clicked.connect(self.toggle_footnote_view)
        self.btn_footnote.setEnabled(False)
        nav.addWidget(self.btn_footnote)
        self.content_layout.addLayout(nav)

        # --- Controls Bar ---
        controls = QHBoxLayout()
        self.speed_controls_layout = controls
        controls.addWidget(QLabel("Speed:"))
        self.wpm_label = QLabel(f"{self.wpm}")
        self.wpm_spin = QSpinBox()
        self.wpm_spin.setRange(60, 1000)
        self.wpm_spin.setValue(self.wpm)
        self.wpm_spin.setFixedWidth(60)
        self.wpm_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.wpm_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wpm_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.wpm_spin.valueChanged.connect(self.update_speed_from_spinbox)
        controls.addWidget(self.wpm_spin)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(60, 1000)
        self.slider.setValue(self.wpm)
        self.slider.setMinimumWidth(80) # Prevent collapse
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.valueChanged.connect(self.update_speed_from_slider)
        controls.addWidget(self.slider, stretch=1) # Allow expansion
        controls.addSpacing(10)
        self.display_controls_container = QWidget()
        dc_layout = QHBoxLayout()
        dc_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Context Slider
        dc_layout.addWidget(QLabel("Context:"))
        self.op_slider = QSlider(Qt.Orientation.Horizontal)
        self.op_slider.setRange(0, 100)
        self.op_slider.setValue(self.opacity)
        self.op_slider.setMinimumWidth(80) # Prevent collapse
        self.op_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.op_slider.valueChanged.connect(self.update_opacity)
        dc_layout.addWidget(self.op_slider, stretch=1)
        dc_layout.addSpacing(15)

        # 2. Flank Slider
        dc_layout.addWidget(QLabel("Flank:"))
        self.flank_slider = QSlider(Qt.Orientation.Horizontal)
        self.flank_slider.setRange(0, 255)
        self.flank_slider.setValue(self.flank_opacity)
        self.flank_slider.setMinimumWidth(80) # Prevent collapse
        self.flank_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.flank_slider.valueChanged.connect(self.update_flank_opacity)
        dc_layout.addWidget(self.flank_slider, stretch=1)
        dc_layout.addSpacing(15)

        # 3. Range Slider
        dc_layout.addWidget(QLabel("Range:"))
        self.ctx_slider = QSlider(Qt.Orientation.Horizontal)
        self.ctx_slider.setRange(5, 100)
        self.ctx_slider.setValue(self.ctx_range)
        self.ctx_slider.setMinimumWidth(80) # Prevent collapse
        self.ctx_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ctx_slider.valueChanged.connect(self.update_ctx_range)
        dc_layout.addWidget(self.ctx_slider, stretch=1)        
        self.display_controls_container.setLayout(dc_layout)
        controls.addWidget(self.display_controls_container, stretch=3)        
        controls.addSpacing(10)        
        self.btn_pauses = QPushButton("Pauses")
        self.btn_pauses.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_pauses.clicked.connect(self.open_pause_settings)
        controls.addWidget(self.btn_pauses)
        self.btn_ai_settings = QPushButton("AI Settings")
        self.btn_ai_settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_ai_settings.clicked.connect(self.open_ai_settings)
        controls.addWidget(self.btn_ai_settings)
        self.content_layout.addLayout(controls)        
        self.content_widget.setLayout(self.content_layout)
        self.main_layout.addWidget(self.content_widget)
        
        # --- AI & Workers ---
        self.ai_worker = SequentialAIWorker(self.ai_backend)
        self.ai_worker.result_ready.connect(self.route_ai_response) 
        self.ai_worker.error_occurred.connect(lambda e: print(f"AI Error: {e}"))
        
        # Queue Monitor connections
        self.ai_worker.queue_updated.connect(self.queue_monitor.update_queue_list)
        self.ai_worker.processing_started.connect(self.queue_monitor.set_processing)
        self.ai_worker.processing_finished.connect(self.queue_monitor.set_idle)        
        self.ai_worker.start()         
        self.ai_panel = AIQuestionPanel(self.central_widget)
        self.entity_panel = EntityPanel(self.central_widget)
        
        if not self.ai_enabled: self.ai_panel.hide()
        if not self.entity_enabled: self.entity_panel.hide()
        else: self.entity_panel.show()
        
        self.ai_panel.submit_task_signal.connect(self.ai_worker.add_task)
        
        self.resize(1200, 800)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_next_word)
        self.setFocus()

        # --- TUTORIAL CHECK ---
        if self.settings.get("first_run", False):
            # Wait for full render
            QTimer.singleShot(500, self.start_tutorial)

    def start_tutorial(self):
        # Prevent multiple instances
        if hasattr(self, 'tutorial') and self.tutorial.isVisible():
            return

        steps = [
            (self.btn_open, "Start here! Click 'Open Book' to load an EPUB or PDF."),
            (self.sidebar, "This sidebar displays chapters. Click any chapter to jump directly to it."),
            (self.btn_menu, "Need more space? Click 'List' to toggle the chapter sidebar visibility."),
            (self.queue_monitor, "This is the AI Queue Monitor. It provides extra information about when AI is processing requests."),
            (self.page_spin, "Know the exact page? Type it here to jump instantly."),
            (self.pct_btn, "Or use the percentage jump to navigate through the book."),
            (self.btn_footnote, "If a page has footnotes, this button lights up. Click to read them without losing your place."),
            (self.slider, "Speed Control (WPM). Use Up/Down arrow keys while reading to adjust this on the fly."),
            (self.display_controls_container, "Customize your view.\nContext: Context visibility.\nFlank: Side-word visibility.\nRange: How much context to show."),
            (self.btn_pauses, "Smart Pauses: Configure how long the reader pauses on commas, periods, and headers."),
            (self.btn_ai_settings, "Configure your local LLM (Ollama) or adjust how often the AI reads the text for context."),
            (None, "HOTKEYS") # Triggers the graphical hotkey layout
        ]
        
        self.tutorial = TutorialOverlay(self.central_widget, steps)
        self.tutorial.finished.connect(self.on_tutorial_finished)
        self.tutorial.show()

    def on_tutorial_finished(self):
        complete_first_run()
        QMessageBox.information(self, "Ready", "You're all set! Open a book and press SPACE to start reading.")

    def update_overlay_positions(self):
        """Recalculates positions for the floating panels based on current layout."""
        if not hasattr(self, 'h_line'): return

        # Unfortunatate code smell
        VISUAL_MARGIN = 30
        
        line_pos = self.h_line.mapTo(self.central_widget, QPoint(0,0))
        global_line_pos = self.h_line.mapToGlobal(QPoint(0,0))
        
        # AI Panel 
        if hasattr(self, 'ai_panel'):
            pw = self.ai_panel.width()
            # Align right edge of panel with right end of separator line
            target_x = self.central_widget.width() - pw - VISUAL_MARGIN
            self.ai_panel.place_panel(target_x, line_pos.y(), global_line_pos.y())
        
        # Entity Panel
        if hasattr(self, 'entity_panel'):
            content_start_x = self.sidebar.width() if self.sidebar.isVisible() else 0
            target_x = content_start_x + VISUAL_MARGIN
            
            self.entity_panel.place_panel(target_x, line_pos.y())
    
    def on_context_scroll(self, step):
        if self.is_running:
            self.toggle_reading()

        new_index = self.index + step

        if 0 <= new_index < len(self.words):
            self.index = new_index
            
            self.update_display_manual()
    
    def route_ai_response(self, response, metadata):
        task_type = metadata.get("type")
        
        if task_type == "QUESTION":
            context_text = metadata.get("context", "")
            self.ai_panel.add_question(response, context_text)
            
        elif task_type == "ENTITY":
            self.entity_panel.add_entities(response)
    
        elif task_type == "CHECK_ANSWER":
            tab_id = metadata.get("tab_id")
            self.ai_panel.deliver_feedback(tab_id, response)
    
    def resizeEvent(self, event):
        self.update_overlay_positions()
        
        if hasattr(self, 'tutorial') and self.tutorial.isVisible():
            self.tutorial.setGeometry(self.central_widget.rect())
            self.tutorial.center_msg_box()
            
        super().resizeEvent(event)
    
    def toggle_sidebar(self):
        new_state = not self.sidebar.isVisible()
        self.sidebar.setVisible(new_state)
        
        QTimer.singleShot(0, self.update_overlay_positions)
    
    def open_file_dialog(self):
        if self.file_path: self.persist_state()
        if self.is_running: self.toggle_reading()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Book", "", "Books (*.epub *.pdf);;EPUB Files (*.epub);;PDF Files (*.pdf)")
        if file_path: self.load_book(os.path.abspath(file_path))

    def load_book(self, file_path):
        print(f"Loading: {file_path}")
        self.loading_bar.setValue(0)
        self.loading_label.setText(f"Loading {os.path.basename(file_path)}...")
        self.loading_container.setVisible(True)
        self.central_widget.setEnabled(False)
        self.loader_thread = BookLoader(file_path)
        self.loader_thread.progress_updated.connect(self.loading_bar.setValue)
        self.loader_thread.finished_loading.connect(lambda w, c, p, f: self.on_book_loaded(w, c, p, f, file_path))
        self.loader_thread.error_occurred.connect(lambda e: QMessageBox.critical(self, "Error", f"Failed: {e}"))
        self.loader_thread.finished.connect(self.reset_loading_ui)
        self.loader_thread.start()

    def reset_loading_ui(self):
        self.loading_container.setVisible(False)
        self.central_widget.setEnabled(True)
        self.setFocus()

    def on_book_loaded(self, words, chapters, page_map, footnotes, file_path):
        if not words:
            QMessageBox.critical(self, "Error", "Book is empty.")
            return
        self.words = words
        self.chapters = chapters
        self.page_map = page_map
        self.footnotes = footnotes
        self.file_path = file_path
    
        if self.page_map:
            self.page_nums = sorted(self.page_map.keys())
            self.page_starts = [self.page_map[p] for p in self.page_nums]
            self.page_spin.setRange(1, self.page_nums[-1])
            self.lbl_total_pages.setText(f"/ {self.page_nums[-1]}")
            self.page_spin.setEnabled(True)
        else:
            # EPUB or failed mapping
            self.page_nums = []
            self.page_starts = []
            self.page_spin.setRange(0, 0)
            self.lbl_total_pages.setText("/ --")
            self.page_spin.setEnabled(False)

        self.read_buffer = [] 
        self.entity_buffer = []
        saved_index = self.settings.get("books", {}).get(self.file_path, 0)
        self.index = min(saved_index, len(self.words) - 1)
        
        # Update Lists
        self.chapter_list.clear()
        for title, idx in self.chapters:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.chapter_list.addItem(item)
            
        self.progress_bar.setRange(0, len(self.words))
        self.progress_bar.setValue(self.index)
        self.rsvp_display.set_status(False)
        self.update_display_manual()
        self.highlight_current_chapter()

    def open_pause_settings(self):
        was_running = self.is_running
        if was_running: self.toggle_reading()
        
        # Pass PAUSE_CONFIG
        dlg = PauseSettingsDialog(self.settings, PAUSE_CONFIG, self)
        
        if dlg.exec():
            vals = dlg.get_values()
            self.settings.update(vals)
            for key in PAUSE_CONFIG: 
                self.delays[key] = vals[f"{key}_delay"]
            save_settings(self.settings)
        
        self.setFocus()
        
    def open_ai_settings(self):
        if self.is_running:
            self.toggle_reading()

        dlg = AISettingsDialog(self.settings, self.ai_backend, self)
        if dlg.exec():
            new_vals = dlg.get_values()
            
            # Update Local State
            self.ai_enabled = new_vals["ai_enabled"]
            self.ai_frequency = new_vals["ai_frequency"]
            self.entity_enabled = new_vals["entity_enabled"]
            
            # Update Backend Model
            selected_model = new_vals.get("selected_model")
            if selected_model:
                self.ai_backend.set_model(selected_model)

            # Toggle Panels
            if not self.ai_enabled: self.ai_panel.hide()
            else: self.ai_panel.show()
            
            if not self.entity_enabled: self.entity_panel.hide()
            else: self.entity_panel.show()
            
            # Save Settings
            self.settings.update(new_vals)
            self.settings["ai_model"] = selected_model
            save_settings(self.settings)
            
        self.setFocus()

    def update_opacity(self):
        self.opacity = self.op_slider.value()
        self.update_context_view()
        self.setFocus()

    def update_flank_opacity(self):
        self.flank_opacity = self.flank_slider.value()
        self.rsvp_display.set_flank_opacity(self.flank_opacity)
        self.setFocus()

    def update_ctx_range(self):
        self.ctx_range = self.ctx_slider.value()
        self.update_context_view()
        self.setFocus()
        
    def update_ai_config(self):
        self.ai_enabled = self.settings.get("ai_enabled", False)
        self.ai_frequency = self.settings.get("ai_frequency", 500)
        self.entity_enabled = self.settings.get("entity_enabled", True)
        
        if not self.ai_enabled:
            self.read_buffer = []
            self.ai_panel.hide()
        
        if not self.entity_enabled:
            self.entity_buffer = []
            self.entity_panel.hide()
        else:
            self.entity_panel.show()

    def find_sentence_bounds(self):
        s_start = self.index
        limit = 100 
        i = self.index - 1
        count = 0
        while i >= 0 and count < limit:
            w = self.words[i]
            if w and w[-1] in ['.', '?', '!']:
                s_start = i + 1
                break
            if i == 0: s_start = 0
            i -= 1
            count += 1
        s_end = self.index
        i = self.index
        count = 0
        while i < len(self.words) and count < limit:
            w = self.words[i]
            if w and w[-1] in ['.', '?', '!']:
                s_end = i
                break
            i += 1
            count += 1
        return s_start, s_end

    def update_context_view(self):
        if not self.words: return
        s_start, s_end = self.find_sentence_bounds()
        self.context_display.set_data(
            self.words, self.index, self.ctx_range, self.opacity, s_start, s_end
        )

    def on_chapter_clicked(self, item):
        self.index = item.data(Qt.ItemDataRole.UserRole)
        self.read_buffer = [] 
        self.entity_buffer = []
        self.update_display_manual()
        if self.is_running: self.schedule_next_word()
        self.setFocus()

    def keyPressEvent(self, e):
        if not self.words: return
        if e.key() == Qt.Key.Key_Space: self.toggle_reading()
        elif e.key() == Qt.Key.Key_Left: self.skip_words(-10)
        elif e.key() == Qt.Key.Key_Right: self.skip_words(10)
        elif e.key() == Qt.Key.Key_Up: self.change_speed(25)
        elif e.key() == Qt.Key.Key_Down: self.change_speed(-25)
        else: super().keyPressEvent(e)

    def skip_words(self, count):
        self.index = max(0, min(len(self.words) - 1, self.index + count))
        self.read_buffer = [] 
        self.entity_buffer = []
        self.update_display_manual()
        self.highlight_current_chapter()

    def change_speed(self, delta):
        """Called by Up/Down Arrow Keys"""
        new_wpm = self.wpm + delta
        new_wpm = max(self.slider.minimum(), min(self.slider.maximum(), new_wpm))
        self.slider.setValue(new_wpm)

    def mousePressEvent(self, e):
        ignore_widgets = [
            self.slider, self.op_slider, self.flank_slider, self.ctx_slider, 
            self.pct_btn, self.pct_spin, self.btn_pauses, self.btn_ai_settings,
            self.wpm_spin
        ]
        
        click_pos = self.mapFromGlobal(e.globalPosition().toPoint())
        if self.ai_panel.isVisible() and self.ai_panel.geometry().contains(click_pos): pass 
        elif self.entity_panel.isVisible() and self.entity_panel.geometry().contains(click_pos): pass
        elif self.childAt(e.pos()) not in ignore_widgets:
            self.setFocus()
            self.toggle_reading()

    def closeEvent(self, e):
        self.persist_state()
        
        if hasattr(self, 'ai_worker'):
            self.ai_worker.stop()
            self.ai_worker.wait(2000)
            
        e.accept()

    def persist_state(self):
        if not self.file_path: return
        self.settings["wpm"] = self.wpm
        self.settings["opacity"] = self.opacity
        self.settings["context_range"] = self.ctx_range
        self.settings["flank_opacity"] = self.flank_opacity
        self.settings["ai_enabled"] = self.ai_enabled
        self.settings["ai_frequency"] = self.ai_frequency
        self.settings["entity_enabled"] = self.entity_enabled
        self.settings["entity_frequency"] = self.entity_frequency
        if "books" not in self.settings: self.settings["books"] = {}
        self.settings["books"][self.file_path] = self.index
        save_settings(self.settings)

    def toggle_reading(self):
        self.setFocus()
        if not self.words: return
        
        if self.is_running:
            # STOPPING
            self.timer.stop()
            self.is_running = False
            self.rsvp_display.set_status(False) # Turn Red
            self.persist_state()
        else:
            # STARTING
            self.is_running = True
            self.rsvp_display.set_status(True)  # Turn Green
            self.schedule_next_word()

    def update_speed_from_slider(self):
        """Called when user drags the slider"""
        self.wpm = self.slider.value()
        self.wpm_spin.blockSignals(True)
        self.wpm_spin.setValue(self.wpm)
        self.wpm_spin.blockSignals(False)
    
    def update_speed_from_spinbox(self):
        """Called when user types in the box"""
        self.wpm = self.wpm_spin.value()
        self.slider.blockSignals(True)
        self.slider.setValue(self.wpm)
        self.slider.blockSignals(False)
    
    def jump_to_percentage(self):
        if not self.words: return
        self.index = int((self.pct_spin.value() / 100) * len(self.words))
        self.read_buffer = []
        self.entity_buffer = []
        self.update_display_manual()
        self.highlight_current_chapter()
        self.setFocus()
    
    def jump_to_page_input(self):
        if not self.words or not self.page_map: return
        
        target_page = self.page_spin.value()
        if target_page in self.page_map:
            self.index = self.page_map[target_page]
            self.read_buffer = []
            self.entity_buffer = []
            self.update_display_manual()
            self.highlight_current_chapter()
            self.setFocus()
    
    def update_page_display_ui(self):
        if not self.page_map or not self.page_starts: return
        
        idx = bisect.bisect_right(self.page_starts, self.index)
        if idx > 0:
            current_page = self.page_nums[idx - 1]
            
            if self.page_spin.value() != current_page:
                self.page_spin.blockSignals(True)
                self.page_spin.setValue(current_page)
                self.page_spin.blockSignals(False)

            if current_page in self.footnotes:
                self.btn_footnote.setEnabled(True)
                self.btn_footnote.setStyleSheet("""
                    QPushButton { color: #ccc; border: 1px solid #888; border-radius: 3px; }
                    QPushButton:hover { border-color: #4a90e2; color: #4a90e2; }
                """)
                self.btn_footnote.setText("Footnote *")
            else:
                self.btn_footnote.setEnabled(False)
                self.btn_footnote.setStyleSheet("color: #333; border: 1px solid #333;")
                self.btn_footnote.setText("Footnote")
    
    def toggle_footnote_view(self):
        # Pause reading to view
        if self.is_running:
            self.toggle_reading()
            
        current_page = self.page_spin.value()
        content = self.footnotes.get(current_page, "No footnotes for this page.")
        
        # Use the modular dialog
        dlg = FootnoteDialog(current_page, content, self)
        dlg.exec()
        
        self.btn_footnote.setChecked(False) # Uncheck button after closing
        self.setFocus() # Return focus to main window
    
    def highlight_current_chapter(self):
        if not self.chapters: return
        r = 0
        for i, (t, s) in enumerate(self.chapters):
            if s <= self.index: r = i
            else: break
        self.chapter_list.setCurrentRow(r)

    def update_display_manual(self):
        if self.words and self.index < len(self.words):
            current = self.words[self.index]
            prev_w = self.words[self.index - 1] if self.index > 0 else ""
            next_w = self.words[self.index + 1] if self.index < len(self.words) - 1 else ""
            self.rsvp_display.set_word(current, prev_w, next_w)
            self.progress_bar.setValue(self.index)
            self.update_context_view()
            self.update_page_display_ui()

    def schedule_next_word(self):
        if not self.is_running: return
        base_ms = int(60000 / self.wpm)
        multiplier = 1.0
        
        if self.words and self.index < len(self.words):
            current_word = self.words[self.index]
            clean_word = current_word.rstrip('"\'”’)]}')
            last_char = clean_word[-1] if clean_word else ""
            
            # Priority checks
            if is_header(current_word): 
                multiplier = self.delays['header']
            elif '...' in current_word or '…' in current_word: 
                multiplier = self.delays['ellipsis']
            elif '—' in clean_word: 
                multiplier = self.delays['long_hyphen']
            elif '(' in current_word or ')' in current_word: 
                multiplier = self.delays['parens']
            elif last_char in ['.', '?', '!']: 
                multiplier = self.delays['period']
            elif last_char in [',', ':', ';']: 
                multiplier = self.delays['comma']
            elif '-' in current_word: 
                multiplier = self.delays['hyphen']
                
        actual_delay = int(base_ms * multiplier)
        self.timer.start(actual_delay)

    def trigger_background_ai(self):
        max_ctx = self.ai_backend.max_context_length
        overlap = self.ai_backend.comprehension_overlap

        text_chunk = " ".join(self.read_buffer[-max_ctx:])
        
        if len(self.read_buffer) > overlap:
            self.read_buffer = self.read_buffer[-overlap:]
        else:
            self.read_buffer = []
        
        prompt = (
            f"Text Chunk: \n\"{text_chunk}\"\n\n"
            f"Task: Generate one concise reading comprehension question based on the text above.\n\n"
            f"Requirements:\n"
            f"1. Priority: Test the reader's understanding of the central idea, cause-and-effect, or the logic behind the passage.\n"
            f"2. Fallback: If the text is purely informational, ask about a significant factual detail.\n"
            f"3. Constraint: Avoid asking for direct quotes or trivial formatting details. The question should require the reader to have actually processed the meaning of the text.\n"
            f"4. Format: Provide only the question. Do not provide the answer."
        )
        
        metadata = {
            "type": "QUESTION",
            "context": text_chunk
        }
        
        self.ai_worker.add_task(prompt, metadata)

    def trigger_entity_check(self):
        full_context = " ".join(self.entity_buffer)
        
        prompt = (
            f"Analyze the text below. Extract ONLY:\n"
            f"1. Important People (Specific Named Characters)\n"
            f"2. Important Dates or Years\n\n"
            f"For each, provide a brief summary of their significance in this specific text. Use ONLY information from the context.\n"
            f"Format: 'Name/Date - Significance'\n"
            f"Constraints:\n"
            f"- EXCLUDE Section Headers, Chapter Titles, Locations, and generic nouns.\n"
            f"- If the entity is mentioned but has no significance here, ignore it.\n"
            f"- If NO People or Dates are found, output exactly: 'None'.\n\n"
            f"Text: {full_context}"
        )
        
        metadata = {
            "type": "ENTITY",
            "context": full_context
        }
        
        self.ai_worker.add_task(prompt, metadata)

        overlap = self.ai_backend.entity_overlap
        self.entity_buffer = self.entity_buffer[-overlap:]
        
    def on_ai_question_ready(self, question, context_text):
        self.ai_panel.add_question(question, context_text)

    def on_entity_ready(self, response, _):
        if "None" not in response: self.entity_panel.add_entities(response)

    def show_next_word(self):
        self.index += 1
        if self.index < len(self.words):
            current = self.words[self.index]
            prev_w = self.words[self.index - 1] if self.index > 0 else ""
            next_w = self.words[self.index + 1] if self.index < len(self.words) - 1 else ""
            self.rsvp_display.set_word(current, prev_w, next_w)
            self.progress_bar.setValue(self.index)
            self.update_context_view()
            self.update_page_display_ui()
            
            if self.ai_enabled:
                self.read_buffer.append(current)
                if len(self.read_buffer) >= self.ai_frequency:
                    if current.rstrip('"\'”’)]}').endswith(('.', '?', '!')):
                        self.trigger_background_ai()
            
            if self.entity_enabled:
                self.entity_buffer.append(current)
                if len(self.entity_buffer) >= self.entity_frequency:
                    self.trigger_entity_check()
            
            self.schedule_next_word()
        else:
            self.rsvp_display.set_word("Finished", "", "")
            self.is_running = False
            self.rsvp_display.set_status(False)
            self.persist_state()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WordDisplay()
    
    if is_raspberry_pi():
        window.showFullScreen()
    else:
        window.show()
        
    sys.exit(app.exec())