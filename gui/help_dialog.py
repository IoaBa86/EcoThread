"""Instructions dialog: quick usage reference reachable from Help > Instructions."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

HELP_TEXT = """
<h2 style="color:#22e6a8; margin-bottom:4px;">How to use EcoThread</h2>

<p><b>Track a process</b><br>
Click a row in the process table to start profiling it. Ctrl+click (or
Shift+click) to track several processes at once &mdash; each gets its own
colored line on the chart, and the summary cards show the combined total.</p>

<p><b>Track the whole computer</b><br>
The "Whole System (All Processes)" row at the top of the table isn't a real
process &mdash; select it to estimate total system power draw instead of a
single app.</p>

<p><b>Controls</b><br>
<i>Pause</i> freezes the readings without losing what's already been counted.
<i>Reset Session</i> zeroes the energy, carbon and cost totals and clears the
chart. <i>Capture Baseline</i> remembers the current total power so the
Current Power card can show you the difference later. <i>Export CSV</i> saves
everything recorded so far to a file.</p>

<p><b>Settings</b><br>
Adjust the power model (package TDP, idle baseline), electricity price and
currency, grid carbon intensity, display units (W/mW, J/Wh/kWh/Auto), poll
interval, and an optional cost alert threshold that sends a tray
notification once crossed.</p>

<p><b>Closing the window</b><br>
Closing EcoThread minimizes it to the system tray instead of quitting &mdash;
profiling keeps running in the background. Use "Quit EcoThread" from the
tray icon's menu to actually exit. A CSV of the session is saved
automatically to Documents/EcoThread/sessions on exit.</p>

<p style="color:#7d8a8a;">
Power and carbon numbers are a heuristic estimate based on CPU utilization,
not a hardware power sensor reading. See About for details.</p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instructions")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        text_label = QLabel(HELP_TEXT)
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
