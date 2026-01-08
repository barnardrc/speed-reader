# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 08:09:25 2026

@author: barna
"""

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
