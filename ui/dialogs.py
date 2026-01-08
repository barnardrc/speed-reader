# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 08:15:04 2026

@author: barna
"""
from PyQt6.QtWidgets import QVBoxLayout, QFormLayout, QDialogButtonBox
from PyQt6.QtWidgets import QDialog

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

        # Added Header Delay
        self.spin_header = self.create_spin(settings.get("header_delay", 3.0))
        form.addRow("Headers (ALL CAPS):", self.spin_header)

        self.layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self.layout.addWidget(btns)
        
        self.setLayout(self.layout)

    def create_spin(self, val):
        from PyQt6.QtWidgets import QDoubleSpinBox
        dsb = QDoubleSpinBox()
        dsb.setRange(1.0, 10.0) # Increased max range for headers
        dsb.setSingleStep(0.1)
        dsb.setValue(val)
        return dsb

    def get_values(self):
        return {
            "period_delay": self.spin_period.value(),
            "comma_delay": self.spin_comma.value(),
            "hyphen_delay": self.spin_hyphen.value(),
            "header_delay": self.spin_header.value()
        }