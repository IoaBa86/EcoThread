"""Dashboard window: process picker table, live multi-process watts chart, energy/carbon summary."""

import csv
from collections import deque
from datetime import datetime
from pathlib import Path

import psutil
import pyqtgraph as pg
from PyQt6.QtCore import QItemSelectionModel, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import battery_sensor
from core.energy_calculator import format_energy
from core.process_monitor import SYSTEM_WIDE_NAME, SYSTEM_WIDE_PID, ProcessMonitor
from gui.about_dialog import AboutDialog
from gui.help_dialog import HelpDialog
from gui.settings_dialog import SettingsDialog, load_settings, save_settings

CHART_HISTORY_POINTS = 120
CURVE_PALETTE = ["#22e6a8", "#4fb0ff", "#ffb347", "#ff6b6b", "#c792ea", "#f5d76e", "#63d2ff", "#ff8fb1"]


def _metric_card(label_text: str) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)

    label = QLabel(label_text)
    label.setObjectName("metricLabel")

    value = QLabel("--")
    value.setObjectName("metricValue")

    layout.addWidget(label)
    layout.addWidget(value)
    return card, value


def _make_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#22e6a8"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EcoThread — Green Thread Profiler")
        self.resize(1200, 820)
        self.setWindowIcon(_make_app_icon())

        self._process_rows = []
        self._tracked_pids = set()
        self._process_curves = {}
        self._latest_stats = {}
        self._session_log = []
        self._settings = load_settings()
        self._is_paused = False
        self._quitting = False
        self._baseline_watts = 0.0
        self._alerted_this_session = False
        self._process_list_loaded = False

        self._build_ui()
        self._build_menu_bar()
        self._build_tray_icon()
        self._start_monitor()

    def _build_ui(self):
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(14)

        title = QLabel("EcoThread")
        title.setObjectName("titleLabel")
        root_layout.addWidget(title)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Filter processes by name or PID… (Ctrl+click to track multiple)")
        self._search_box.textChanged.connect(self._apply_filter)
        root_layout.addWidget(self._search_box)

        self._process_table = QTableWidget(0, 4)
        self._process_table.setHorizontalHeaderLabels(["PID", "Process Name", "CPU %", "Memory (MB)"])
        self._process_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._process_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._process_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._process_table.setAlternatingRowColors(True)
        self._process_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._process_table.itemSelectionChanged.connect(self._on_selection_changed)
        self._process_table.setMaximumHeight(260)
        root_layout.addWidget(self._process_table)

        controls_layout = QHBoxLayout()
        self._pause_button = QPushButton("Pause")
        self._pause_button.clicked.connect(self._toggle_pause)
        self._reset_button = QPushButton("Reset Session")
        self._reset_button.clicked.connect(self._reset_session)
        self._baseline_button = QPushButton("Capture Baseline")
        self._baseline_button.clicked.connect(self._capture_baseline)
        self._export_button = QPushButton("Export CSV")
        self._export_button.clicked.connect(self._export_csv)
        controls_layout.addWidget(self._pause_button)
        controls_layout.addWidget(self._reset_button)
        controls_layout.addWidget(self._baseline_button)
        controls_layout.addWidget(self._export_button)
        controls_layout.addStretch()
        root_layout.addLayout(controls_layout)

        chart_frame = QFrame()
        chart_frame.setObjectName("card")
        chart_layout = QVBoxLayout(chart_frame)
        pg.setConfigOption("background", "#1e2226")
        pg.setConfigOption("foreground", "#7d8a8a")
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("left", "Power (W)")
        self._plot_widget.setLabel("bottom", "Time (s)")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
        # Manual pan/zoom can lock the viewport to a stale range that no
        # longer contains incoming data, which looks like a dead/blank chart.
        # Disable mouse interaction and keep autoRange forced every tick.
        self._plot_widget.setMouseEnabled(x=False, y=False)
        self._plot_widget.enableAutoRange(axis="xy", enable=True)
        self._plot_widget.addLegend(offset=(10, 10))
        chart_layout.addWidget(self._plot_widget)
        root_layout.addWidget(chart_frame, stretch=1)

        self._battery_hint_label = QLabel("")
        self._battery_hint_label.setObjectName("metricLabel")
        self._battery_hint_label.setVisible(False)
        root_layout.addWidget(self._battery_hint_label)

        summary_layout = QHBoxLayout()
        watts_card, self._watts_value = _metric_card("CURRENT POWER (TRACKED TOTAL)")
        joules_card, self._joules_value = _metric_card("TOTAL ENERGY CONSUMED")
        carbon_card, self._carbon_value = _metric_card("ESTIMATED CARBON OUTPUT (gCO2)")
        cost_card, self._cost_value = _metric_card("ESTIMATED COST")
        threads_card, self._threads_value = _metric_card("TOTAL THREADS (TRACKED)")
        for card in (watts_card, joules_card, carbon_card, cost_card, threads_card):
            summary_layout.addWidget(card)
        root_layout.addLayout(summary_layout)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Loading process list…")

    def _build_menu_bar(self):
        menu_bar = self.menuBar()

        settings_menu = menu_bar.addMenu("&Settings")
        open_settings_action = settings_menu.addAction("Preferences…")
        open_settings_action.triggered.connect(self._open_settings_dialog)

        help_menu = menu_bar.addMenu("&Help")
        instructions_action = help_menu.addAction("Instructions")
        instructions_action.triggered.connect(self._open_help_dialog)
        about_action = help_menu.addAction("About EcoThread")
        about_action.triggered.connect(self._open_about_dialog)

    def _build_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return

        self._tray_icon = QSystemTrayIcon(_make_app_icon(), self)
        self._tray_icon.setToolTip("EcoThread — Green Thread Profiler")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Dashboard")
        show_action.triggered.connect(self._restore_from_tray)
        pause_action = tray_menu.addAction("Pause / Resume")
        pause_action.triggered.connect(self._toggle_pause)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit EcoThread")
        quit_action.triggered.connect(self._quit_application)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()

    def _quit_application(self):
        self._quitting = True
        self.close()

    def _open_settings_dialog(self):
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._settings = dialog.values()
            save_settings(self._settings)
            self._apply_settings_to_monitor()
            for entry in self._process_curves.values():
                entry["time"].clear()
                entry["watts"].clear()
                entry["elapsed"] = 0
                entry["curve"].setData([], [])
            self._baseline_watts = 0.0

    def _open_about_dialog(self):
        AboutDialog(self).exec()

    def _open_help_dialog(self):
        HelpDialog(self).exec()

    def _apply_settings_to_monitor(self):
        self._monitor.apply_config(
            tdp_watts=self._settings["tdp_watts"],
            idle_baseline_watts=self._settings["idle_baseline_watts"],
            carbon_intensity_g_per_kwh=self._settings["carbon_intensity_g_per_kwh"],
            electricity_price_per_kwh=self._settings["electricity_price_per_kwh"],
            poll_interval_ms=self._settings["poll_interval_ms"],
        )
        units = self._settings["power_units"]
        self._plot_widget.setLabel("left", f"Power ({units})")

    def _toggle_pause(self):
        self._is_paused = not self._is_paused
        self._monitor.set_paused(self._is_paused)
        self._pause_button.setText("Resume" if self._is_paused else "Pause")
        self.statusBar().showMessage("Paused" if self._is_paused else "Resumed")

    def _reset_session(self):
        self._monitor.reset_all_targets()
        for entry in self._process_curves.values():
            entry["time"].clear()
            entry["watts"].clear()
            entry["elapsed"] = 0
            entry["curve"].setData([], [])
        self._latest_stats.clear()
        self._session_log.clear()
        self._baseline_watts = 0.0
        self._alerted_this_session = False
        self._joules_value.setText("--")
        self._carbon_value.setText("--")
        self._cost_value.setText("--")
        self.statusBar().showMessage("Session reset")

    def _capture_baseline(self):
        total_watts = sum(s["watts"] for s in self._latest_stats.values())
        self._baseline_watts = self._watts_to_display_unit(total_watts)
        units = self._settings["power_units"]
        self.statusBar().showMessage(f"Baseline captured: {self._baseline_watts:.2f} {units}")

    def _export_csv(self):
        if not self._session_log:
            QMessageBox.information(self, "Export CSV", "No session data to export yet.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Session CSV",
            f"ecothread_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        self._write_csv(Path(file_path))
        self.statusBar().showMessage(f"Exported {len(self._session_log)} rows to {file_path}")

    def _write_csv(self, path: Path):
        fieldnames = [
            "timestamp", "pid", "process_name", "cpu_percent", "watts",
            "total_joules", "carbon_grams", "cost", "thread_count",
        ]
        with open(path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._session_log)

    def _save_session_summary(self):
        if not self._session_log:
            return
        sessions_dir = Path.home() / "Documents" / "EcoThread" / "sessions"
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
            file_path = sessions_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self._write_csv(file_path)
        except OSError:
            return
        if self._tray_icon is not None:
            self._tray_icon.showMessage(
                "EcoThread", f"Session log saved to {file_path}",
                QSystemTrayIcon.MessageIcon.Information, 4000,
            )

    def _watts_to_display_unit(self, watts: float) -> float:
        return watts * 1000.0 if self._settings["power_units"] == "mW" else watts

    def _start_monitor(self):
        self._monitor = ProcessMonitor()
        self._monitor.process_list_updated.connect(self._on_process_list_updated)
        self._monitor.stats_updated.connect(self._on_stats_updated)
        self._monitor.target_removed.connect(self._on_target_removed)
        self._apply_settings_to_monitor()
        self._monitor.start()

    def _on_process_list_updated(self, processes: list):
        self._process_rows = sorted(processes, key=lambda p: p["cpu_percent"], reverse=True)
        self._apply_filter(self._search_box.text())

        if not self._process_list_loaded and processes:
            self._process_list_loaded = True
            if not self._tracked_pids:
                self.statusBar().showMessage("Select one or more processes to begin profiling")

    def _build_system_row(self) -> dict:
        approx_cpu = min(sum(p["cpu_percent_normalized"] for p in self._process_rows), 100.0)
        try:
            memory_mb = psutil.virtual_memory().used / (1024 * 1024)
        except OSError:
            memory_mb = 0.0
        return {
            "pid": SYSTEM_WIDE_PID,
            "name": SYSTEM_WIDE_NAME,
            "cpu_percent": approx_cpu,
            "cpu_percent_normalized": approx_cpu,
            "memory_mb": memory_mb,
        }

    def _apply_filter(self, filter_text: str):
        filter_text = filter_text.strip().lower()

        if filter_text:
            rows = [
                p for p in self._process_rows
                if filter_text in p["name"].lower() or filter_text in str(p["pid"])
            ]
        else:
            rows = self._process_rows

        # The "Whole System" pseudo-target is pinned at the top regardless of
        # the search filter, so it's always reachable for tracking.
        rows = [self._build_system_row()] + rows

        self._process_table.blockSignals(True)
        self._process_table.setRowCount(len(rows))
        selection_model = self._process_table.selectionModel()
        for row_index, proc in enumerate(rows):
            is_system_row = proc["pid"] == SYSTEM_WIDE_PID
            pid_item = QTableWidgetItem(str(proc["pid"]))
            name_item = QTableWidgetItem(proc["name"])
            cpu_item = QTableWidgetItem(f"{proc['cpu_percent_normalized']:.1f}")
            if is_system_row:
                cpu_item.setToolTip("Approximate: sum of visible process load")
            else:
                cpu_item.setToolTip(f"Raw (summed across cores): {proc['cpu_percent']:.1f}%")
            memory_item = QTableWidgetItem(f"{proc['memory_mb']:.1f}")
            self._process_table.setItem(row_index, 0, pid_item)
            self._process_table.setItem(row_index, 1, name_item)
            self._process_table.setItem(row_index, 2, cpu_item)
            self._process_table.setItem(row_index, 3, memory_item)
            if proc["pid"] in self._tracked_pids:
                index = self._process_table.model().index(row_index, 0)
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )
        self._process_table.blockSignals(False)

    def _on_selection_changed(self):
        new_pids = set()
        for item in self._process_table.selectedItems():
            pid_item = self._process_table.item(item.row(), 0)
            if pid_item is not None:
                new_pids.add(int(pid_item.text()))

        for pid in self._tracked_pids - new_pids:
            self._untrack_pid(pid)
        for pid in new_pids - self._tracked_pids:
            self._track_pid(pid)

        self._tracked_pids = new_pids
        if self._tracked_pids:
            self.statusBar().showMessage(f"Tracking {len(self._tracked_pids)} process(es)")
        else:
            self.statusBar().showMessage("Select one or more processes to begin profiling")

    def _track_pid(self, pid: int):
        self._monitor.add_target(pid)
        if pid == SYSTEM_WIDE_PID:
            legend_name = SYSTEM_WIDE_NAME
        else:
            name = next((p["name"] for p in self._process_rows if p["pid"] == pid), str(pid))
            legend_name = f"{name} ({pid})"
        color = CURVE_PALETTE[len(self._process_curves) % len(CURVE_PALETTE)]
        curve = self._plot_widget.plot(pen=pg.mkPen(color=color, width=2), name=legend_name)
        self._process_curves[pid] = {
            "curve": curve,
            "time": deque(maxlen=CHART_HISTORY_POINTS),
            "watts": deque(maxlen=CHART_HISTORY_POINTS),
            "elapsed": 0,
        }

    def _untrack_pid(self, pid: int):
        self._monitor.remove_target(pid)
        entry = self._process_curves.pop(pid, None)
        if entry is not None:
            self._plot_widget.removeItem(entry["curve"])
        self._latest_stats.pop(pid, None)
        self._refresh_summary_cards()

    def _on_target_removed(self, pid: int, reason: str):
        self._tracked_pids.discard(pid)
        self._untrack_pid(pid)
        self.statusBar().showMessage(f"PID {pid} stopped tracking: {reason}")

    def _on_stats_updated(self, stats: dict):
        pid = stats["pid"]
        entry = self._process_curves.get(pid)
        if entry is None:
            return

        display_watts = self._watts_to_display_unit(stats["watts"])
        entry["elapsed"] += 1
        entry["time"].append(entry["elapsed"])
        entry["watts"].append(display_watts)
        entry["curve"].setData(list(entry["time"]), list(entry["watts"]))
        self._plot_widget.enableAutoRange(axis="xy", enable=True)

        self._latest_stats[pid] = stats

        self._session_log.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "pid": pid,
            "process_name": stats["name"],
            "cpu_percent": round(stats["cpu_percent"], 2),
            "watts": round(stats["watts"], 4),
            "total_joules": round(stats["total_joules"], 2),
            "carbon_grams": round(stats["carbon_grams"], 6),
            "cost": round(stats["cost"], 6),
            "thread_count": stats["thread_count"],
        })

        self._refresh_summary_cards()
        self._check_alert_threshold()

    def _refresh_summary_cards(self):
        if not self._latest_stats:
            self._watts_value.setText("--")
            self._watts_value.setToolTip("")
            self._threads_value.setText("--")
            self._battery_hint_label.setVisible(False)
            return

        total_watts = sum(s["watts"] for s in self._latest_stats.values())
        total_joules = sum(s["total_joules"] for s in self._latest_stats.values())
        total_carbon = sum(s["carbon_grams"] for s in self._latest_stats.values())
        total_cost = sum(s["cost"] for s in self._latest_stats.values())
        # The Whole System pseudo-target reports total process count in this
        # field, not a thread count, so it's excluded from the sum.
        total_threads = sum(
            s["thread_count"] for pid, s in self._latest_stats.items() if pid != SYSTEM_WIDE_PID
        )

        units = self._settings["power_units"]
        display_watts = self._watts_to_display_unit(total_watts)
        self._watts_value.setText(f"{display_watts:.2f} {units}")
        if self._baseline_watts:
            delta = display_watts - self._baseline_watts
            self._watts_value.setToolTip(f"Δ {delta:+.2f} {units} vs captured baseline")
        else:
            self._watts_value.setToolTip("Click \"Capture Baseline\" to compare against this moment")

        energy_unit = self._settings["energy_units"]
        self._joules_value.setText(format_energy(total_joules, energy_unit))
        self._joules_value.setToolTip(
            f"{total_joules:,.1f} J  |  {total_joules / 3600:.4f} Wh  |  {total_joules / 3_600_000:.6f} kWh"
        )

        self._carbon_value.setText(f"{total_carbon:.4f} g")

        currency = self._settings["currency_symbol"]
        cost_text = f"{currency}{total_cost:.4f}" if total_cost < 0.01 else f"{currency}{total_cost:.2f}"
        self._cost_value.setText(cost_text)

        self._threads_value.setText(str(total_threads))

        battery_watts = battery_sensor.get_battery_discharge_watts()
        if battery_watts is not None:
            self._battery_hint_label.setText(
                f"System-measured battery draw (sanity check, whole machine): {battery_watts:.1f} W"
            )
            self._battery_hint_label.setVisible(True)
        else:
            self._battery_hint_label.setVisible(False)

    def _check_alert_threshold(self):
        threshold = self._settings.get("alert_cost_threshold", 0.0)
        if threshold <= 0 or self._alerted_this_session or self._tray_icon is None:
            return
        total_cost = sum(s["cost"] for s in self._latest_stats.values())
        if total_cost >= threshold:
            self._alerted_this_session = True
            currency = self._settings["currency_symbol"]
            self._tray_icon.showMessage(
                "EcoThread — Cost Alert",
                f"Tracked processes have cost an estimated {currency}{total_cost:.2f} this session.",
                QSystemTrayIcon.MessageIcon.Warning, 5000,
            )

    def closeEvent(self, event):
        if not self._quitting and self._tray_icon is not None:
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                "EcoThread", "Still running in the background — profiling continues.",
                QSystemTrayIcon.MessageIcon.Information, 3000,
            )
            return

        self._save_session_summary()
        self._monitor.stop()
        if self._tray_icon is not None:
            self._tray_icon.hide()
        super().closeEvent(event)
