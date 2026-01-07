import sys
import os
import json
import zipfile
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, 
    QSlider, QHBoxLayout, QProgressBar, QFileDialog,
    QSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QSizePolicy, QFrame, QMainWindow, QStackedLayout, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen

SETTINGS_FILE = "speed_reader_settings.json"

DARK_THEME = """
QMainWindow, QWidget, QDialog {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
}
QLabel {
    color: #ffffff;
}
QProgressBar {
    border: 2px solid #444;
    border-radius: 5px;
    text-align: center;
    color: white;
    background-color: #2d2d2d;
}
QProgressBar::chunk {
    background-color: #3a86ff; 
    width: 10px; 
}
QPushButton {
    background-color: #333;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
    min-width: 60px;
}
QPushButton:hover {
    background-color: #444;
    border-color: #3a86ff;
}
QPushButton:pressed {
    background-color: #222;
}
QSpinBox, QDoubleSpinBox {
    background-color: #2d2d2d;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
    color: white;
}
QSlider::groove:horizontal {
    border: 1px solid #555;
    height: 6px;
    background: #2d2d2d;
    margin: 2px 0;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #3a86ff;
    border: 1px solid #3a86ff;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #66a3ff;
}
QListWidget {
    background-color: #252526;
    border-right: 1px solid #333;
    outline: none;
}
QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #2d2d2d;
}
QListWidget::item:selected {
    background-color: #37373d;
    color: #ffffff;
    border-left: 3px solid #3a86ff;
}
"""

def load_settings():
    defaults = {
        "wpm": 300, 
        "opacity": 30, 
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

def get_words_and_chapters(epub_path):
    words_list = []
    chapters = [] 
    current_word_count = 0

    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            container_xml = z.read('META-INF/container.xml')
            container_root = ET.fromstring(container_xml)
            rootfile_path = None
            for node in container_root.iter():
                if 'full-path' in node.attrib:
                    rootfile_path = node.attrib['full-path']
                    break
            if not rootfile_path: return [], []

            opf_data = z.read(rootfile_path)
            opf_root = ET.fromstring(opf_data)
            opf_dir = os.path.dirname(rootfile_path)
            
            manifest = {item.attrib['id']: item.attrib['href'] 
                        for item in opf_root.findall(".//{*}manifest/{*}item")}
            
            toc_titles = {}
            try:
                spine_node = opf_root.find(".//{*}spine")
                toc_id = spine_node.attrib.get('toc')
                if toc_id and toc_id in manifest:
                    toc_rel_path = manifest[toc_id]
                    toc_full_path = os.path.join(opf_dir, toc_rel_path).replace('\\', '/')
                    toc_data = z.read(toc_full_path)
                    toc_root = ET.fromstring(toc_data)
                    for nav in toc_root.findall(".//{*}navPoint"):
                        label = nav.find(".//{*}navLabel/{*}text")
                        content = nav.find(".//{*}content")
                        if label is not None and content is not None:
                            src = content.attrib.get('src', '').split('#')[0]
                            toc_titles[src] = label.text.strip()
            except: pass

            spine_ids = [item.attrib['idref'] for item in opf_root.findall(".//{*}spine/{*}itemref")]
            
            for item_id in spine_ids:
                if item_id in manifest:
                    rel_path = manifest[item_id]
                    full_item_path = os.path.join(opf_dir, rel_path).replace('\\', '/')
                    try:
                        content = z.read(full_item_path)
                        soup = BeautifulSoup(content, 'html.parser')
                        title = toc_titles.get(rel_path)
                        if not title and soup.title: title = soup.title.string.strip()
                        if not title:
                            h = soup.find(['h1', 'h2', 'h3'])
                            if h: title = h.get_text().strip()[:40]
                        if not title: title = f"Section {len(chapters)+1}"

                        chapters.append((title, current_word_count))
                        words_list.extend(soup.get_text(separator=' ').split())
                        current_word_count += len(words_list) - chapters[-1][1]
                    except KeyError: continue
    except Exception as e:
        print(f"Error: {e}")
        return [], []
    return words_list, chapters

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

        painter.setPen(QPen(QColor("#444"), 2))
        painter.drawLine(cx, cy - 60, cx, cy - 75)
        painter.drawLine(cx, cy + 20, cx, cy + 35)

        painter.setPen(QColor("#ff5555"))
        painter.drawText(pivot_x, cy, pivot_char)

        painter.setPen(QColor("#ffffff"))
        left_width = self.metrics.horizontalAdvance(left_part)
        painter.drawText(pivot_x - left_width, cy, left_part)
        painter.drawText(pivot_x + pivot_width, cy, right_part)

# --- New Dialog for Delay Settings ---
class PauseSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pause Settings")
        self.settings = settings
        self.layout = QVBoxLayout()

        form = QFormLayout()
        
        self.spin_period = self.create_spin(settings.get("period_delay", 2.0))
        form.addRow("End of Sentence (. ? !):", self.spin_period)

        self.spin_comma = self.create_spin(settings.get("comma_delay", 1.5))
        form.addRow("Comma (, : ;):", self.spin_comma)

        self.spin_hyphen = self.create_spin(settings.get("hyphen_delay", 1.2))
        form.addRow("Hyphen/Dash (-):", self.spin_hyphen)

        self.layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self.layout.addWidget(btns)
        
        self.setLayout(self.layout)

    def create_spin(self, val):
        sb = QSpinBox() # Double
        from PyQt6.QtWidgets import QDoubleSpinBox
        dsb = QDoubleSpinBox()
        dsb.setRange(1.0, 5.0)
        dsb.setSingleStep(0.1)
        dsb.setValue(val)
        return dsb

    def get_values(self):
        return {
            "period_delay": self.spin_period.value(),
            "comma_delay": self.spin_comma.value(),
            "hyphen_delay": self.spin_hyphen.value()
        }

class WordDisplay(QMainWindow):
    def __init__(self, words, chapters, file_path):
        super().__init__()
        self.words = words
        self.chapters = chapters
        self.file_path = file_path
        self.is_running = False
        
        self.setStyleSheet(DARK_THEME)
        
        self.settings = load_settings()
        self.wpm = self.settings.get("wpm", 300)
        self.opacity = self.settings.get("opacity", 30)
        
        # Load custom delay settings
        self.delays = {
            "period": self.settings.get("period_delay", 2.0),
            "comma": self.settings.get("comma_delay", 1.5),
            "hyphen": self.settings.get("hyphen_delay", 1.2)
        }

        saved_index = self.settings.get("books", {}).get(self.file_path, 0)
        self.index = min(saved_index, len(self.words) - 1) if self.words else 0

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
        for title, idx in self.chapters:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.chapter_list.addItem(item)
        self.chapter_list.itemClicked.connect(self.on_chapter_clicked)
        self.sidebar_layout.addWidget(self.chapter_list)
        self.sidebar.setLayout(self.sidebar_layout)
        self.main_layout.addWidget(self.sidebar)

        # Content Area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        
        top = QHBoxLayout()
        btn = QPushButton("☰ Menu")
        btn.setFixedSize(80, 30)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        top.addWidget(btn)
        top.addStretch()
        self.content_layout.addLayout(top)
        
        self.content_layout.addStretch()
        
        # Stacked Display
        self.display_container = QWidget()
        self.display_container.setFixedHeight(300) 
        self.stack_layout = QStackedLayout()
        self.stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        
        self.context_label = QLabel()
        self.context_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.context_label.setWordWrap(True)
        self.context_label.setTextFormat(Qt.TextFormat.PlainText)
        self.context_label.setStyleSheet(f"font-size: 20px; font-family: 'Georgia'; color: rgba(255, 255, 255, {self.opacity/100});")
        self.stack_layout.addWidget(self.context_label)

        self.rsvp_display = RSVPWidget()
        self.stack_layout.addWidget(self.rsvp_display)
        
        self.display_container.setLayout(self.stack_layout)
        self.content_layout.addWidget(self.display_container)

        self.content_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.words))
        self.progress_bar.setValue(self.index)
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
        
        # Opacity Slider
        controls.addWidget(QLabel("Op:"))
        self.op_slider = QSlider(Qt.Orientation.Horizontal)
        self.op_slider.setRange(0, 100)
        self.op_slider.setValue(self.opacity)
        self.op_slider.setFixedWidth(80)
        self.op_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.op_slider.valueChanged.connect(self.update_opacity)
        controls.addWidget(self.op_slider)

        controls.addSpacing(10)

        # Pause Settings Button
        self.btn_pauses = QPushButton("Pauses")
        self.btn_pauses.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_pauses.clicked.connect(self.open_pause_settings)
        controls.addWidget(self.btn_pauses)

        controls.addStretch()
        self.content_layout.addLayout(controls)

        self.content_widget.setLayout(self.content_layout)
        self.main_layout.addWidget(self.content_widget)

        self.resize(1000, 600)
        
        # Timer Setup
        self.timer = QTimer()
        self.timer.setSingleShot(True) # Crucial for variable delays
        self.timer.timeout.connect(self.show_next_word)
        
        if self.index > 0: self.update_display_manual()
        self.highlight_current_chapter()
        self.setFocus()

    def open_pause_settings(self):
        was_running = self.is_running
        if was_running: self.toggle_reading() # Pause while editing
        
        dlg = PauseSettingsDialog(self.settings, self)
        if dlg.exec():
            vals = dlg.get_values()
            self.settings.update(vals)
            self.delays = {
                "period": vals["period_delay"],
                "comma": vals["comma_delay"],
                "hyphen": vals["hyphen_delay"]
            }
            save_settings(self.settings)
            
        self.setFocus()

    def update_opacity(self):
        self.opacity = self.op_slider.value()
        alpha = self.opacity / 100.0
        self.context_label.setStyleSheet(f"font-size: 20px; font-family: 'Georgia'; color: rgba(255, 255, 255, {alpha});")
        self.setFocus()

    def update_context_view(self):
        start = max(0, self.index - 20)
        end = min(len(self.words), self.index + 20)
        context_words = [self.words[i] for i in range(start, end)]
        full_text = " ".join(context_words)
        self.context_label.setText(full_text)

    def on_chapter_clicked(self, item):
        self.index = item.data(Qt.ItemDataRole.UserRole)
        self.update_display_manual()
        if self.is_running: self.schedule_next_word()
        self.setFocus()

    def keyPressEvent(self, e):
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
        if self.childAt(e.pos()) not in [self.slider, self.op_slider, self.pct_btn, self.pct_spin, self.btn_pauses]:
            self.setFocus()
            self.toggle_reading()

    def closeEvent(self, e):
        self.persist_state()
        e.accept()

    def persist_state(self):
        self.settings["wpm"] = self.wpm
        self.settings["opacity"] = self.opacity
        if "books" not in self.settings: self.settings["books"] = {}
        self.settings["books"][self.file_path] = self.index
        save_settings(self.settings)

    def toggle_reading(self):
        self.setFocus()
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
        # Only restart if running, logic handled in schedule_next_word
        
    def jump_to_percentage(self):
        self.index = int((self.pct_spin.value() / 100) * len(self.words))
        self.update_display_manual()
        self.highlight_current_chapter()
        self.setFocus()

    def highlight_current_chapter(self):
        r = 0
        for i, (t, s) in enumerate(self.chapters):
            if s <= self.index: r = i
            else: break
        self.chapter_list.setCurrentRow(r)

    def update_display_manual(self):
        if self.index < len(self.words):
            self.rsvp_display.set_word(self.words[self.index])
            self.progress_bar.setValue(self.index)
            self.update_context_view()

    # --- TIMER LOGIC ---
    def schedule_next_word(self):
        if not self.is_running: return
        
        # Calculate Base Delay
        base_ms = int(60000 / self.wpm)
        
        # Different times for different punctuations
        multiplier = 1.0
        if self.index < len(self.words):
            current_word = self.words[self.index]
            last_char = current_word[-1] if current_word else ""
            
            if last_char in ['.', '?', '!']:
                multiplier = self.delays['period']
            elif last_char in [',', ':', ';']:
                multiplier = self.delays['comma']
            # Choosing to pause if hyphen mid-word too, might delete
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
    f, _ = QFileDialog.getOpenFileName(None, "Open EPUB", "", "EPUB Files (*.epub)")
    if f:
        w, c = get_words_and_chapters(os.path.abspath(f))
        if w:
            WordDisplay(w, c, os.path.abspath(f)).show()
            sys.exit(app.exec())
    sys.exit()