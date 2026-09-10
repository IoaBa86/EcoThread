"""About dialog: app identity, version, and methodology disclosure."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

APP_VERSION = "0.1.0"

ABOUT_TEXT = """
<h2 style="color:#22e6a8; margin-bottom:0;">EcoThread</h2>
<p style="color:#7d8a8a; margin-top:2px;">Green Thread Profiler &mdash; v{version}</p>
<p>
Tracks a target Windows process's thread behavior and estimates its
real-time power draw and carbon footprint.
</p>
<p>
Power estimates use a TDP-scaling heuristic (idle baseline + a load-weighted
share of configurable package TDP) &mdash; there is no per-process hardware
power sensor on consumer Windows systems. Adjust TDP, idle baseline, and
grid carbon intensity in Settings to match your hardware and region.
</p>
<p style="color:#7d8a8a;">Built with PyQt6, psutil, and pyqtgraph.</p>
<p style="color:#7d8a8a;">
Built by Ioannis Bakas &mdash;
<a href="https://ibakas.com" style="color:#22e6a8;">ibakas.com</a>
</p>
"""


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About EcoThread")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        text_label = QLabel(ABOUT_TEXT.format(version=APP_VERSION))
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setWordWrap(True)
        text_label.setOpenExternalLinks(True)
        layout.addWidget(text_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
