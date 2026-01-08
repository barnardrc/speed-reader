import sys
import os
import json
import zipfile
import html
import pypdf
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, 
    QSlider, QHBoxLayout, QProgressBar, QFileDialog,
    QSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QSizePolicy, QFrame, QMainWindow, QDialog, QFormLayout, 
    QDialogButtonBox, QMessageBox, QProgressDialog, QTextBrowser
)
from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen, QTextCursor
from utils.style_sheet import DARK_THEME
from ui.dialogs import PauseSettingsDialog
from ui.widgets import RSVPWidget, ContextFlowWidget
from utils.text_utils import is_header

SETTINGS_FILE = "speed_reader_settings.json"

def load_settings():
    defaults = {
        "wpm": 300, 
        "opacity": 50, # Default higher so text is visible
        "context_range": 20, 
        "period_delay": 2.0, 
        "comma_delay": 1.5, 
        "hyphen_delay": 1.2,
        "books": {}
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                defaults.update(data)
                return defaults
        except Exception: pass
    return defaults

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception: pass

class BookLoader(QThread):
    progress_updated = pyqtSignal(int)
    finished_loading = pyqtSignal(list, list)
    error_occurred = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            words = []
            chapters = []

            if self.file_path.lower().endswith('.pdf'):
                words, chapters = self._load_pdf()
            elif self.file_path.lower().endswith('.epub'):
                words, chapters = self._load_epub()
            else:
                raise ValueError("Unsupported file format")

            if self.isInterruptionRequested():
                return

            self.finished_loading.emit(words, chapters)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _load_pdf(self):
        words_list = []
        chapters = []
        current_word_count = 0
        
        reader = pypdf.PdfReader(self.file_path)
        total_pages = len(reader.pages)
        page_map = {} 

        # 1. Extract Text
        for i, page in enumerate(reader.pages):
            if self.isInterruptionRequested(): return [], []
            self.progress_updated.emit(int((i / total_pages) * 100))
            
            page_map[i] = current_word_count
            text = page.extract_text()
            if text:
                page_words = text.split()
                words_list.extend(page_words)
                current_word_count += len(page_words)

        # 2. Extract Outline (Recursive)
        def parse_outline(outline_items):
            for item in outline_items:
                if isinstance(item, list):
                    parse_outline(item)
                else:
                    try:
                        title = item.title
                        page_num = reader.get_destination_page_number(item)
                        if page_num in page_map:
                            chapters.append((title, page_map[page_num]))
                    except Exception: pass

        if reader.outline:
            parse_outline(reader.outline)

        # 3. Fallback to Pages
        if not chapters:
            for i in range(total_pages):
                if i in page_map:
                    chapters.append((f"Page {i+1}", page_map[i]))
        
        words_list = self._process_headers(words_list)
        return words_list, chapters
        

    def _load_epub(self):
        words_list = []
        chapters = []
        current_word_count = 0

        with zipfile.ZipFile(self.file_path, 'r') as z:
            # Locate Root File
            container_xml = z.read('META-INF/container.xml')
            container_root = ET.fromstring(container_xml)
            rootfile_path = next(node.attrib['full-path'] for node in container_root.iter() if 'full-path' in node.attrib)
            
            opf_data = z.read(rootfile_path)
            opf_root = ET.fromstring(opf_data)
            opf_dir = os.path.dirname(rootfile_path)
            
            manifest = {item.attrib['id']: item.attrib['href'] 
                        for item in opf_root.findall(".//{*}manifest/{*}item")}
            
            # Extract TOC Titles
            toc_titles = {}
            try:
                spine_node = opf_root.find(".//{*}spine")
                toc_id = spine_node.attrib.get('toc')
                if toc_id and toc_id in manifest:
                    toc_full_path = os.path.join(opf_dir, manifest[toc_id]).replace('\\', '/')
                    toc_root = ET.fromstring(z.read(toc_full_path))
                    for nav in toc_root.findall(".//{*}navPoint"):
                        label = nav.find(".//{*}navLabel/{*}text")
                        content = nav.find(".//{*}content")
                        if label is not None and content is not None:
                            src = content.attrib.get('src', '').split('#')[0]
                            toc_titles[src] = label.text.strip()
            except: pass

            # Process Spine
            spine_ids = [item.attrib['idref'] for item in opf_root.findall(".//{*}spine/{*}itemref")]
            total_items = len(spine_ids)

            for i, item_id in enumerate(spine_ids):
                if self.isInterruptionRequested(): return [], []
                self.progress_updated.emit(int((i / total_items) * 100))

                if item_id in manifest:
                    rel_path = manifest[item_id]
                    full_path = os.path.join(opf_dir, rel_path).replace('\\', '/')
                    try:
                        soup = BeautifulSoup(z.read(full_path), 'html.parser')
                        title = toc_titles.get(rel_path)
                        
                        # Fallback Title Logic
                        if not title and soup.title: title = soup.title.string.strip()
                        if not title:
                            h = soup.find(['h1', 'h2', 'h3'])
                            if h: title = h.get_text().strip()[:40]
                        if not title: title = f"Section {len(chapters)+1}"

                        chapters.append((title, current_word_count))
                        words_list.extend(soup.get_text(separator=' ').split())
                        current_word_count += len(words_list) - chapters[-1][1]
                    except KeyError: continue
        
        words_list = self._process_headers(words_list)
        return words_list, chapters
    
    def _process_headers(self, words):
        processed = []
        stack = []
        
        for word in words:
            # Check if word is ALL CAPS and no quotes
            is_caps = word.isupper() and any(c.isalpha() for c in word)
            has_quote = '"' in word or "'" in word
            
            if is_caps and not has_quote:
                stack.append(word)
            else:
                # Flush existing stack if we hit a non-header word
                if stack:
                    if len(stack) <= 10:
                        processed.append(" ".join(stack))
                    else:
                        processed.extend(stack)
                    stack = []
                processed.append(word)
        
        # Flush remaining stack at the end
        if stack:
            if len(stack) <= 10:
                processed.append(" ".join(stack))
            else:
                processed.extend(stack)
                
        return processed
    
class WordDisplay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.words = []
        self.chapters = []
        self.file_path = ""
        self.is_running = False
        self.index = 0
        
        self.setStyleSheet(DARK_THEME)
        self.settings = load_settings()
        self.wpm = self.settings.get("wpm", 300)
        self.opacity = self.settings.get("opacity", 50)
        self.ctx_range = self.settings.get("context_range", 20)
        
        self.delays = {
            "period": self.settings.get("period_delay", 2.0),
            "comma": self.settings.get("comma_delay", 1.5),
            "hyphen": self.settings.get("hyphen_delay", 1.2),
            "header": self.settings.get("header_delay", 10.0)
        }

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.central_widget.setLayout(self.main_layout)

        # Sidebar
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

        # Content
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        
        # --- Loading Bar Container (Hidden by default) ---
        self.loading_container = QWidget()
        self.loading_layout = QHBoxLayout()
        self.loading_layout.setContentsMargins(0, 0, 0, 0)
        
        self.loading_label = QLabel("Parsing Book...")
        self.loading_bar = QProgressBar()
        self.loading_bar.setTextVisible(True)
        
        self.loading_layout.addWidget(self.loading_label)
        self.loading_layout.addWidget(self.loading_bar)
        
        self.loading_container.setLayout(self.loading_layout)
        self.loading_container.setVisible(False) # Hide initially
        self.content_layout.addWidget(self.loading_container)
        
        top = QHBoxLayout()
        btn_open = QPushButton("Open Book")
        btn_open.setFixedSize(100, 30)
        btn_open.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_open.clicked.connect(self.open_file_dialog)
        top.addWidget(btn_open)

        btn_menu = QPushButton("☰ List")
        btn_menu.setFixedSize(80, 30)
        btn_menu.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_menu.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        top.addWidget(btn_menu)
        
        top.addStretch()
        self.content_layout.addLayout(top)
        
        self.content_layout.addStretch()
        
        # Display Container
        self.display_container = QWidget()
        self.display_layout = QVBoxLayout()
        
        # 1. Context Widget (Custom Flow)
        self.context_display = ContextFlowWidget()
        self.display_layout.addWidget(self.context_display, stretch=1)

        # 2. RSVP Widget (Bottom)
        self.rsvp_display = RSVPWidget()
        self.display_layout.addWidget(self.rsvp_display, stretch=1)
        
        self.display_container.setLayout(self.display_layout)
        self.content_layout.addWidget(self.display_container, stretch=2) 

        self.content_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.content_layout.addWidget(self.progress_bar)

        nav = QHBoxLayout()
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
        self.content_layout.addLayout(nav)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Speed:"))
        self.wpm_label = QLabel(f"{self.wpm}")
        controls.addWidget(self.wpm_label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(60, 1000)
        self.slider.setValue(self.wpm)
        self.slider.setFixedWidth(150)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.valueChanged.connect(self.update_speed_from_slider)
        controls.addWidget(self.slider)

        controls.addSpacing(10)
        controls.addWidget(QLabel("Op:"))
        self.op_slider = QSlider(Qt.Orientation.Horizontal)
        self.op_slider.setRange(0, 100)
        self.op_slider.setValue(self.opacity)
        self.op_slider.setFixedWidth(80)
        self.op_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.op_slider.valueChanged.connect(self.update_opacity)
        controls.addWidget(self.op_slider)

        controls.addSpacing(10)
        controls.addWidget(QLabel("Ctx Range:"))
        self.ctx_slider = QSlider(Qt.Orientation.Horizontal)
        self.ctx_slider.setRange(5, 100)
        self.ctx_slider.setValue(self.ctx_range)
        self.ctx_slider.setFixedWidth(80)
        self.ctx_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ctx_slider.valueChanged.connect(self.update_ctx_range)
        controls.addWidget(self.ctx_slider)

        controls.addSpacing(10)
        self.btn_pauses = QPushButton("Pauses")
        self.btn_pauses.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_pauses.clicked.connect(self.open_pause_settings)
        controls.addWidget(self.btn_pauses)
        controls.addStretch()
        self.content_layout.addLayout(controls)

        self.content_widget.setLayout(self.content_layout)
        self.main_layout.addWidget(self.content_widget)

        self.resize(1000, 700)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_next_word)
        
        self.setFocus()

    def open_file_dialog(self):
        if self.file_path:
            self.persist_state()
            
        if self.is_running:
            self.toggle_reading()

        # Updated filter to include PDF
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Book", 
            "", 
            "Books (*.epub *.pdf);;EPUB Files (*.epub);;PDF Files (*.pdf)"
        )
        if file_path:
            self.load_book(os.path.abspath(file_path))

    def load_book(self, file_path):
        print(f"Loading: {file_path}")
        
        # 1. UI State: Show loading, disable interactions
        self.loading_bar.setValue(0)
        self.loading_label.setText(f"Loading {os.path.basename(file_path)}...")
        self.loading_container.setVisible(True)
        self.central_widget.setEnabled(False)

        # 2. Setup Thread
        self.loader_thread = BookLoader(file_path)
        self.loader_thread.progress_updated.connect(self.loading_bar.setValue)
        self.loader_thread.finished_loading.connect(lambda w, c: self.on_book_loaded(w, c, file_path))
        
        self.loader_thread.error_occurred.connect(lambda e: QMessageBox.critical(self, "Error", f"Failed: {e}"))
        
        self.loader_thread.finished.connect(self.reset_loading_ui)
        
        self.loader_thread.start()

    def reset_loading_ui(self):
        self.loading_container.setVisible(False)
        self.central_widget.setEnabled(True)
        self.setFocus()

    def on_book_loaded(self, words, chapters, file_path):
        if not words:
            QMessageBox.critical(self, "Error", "Book is empty or could not be parsed.")
            return

        self.words = words
        self.chapters = chapters
        self.file_path = file_path
        
        saved_index = self.settings.get("books", {}).get(self.file_path, 0)
        self.index = min(saved_index, len(self.words) - 1)

        self.chapter_list.clear()
        for title, idx in self.chapters:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.chapter_list.addItem(item)

        self.progress_bar.setRange(0, len(self.words))
        self.progress_bar.setValue(self.index)

        self.update_display_manual()
        self.highlight_current_chapter()

    def open_pause_settings(self):
        was_running = self.is_running
        if was_running: self.toggle_reading()
        
        dlg = PauseSettingsDialog(self.settings, self)
        if dlg.exec():
            vals = dlg.get_values()
            self.settings.update(vals)
            self.delays = {
                "period": vals["period_delay"],
                "comma": vals["comma_delay"],
                "hyphen": vals["hyphen_delay"],
                "header": vals["header_delay"] # <--- ADD THIS
            }
            save_settings(self.settings)
        self.setFocus()

    def update_opacity(self):
        self.opacity = self.op_slider.value()
        self.update_context_view()
        self.setFocus()

    def update_ctx_range(self):
        self.ctx_range = self.ctx_slider.value()
        self.update_context_view()
        self.setFocus()

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
            if i == 0:
                s_start = 0
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
        
        # Pass data to the custom widget for painting
        self.context_display.set_data(
            self.words,
            self.index,
            self.ctx_range,
            self.opacity,
            s_start,
            s_end
        )

    def on_chapter_clicked(self, item):
        self.index = item.data(Qt.ItemDataRole.UserRole)
        self.update_display_manual()
        if self.is_running: self.schedule_next_word()
        self.setFocus()

    def keyPressEvent(self, e):
        if not self.words: return
        if e.key() == Qt.Key.Key_Space:
            self.toggle_reading()
        elif e.key() == Qt.Key.Key_Left:
            self.skip_words(-10)
        elif e.key() == Qt.Key.Key_Right:
            self.skip_words(10)
        elif e.key() == Qt.Key.Key_Up:
            self.change_speed(25)
        elif e.key() == Qt.Key.Key_Down:
            self.change_speed(-25)
        else:
            super().keyPressEvent(e)

    def skip_words(self, count):
        self.index = max(0, min(len(self.words) - 1, self.index + count))
        self.update_display_manual()
        self.highlight_current_chapter()

    def change_speed(self, delta):
        new_wpm = self.wpm + delta
        new_wpm = max(self.slider.minimum(), min(self.slider.maximum(), new_wpm))
        self.slider.setValue(new_wpm) 

    def mousePressEvent(self, e):
        if self.childAt(e.pos()) not in [self.slider, self.op_slider, self.ctx_slider, self.pct_btn, self.pct_spin, self.btn_pauses]:
            self.setFocus()
            self.toggle_reading()

    def closeEvent(self, e):
        self.persist_state()
        e.accept()

    def persist_state(self):
        if not self.file_path: return
        self.settings["wpm"] = self.wpm
        self.settings["opacity"] = self.opacity
        self.settings["context_range"] = self.ctx_range
        if "books" not in self.settings: self.settings["books"] = {}
        self.settings["books"][self.file_path] = self.index
        save_settings(self.settings)

    def toggle_reading(self):
        self.setFocus()
        if not self.words: return
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.persist_state()
        else:
            self.is_running = True
            self.schedule_next_word()

    def update_speed_from_slider(self):
        self.wpm = self.slider.value()
        self.wpm_label.setText(f"{self.wpm}")
        
    def jump_to_percentage(self):
        if not self.words: return
        self.index = int((self.pct_spin.value() / 100) * len(self.words))
        self.update_display_manual()
        self.highlight_current_chapter()
        self.setFocus()

    def highlight_current_chapter(self):
        if not self.chapters: return
        r = 0
        for i, (t, s) in enumerate(self.chapters):
            if s <= self.index: r = i
            else: break
        self.chapter_list.setCurrentRow(r)

    def update_display_manual(self):
        if self.words and self.index < len(self.words):
            self.rsvp_display.set_word(self.words[self.index])
            self.progress_bar.setValue(self.index)
            self.update_context_view()

    def schedule_next_word(self):
        if not self.is_running: return
        
        base_ms = int(60000 / self.wpm)
        multiplier = 1.0
        
        if self.words and self.index < len(self.words):
            current_word = self.words[self.index]
            last_char = current_word[-1] if current_word else ""
            
            if is_header(current_word):
                multiplier = self.delays['header']
            elif last_char in ['.', '?', '!']:
                multiplier = self.delays['period']
            elif last_char in [',', ':', ';']:
                multiplier = self.delays['comma']
            elif '-' in current_word:
                multiplier = self.delays['hyphen']
        
        actual_delay = int(base_ms * multiplier)
        self.timer.start(actual_delay)

    def show_next_word(self):
        self.index += 1
        if self.index < len(self.words):
            self.rsvp_display.set_word(self.words[self.index])
            self.progress_bar.setValue(self.index)
            self.update_context_view()
            self.schedule_next_word()
        else:
            self.rsvp_display.set_word("Finished")
            self.is_running = False
            self.persist_state()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WordDisplay()
    window.show()
    sys.exit(app.exec())