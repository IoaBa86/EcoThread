"""Dark theme QSS stylesheet for EcoThread."""

DARK_STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Consolas', sans-serif;
    outline: none;
}

QMainWindow, QWidget {
    background-color: #1a1d21;
    color: #d8e0e0;
}

QLabel {
    color: #c5d0d0;
    font-size: 13px;
}

QLabel#titleLabel {
    color: #22e6a8;
    font-size: 20px;
    font-weight: 600;
}

QLabel#metricValue {
    color: #22e6a8;
    font-size: 26px;
    font-weight: 700;
}

QLabel#metricLabel {
    color: #7d8a8a;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}

QFrame#card {
    background-color: #22262b;
    border: 1px solid #2e3338;
    border-radius: 8px;
}

QLineEdit {
    background-color: #22262b;
    border: 1px solid #33393f;
    border-radius: 5px;
    padding: 6px 10px;
    color: #e6ecec;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #22e6a8;
}

QTableWidget {
    background-color: #1e2226;
    alternate-background-color: #22262b;
    gridline-color: #2b3035;
    border: 1px solid #2e3338;
    border-radius: 6px;
    color: #d8e0e0;
    selection-background-color: #16413a;
    selection-color: #7cf5cf;
}

QHeaderView::section {
    background-color: #262b30;
    color: #7d8a8a;
    padding: 6px;
    border: none;
    border-bottom: 2px solid #22e6a8;
    font-weight: 600;
    font-size: 11px;
}

QTableWidget::item {
    padding: 4px;
}

QPushButton {
    background-color: #1f7a5c;
    color: #eafff6;
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #22a179;
}

QPushButton:pressed {
    background-color: #17624a;
}

QPushButton:disabled {
    background-color: #2e3338;
    color: #5c6666;
}

QScrollBar:vertical {
    background: #1a1d21;
    width: 10px;
}

QScrollBar::handle:vertical {
    background: #33393f;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #22e6a8;
}

QStatusBar {
    background-color: #16181b;
    color: #7d8a8a;
}
"""
