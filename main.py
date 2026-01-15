# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 20:42:08 2026

@author: barna
"""
import sys
import os
import bisect
from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, 
    QHBoxLayout, QProgressBar, QFileDialog,
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
from utils.eye_tracking.camera_worker import EyeTrackingWorker

# UI Components
from ui.dialogs import PauseSettingsDialog, AISettingsDialog, FootnoteDialog
from ui.widgets import RSVPWidget, ContextFlowWidget, QueueMonitorWidget, ControlBar
from ui.tutorial import TutorialOverlay 

class WordDisplay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.words = []
        self.chapters = []
        self.file_path = ""
        self.is_running = False
        self.is_gaze_paused = False
        self.calibration_requested = False
        self.debug_window = None
        self.eye_worker = None
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
        # Ensure it has a background so text underneath doesn't show through in overlay mode
        self.sidebar.setStyleSheet("background-color: #2b2b2b; border-right: 1px solid #444;")
        
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setContentsMargins(5, 10, 5, 5) # Add margins
        
        # -- Sidebar Header --
        sidebar_header = QHBoxLayout()
        lbl_chap = QLabel("  Chapters")
        lbl_chap.setStyleSheet("font-weight: bold; color: #aaa;")
        sidebar_header.addWidget(lbl_chap)
        
        sidebar_header.addStretch()
        
        # The new Close Button
        self.btn_close_sidebar = QPushButton("✕")
        self.btn_close_sidebar.setFixedSize(30, 30)
        self.btn_close_sidebar.setStyleSheet("color: #aaa; border: none; font-weight: bold;")
        self.btn_close_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_sidebar.clicked.connect(self.toggle_sidebar)
        sidebar_header.addWidget(self.btn_close_sidebar)
        
        self.sidebar_layout.addLayout(sidebar_header)
        # --------------------

        self.chapter_list = QListWidget()
        self.chapter_list.setFrameShape(QFrame.Shape.NoFrame)
        self.chapter_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chapter_list.setStyleSheet("background: transparent;") # Match new background
        self.chapter_list.itemClicked.connect(self.on_chapter_clicked)
        self.sidebar_layout.addWidget(self.chapter_list)
        self.btn_exit = QPushButton("Quit Application")
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #3e3e3e; 
                color: #ff6b6b; 
                border: 1px solid #555; 
                padding: 8px; 
                border-radius: 4px;
                font-weight: bold;
                margin-top: 5px;
            }
            QPushButton:hover { 
                background-color: #c62828; 
                color: white; 
                border-color: #c62828;
            }
        """)
        self.btn_exit.clicked.connect(self.close)
        self.sidebar_layout.addWidget(self.btn_exit)
        self.sidebar.setLayout(self.sidebar_layout)
        self.sidebar.hide()

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
        self.btn_open = QPushButton("Open")
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

        # --- MODIFICATION START ---
        # Insert a strong spacer here to push the RSVP widget to the bottom.
        # This creates the physical gap needed for the eye tracker to distinct 
        # between looking "UP" (Context) and looking "DOWN" (Reading).
        if is_raspberry_pi():
            self.display_layout.addStretch(5) 
        # --------------------------

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
        self.controls = ControlBar(self.settings)
        
        # Connect Signals
        self.controls.wpm_changed.connect(self.set_wpm) # Helper method below
        self.controls.pause_settings_clicked.connect(self.open_pause_settings)
        self.controls.ai_settings_clicked.connect(self.open_ai_settings)
        
        self.controls.opacity_changed.connect(lambda v: self.set_visual_setting('opacity', v, self.update_context_view))
        self.controls.flank_changed.connect(lambda v: self.set_visual_setting('flank_opacity', v, lambda: self.rsvp_display.set_flank_opacity(v)))
        self.controls.ctx_range_changed.connect(lambda v: self.set_visual_setting('ctx_range', v, self.update_context_view))
        
        self.content_layout.addWidget(self.controls)
        
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
        
        if is_raspberry_pi():
            from ui.widgets import CameraIndicator
            self.cam_indicator = CameraIndicator(self.central_widget)
            self.cam_indicator.show()
            self.cam_indicator.raise_()
            self.cam_indicator.clicked.connect(self.toggle_debug_window)
            self.start_eye_tracking()
        
        self.ai_panel.submit_task_signal.connect(self.ai_worker.add_task)
        
        # Connect Exclusivity Logic
        self.ai_panel.panel_toggled.connect(self.on_ai_toggled)
        self.entity_panel.panel_toggled.connect(self.on_entity_toggled)
        
        self.resize(1200, 800)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_next_word)
        self.setFocus()
        
        # --- TUTORIAL CHECK ---
        if self.settings.get("first_run", False):
            # Wait for full render
            QTimer.singleShot(500, self.start_tutorial)
    
    def check_sidebar_mode(self):
        is_small = self.width() < 750
        is_in_layout = self.main_layout.indexOf(self.sidebar) != -1

        if is_small:
            # SWITCH TO OVERLAY MODE
            if is_in_layout:
                self.main_layout.removeWidget(self.sidebar)
                self.sidebar.setParent(self.central_widget) # Float it
            
            # Force geometry to cover left side
            if self.sidebar.isVisible():
                self.sidebar.setGeometry(0, 0, 200, self.height())
                self.sidebar.raise_() # Ensure it sits on top of content
                
        else:
            # SWITCH TO LAYOUT MODE
            if not is_in_layout:
                # Add to index 0 (left side)
                self.main_layout.insertWidget(0, self.sidebar) 
                
            # Reset geometry so layout takes control
            self.sidebar.resize(200, self.sidebar.height())
    
    def set_wpm(self, value):
        self.wpm = value
        
    def set_visual_setting(self, attr_name, value, callback=None):
        setattr(self, attr_name, value)
        if callback: callback()
        
    def on_ai_toggled(self, is_open):
        if is_open and self.entity_panel.is_expanded:
            self.entity_panel.collapse()

    def on_entity_toggled(self, is_open):
        if is_open and self.ai_panel.is_expanded:
            self.ai_panel.collapse()    
    
    def start_tutorial(self):
        if hasattr(self, 'tutorial') and self.tutorial.isVisible():
            return
        
        if self.controls.visual_frame.isVisible():
            visual_target = self.controls.visual_frame
        else:
            visual_target = self.controls.btn_visuals

        steps = [
            (self.btn_open, "Start here! Click 'Open Book' to load an EPUB or PDF."),
            (self.btn_menu, "Click 'List' to open the sidebar. Use it to jump to specific chapters or quit the application."),
            (self.queue_monitor, "This is the AI Queue Monitor. It shows when the AI is reading or thinking."),
            (self.page_spin, "Know the exact page? Type it here to jump instantly."),
            (self.pct_btn, "Or use the percentage jump to navigate through the book."),
            (self.btn_footnote, "If a page has footnotes, this button lights up. Click to read them."),
            (self.controls.wpm_slider, "Speed Control (WPM)."),
            (visual_target, "Customize your view.\nAdjust Context, Flank words, and Range visibility here."),
            (self.controls.btn_pauses, "Smart Pauses: Configure how long the reader pauses on commas, periods, and headers."),
            (self.controls.btn_ai, "Configure your local LLM (Ollama) or adjust how often the AI reads the text."),
        ]
        
        self.eye_worker = None
        
        if is_raspberry_pi():
            steps.append((self.rsvp_display, "Tap anywhere in this area to Play or Pause reading."))
            steps.append((self.rsvp_display, "EYE_CALIB"))
            
            # Step C: Eye Tracking Test
            steps.append((self.context_display, "EYE_TEST"))
                
        else:
            steps.append((None, "HOTKEYS"))
        
        self.tutorial = TutorialOverlay(self.central_widget, steps)
        
        self.tutorial.setGeometry(self.central_widget.rect()) 
        
        self.tutorial.finished.connect(self.on_tutorial_finished)
        self.tutorial.show()
    
    def start_eye_tracking(self):
        # Prevent starting multiple workers
        if self.eye_worker is not None and self.eye_worker.isRunning():
            return

        print("Starting Eye Tracking...")
        self.eye_worker = EyeTrackingWorker()
        self.eye_worker.update_signal.connect(self.on_eye_data)
        self.eye_worker.start()

    def on_eye_data(self, frame, avg_ratio, eyes_off, limit_ratio):
        """
        Received fresh data from the background thread.
        This runs on the Main UI Thread, so update widgets here.
        """
        # 1. Ping Indicator
        if hasattr(self, 'cam_indicator'):
            self.cam_indicator.ping()

        # 2. Handle Calibration Request
        if self.calibration_requested and avg_ratio is not None:
            self.eye_worker.calibrate(avg_ratio)
            self.calibration_requested = False
            
            # --- FIX STARTS HERE ---
            # We just calibrated. The 'eyes_off' variable passed to this function 
            # was calculated using the OLD calibration (or no calibration).
            # We must override it to False, otherwise the app will immediately 
            # switch to "Gaze Paused" (Orange) before the new calibration takes effect.
            eyes_off = False 
            # --- FIX ENDS HERE ---

            # Tutorial Auto-Advance
            if hasattr(self, 'tutorial') and self.tutorial.isVisible():
                current_msg = self.tutorial.steps[self.tutorial.current_step][1]
                if current_msg == "EYE_CALIB":
                    self.tutorial.next_step()
                    if self.is_running: self.toggle_reading()

        # 3. Update Debug Window
        if self.debug_window and self.debug_window.isVisible():
            self.debug_window.update_frame(frame, avg_ratio, limit_ratio, eyes_off)

        # 4. Logic Control (Pause/Resume)
        if eyes_off:
            if not self.is_gaze_paused:
                self.is_gaze_paused = True
                self.rsvp_display.set_status(2) # Orange
        else:
            # If we are running but paused by gaze, resume now
            if self.is_running and self.is_gaze_paused:
                self.is_gaze_paused = False
                self.rsvp_display.set_status(1) # Green
                self.schedule_next_word()
    
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
        
        if hasattr(self, 'ai_panel'):
            pw = self.ai_panel.width()
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
        self.check_sidebar_mode()
        width = self.width()
        is_compact = width < 1250
        
        if hasattr(self, 'cam_indicator'):
            self.cam_indicator.move(self.width() - 25, 5)
            self.cam_indicator.raise_()
        
        if hasattr(self, 'ai_panel'):
            self.ai_panel.set_button_mode(is_compact)
            
        if hasattr(self, 'entity_panel'):
            self.entity_panel.set_button_mode(is_compact)
            
        self.update_overlay_positions()
        
        if hasattr(self, 'tutorial') and self.tutorial.isVisible():
            self.tutorial.setGeometry(self.central_widget.rect())
            self.tutorial.center_msg_box()

        super().resizeEvent(event)
    
    def toggle_sidebar(self):
        was_fullscreen = self.isFullScreen()
        new_state = not self.sidebar.isVisible()
        self.sidebar.setVisible(new_state)
        
        if new_state and self.width() < 750:
            self.sidebar.raise_()
            self.sidebar.setGeometry(0, 0, 200, self.height())

        if was_fullscreen:
            self.showFullScreen()
            
        QTimer.singleShot(0, self.update_overlay_positions)
    
    def open_file_dialog(self):
         # 1. PAUSE CAMERA (Crucial!)
         # Stop the update loop so it doesn't fight the dialog for resources
         was_tracking = False
         if self.eye_worker and self.eye_worker.isRunning():
            self.eye_worker.stop()
            self.eye_worker.wait() # FIX: Wait for thread to finish and release camera
            was_tracking = True
 
         # 2. Capture state
         self.intended_fullscreen = self.isFullScreen()
         if self.file_path: self.persist_state()
         if self.is_running: self.toggle_reading()
         
         # 3. Open Dialog with "DontUseNativeDialog"
         # This prevents the OS window manager from creating a separate window surface
         # which often causes the "ghost window" bug on Pi/Linux.
         file_path, _ = QFileDialog.getOpenFileName(
             self, 
             "Open Book", 
             "", 
             "Books (*.epub *.pdf);;EPUB Files (*.epub);;PDF Files (*.pdf)",
             options=QFileDialog.Option.DontUseNativeDialog
         )
         
         # 4. Restore Fullscreen immediately to prevent flickering
         if self.intended_fullscreen:
             self.showFullScreen()
 
         # 5. Load Book if selected
         if file_path: 
             self.load_book(os.path.abspath(file_path))
             
         # 6. RESUME CAMERA
         if was_tracking:
            self.start_eye_tracking()

    def load_book(self, file_path):
        print(f"Loading: {file_path}")
        self.loading_bar.setValue(0)
        self.loading_label.setText(f"Loading {os.path.basename(file_path)}...")
        self.loading_container.setVisible(True)
        self.loader_thread = BookLoader(file_path)
        self.loader_thread.progress_updated.connect(self.loading_bar.setValue)
        self.loader_thread.finished_loading.connect(lambda w, c, p, f: self.on_book_loaded(w, c, p, f, file_path))
        self.loader_thread.error_occurred.connect(lambda e: QMessageBox.critical(self, "Error", f"Failed: {e}"))
        self.loader_thread.finished.connect(self.reset_loading_ui)
        self.loader_thread.start()

    def reset_loading_ui(self):
        self.loading_container.setVisible(False)
        self.setFocus()
        
        if getattr(self, 'intended_fullscreen', False):
            self.showFullScreen()

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
        
        # window size debug line:
        print(self.size())
        
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
        
        # FIX: Auto-close sidebar on mobile/overlay mode
        if self.width() < 750:
             self.toggle_sidebar()
             
        self.setFocus()
    
    def toggle_debug_window(self):
        if not is_raspberry_pi(): return

        if self.debug_window is None:
            from ui.debug_window import CameraDebugWindow
            self.debug_window = CameraDebugWindow(self)

        if self.debug_window.isVisible():
            self.debug_window.hide()
        else:
            self.debug_window.show()
    
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
        if hasattr(self.controls, 'wpm_slider'):
             self.controls.wpm_slider.setValue(new_wpm)

    def mousePressEvent(self, e):
        # Get the actual widget under the mouse cursor
        widget = QApplication.widgetAt(e.globalPosition().toPoint())
        
        # Traverse up the widget hierarchy to check if we clicked a control
        current = widget
        while current:
            if current in [self.controls, self.ai_panel, self.entity_panel, self.sidebar]:
                return # Click was inside a control panel; ignore it
            current = current.parent()
            
        # If we didn't hit a control panel, toggle reading
        self.toggle_reading()

    def closeEvent(self, e):
        self.persist_state()
        
        if hasattr(self, 'ai_worker'):
            self.ai_worker.stop()
            self.ai_worker.wait(2000)
            
        # STOP CAMERA WORKER
        if self.eye_worker:
            self.eye_worker.stop()
            
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
            self.is_gaze_paused = False
            self.rsvp_display.set_status(0) # 0 = Red
            self.persist_state()
        else:
            # STARTING
            self.is_running = True
            self.calibration_requested = True
            self.rsvp_display.set_status(1)  # 1 = Green
            self.schedule_next_word()
    
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
        if self.is_gaze_paused: return
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
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self.update_overlay_positions)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WordDisplay()
    
    if is_raspberry_pi():
        window.showFullScreen()
    else:
        window.show()
        
    sys.exit(app.exec())