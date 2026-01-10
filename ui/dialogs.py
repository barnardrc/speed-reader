# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 08:15:04 2026

@author: barna
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QFormLayout, QDialogButtonBox, QWidget, QHBoxLayout, 
    QPushButton, QDialog, QCheckBox, QLabel, QSpinBox, QTextBrowser,
    QComboBox, QMessageBox, QDoubleSpinBox
    )
import html
import re

class PauseSettingsDialog(QDialog):
    def __init__(self, settings, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pause Settings")
        self.layout = QVBoxLayout()
        self.form = QFormLayout()
        self.spinners = {} 

        # Dynamically build rows based on config dict
        # Config format: {'key': (default_val, "Label Text")}
        for key, (default, label) in config.items():
            setting_key = f"{key}_delay"
            val = settings.get(setting_key, default)
            
            spin = self.create_spin(val)
            self.form.addRow(label, spin)
            self.spinners[setting_key] = spin

        self.layout.addLayout(self.form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self.layout.addWidget(btns)
        
        self.setLayout(self.layout)

    def create_spin(self, val):
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        dsb = QDoubleSpinBox()
        dsb.setRange(0.0, 5.0) # Reasonable range for delays
        dsb.setSingleStep(0.1)
        dsb.setValue(float(val))
        dsb.setSuffix("x")
        dsb.setFixedWidth(70)
        dsb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dsb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        
        # Dark Mode Styling
        dsb.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                border-right: none; 
                border-top-left-radius: 3px;
                border-bottom-left-radius: 3px;
                padding: 4px;
                height: 22px;
            }
        """)

        # Custom Buttons
        btn_container = QWidget()
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0)

        btn_style = """
            QPushButton {
                background-color: #444;
                color: white;
                border: 1px solid #555;
                font-weight: bold;
                font-size: 12px;
                padding: 0px; 
                text-align: center;
            }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #333; }
        """

        btn_plus = QPushButton("+")
        btn_plus.setFixedSize(20, 15)
        btn_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_plus.setStyleSheet(btn_style + "border-top-right-radius: 3px;")
        btn_plus.clicked.connect(dsb.stepUp)

        btn_minus = QPushButton("-")
        btn_minus.setFixedSize(20, 15) 
        btn_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_minus.setStyleSheet(btn_style + "border-top: none; border-bottom-right-radius: 3px;")
        btn_minus.clicked.connect(dsb.stepDown)

        btn_layout.addWidget(btn_plus)
        btn_layout.addWidget(btn_minus)
        btn_container.setLayout(btn_layout)

        layout.addWidget(dsb)
        layout.addWidget(btn_container)
        container.setLayout(layout)
        
        container.spinbox = dsb 
        return container

    def get_values(self):
        return {k: v.spinbox.value() for k, v in self.spinners.items()}


class AISettingsDialog(QDialog):
    def __init__(self, settings, backend_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.backend = backend_manager
        self.layout = QVBoxLayout()
        self.form = QFormLayout()
        
        # --- 1. Connection & Model Selection ---
        status, msg = self.backend.check_status()
        color = "green" if status else "red"
        status_lbl = QLabel(f"{msg}")
        status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.form.addRow("Status:", status_lbl)

        self.combo_model = QComboBox()
        self.combo_model.addItems(self.backend.get_available_models())
        
        current_model = self.backend.selected_model
        idx = self.combo_model.findText(current_model)
        if idx >= 0: self.combo_model.setCurrentIndex(idx)
        
        self.form.addRow("Model:", self.combo_model)
        
        btn_refresh = QPushButton("Refresh Models")
        btn_refresh.setFixedWidth(120)
        btn_refresh.clicked.connect(self.refresh_models)
        self.form.addRow("", btn_refresh)
        
        self.form.addRow(QLabel("")) 

        # --- 2. Existing Settings ---
        self.ai_enabled = settings.get("ai_enabled", False)
        self.ai_freq = settings.get("ai_frequency", 500)
        self.entity_enabled = settings.get("entity_enabled", True)
        self.entity_freq = settings.get("entity_frequency", 300)

        self.chk_questions = QCheckBox()
        self.chk_questions.setChecked(self.ai_enabled)
        self.form.addRow("Enable Comprehension:", self.chk_questions)

        self.spin_questions = self.create_int_spin(self.ai_freq, 500, 5000, 50)
        self.form.addRow("Question Freq:", self.spin_questions)

        self.chk_entities = QCheckBox()
        self.chk_entities.setChecked(self.entity_enabled)
        self.form.addRow("Enable Context Monitor:", self.chk_entities)

        self.layout.addLayout(self.form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self.layout.addWidget(btns)
        
        self.setLayout(self.layout)

    def refresh_models(self):
        status, msg = self.backend.check_status()
        if status:
            self.combo_model.clear()
            self.combo_model.addItems(self.backend.get_available_models())
            QMessageBox.information(self, "Success", f"Found {self.combo_model.count()} models.")
        else:
            QMessageBox.critical(self, "Error", msg)

    def create_int_spin(self, val, min_val, max_val, step):
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sb = QSpinBox()
        sb.setRange(min_val, max_val)
        sb.setSingleStep(step)
        sb.setValue(val)
        sb.setFixedWidth(70)
        sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        
        # Matches PauseSettingsDialog Style
        sb.setStyleSheet("""
            QSpinBox {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                border-right: none; 
                border-top-left-radius: 3px;
                border-bottom-left-radius: 3px;
                padding: 4px;
                height: 22px;
            }
        """)

        btn_container = QWidget()
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0)

        btn_style = """
            QPushButton {
                background-color: #444;
                color: white;
                border: 1px solid #555;
                font-weight: bold;
                font-size: 12px;
                padding: 0px; 
                text-align: center;
            }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #333; }
        """

        btn_plus = QPushButton("+")
        btn_plus.setFixedSize(20, 15)
        btn_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_plus.setStyleSheet(btn_style + "border-top-right-radius: 3px;")
        btn_plus.clicked.connect(sb.stepUp)

        btn_minus = QPushButton("-")
        btn_minus.setFixedSize(20, 15) 
        btn_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_minus.setStyleSheet(btn_style + "border-top: none; border-bottom-right-radius: 3px;")
        btn_minus.clicked.connect(sb.stepDown)

        btn_layout.addWidget(btn_plus)
        btn_layout.addWidget(btn_minus)
        btn_container.setLayout(btn_layout)

        layout.addWidget(sb)
        layout.addWidget(btn_container)
        container.setLayout(layout)
        
        container.spinbox = sb 
        return container

    def get_values(self):
        return {
            "ai_enabled": self.chk_questions.isChecked(),
            "ai_frequency": self.spin_questions.spinbox.value(),
            "entity_enabled": self.chk_entities.isChecked(),
            "entity_frequency": self.entity_freq,
            "selected_model": self.combo_model.currentText()
        }
    
class FootnoteDialog(QDialog):
    def __init__(self, page_num, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Footnotes - Page {page_num}")
        self.setFixedSize(500, 400)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #e0e0e0; font-family: Arial; }
            QLabel { font-size: 16px; font-weight: bold; margin-bottom: 10px; color: #4a90e2; }
            QTextBrowser { 
                background-color: #1e1e1e; 
                color: #ccc; 
                border: 1px solid #444; 
                border-radius: 4px; 
                padding: 10px; 
                font-size: 14px;
                line-height: 1.5;
            }
            QPushButton { 
                background-color: #444; 
                color: white; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #555; }
        """)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Footnotes: Page {page_num}"))
        
        self.text_browser = QTextBrowser()
        
        # 1. Escape HTML
        safe_content = html.escape(content)
        
        # 2. Aggressive Regex
        # (?<=[\s\>])   -> Lookbehind: Must be preceded by Space OR closing tag (handle previous breaks)
        # (\d{1,2})     -> Capture 1: The Number (1-99)
        # ([.]?)        -> Capture 2: Optional dot
        # (\s*)         -> Capture 3: Optional space
        # (?=[A-Z])     -> Lookahead: Must be followed by a Capital Letter
        
        # NOTE: We prepend a space to safe_content to ensure the regex catches the very first number
        work_text = " " + safe_content
        
        formatted_content = re.sub(
            r'(?<=[\s])(\d{1,2})([.]?)(\s*)(?=[A-Z])', 
            r'<br><br><span style="color:#4a90e2; font-weight:bold;">\1\2</span>\3', 
            work_text
        )
        
        # 3. Cleanup: Remove the extra leading break/space we might have added
        formatted_content = formatted_content.strip()
        if formatted_content.startswith("<br><br>"):
            formatted_content = formatted_content[8:]
            
        self.text_browser.setHtml(formatted_content)
        layout.addWidget(self.text_browser)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.setLayout(layout)