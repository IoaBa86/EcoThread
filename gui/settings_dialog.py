"""Settings dialog: energy model, power profile presets, units, and app behavior."""

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from core import autostart
from core.energy_calculator import ENERGY_UNIT_OPTIONS

ORG_NAME = "EcoThread"
APP_NAME = "GreenThreadProfiler"

SETTINGS_DEFAULTS = {
    "tdp_watts": 65.0,
    "idle_baseline_watts": 4.0,
    "carbon_intensity_g_per_kwh": 400.0,
    "electricity_price_per_kwh": 0.15,
    "currency_symbol": "$",
    "poll_interval_ms": 1000,
    "power_units": "W",
    "energy_units": "Auto",
    "alert_cost_threshold": 0.0,
    "chart_window_seconds": 120,
}

# (package TDP watts, idle baseline watts) per preset.
POWER_PROFILES = {
    "Custom": None,
    "Laptop (15W TDP)": (15.0, 2.0),
    "Laptop (28W TDP)": (28.0, 3.0),
    "Desktop (65W TDP)": (65.0, 4.0),
    "Desktop (125W TDP)": (125.0, 6.0),
    "Desktop (170W TDP, HEDT)": (170.0, 8.0),
}

CHART_WINDOW_OPTIONS = [
    ("1 minute", 60),
    ("2 minutes", 120),
    ("5 minutes", 300),
    ("15 minutes", 900),
    ("30 minutes", 1800),
]


def load_settings() -> dict:
    settings = QSettings(ORG_NAME, APP_NAME)
    values = dict(SETTINGS_DEFAULTS)
    for key, default in SETTINGS_DEFAULTS.items():
        values[key] = type(default)(settings.value(key, default))
    return values


def save_settings(values: dict):
    settings = QSettings(ORG_NAME, APP_NAME)
    for key, value in values.items():
        settings.setValue(key, value)


class SettingsDialog(QDialog):
    """Modal dialog exposing energy-model parameters, units, and app behavior."""

    def __init__(self, current_values: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)

        self._updating_from_profile = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._profile_combo = QComboBox()
        self._profile_combo.addItems(POWER_PROFILES.keys())
        self._profile_combo.currentTextChanged.connect(self._apply_profile)
        form.addRow("Power profile", self._profile_combo)

        self._tdp_spin = QDoubleSpinBox()
        self._tdp_spin.setRange(1.0, 500.0)
        self._tdp_spin.setSuffix(" W")
        self._tdp_spin.setValue(current_values["tdp_watts"])
        self._tdp_spin.valueChanged.connect(self._mark_custom_profile)
        form.addRow("Package TDP", self._tdp_spin)

        self._idle_spin = QDoubleSpinBox()
        self._idle_spin.setRange(0.0, 100.0)
        self._idle_spin.setSuffix(" W")
        self._idle_spin.setValue(current_values["idle_baseline_watts"])
        self._idle_spin.valueChanged.connect(self._mark_custom_profile)
        form.addRow("Idle baseline power", self._idle_spin)

        self._carbon_spin = QDoubleSpinBox()
        self._carbon_spin.setRange(0.0, 2000.0)
        self._carbon_spin.setSuffix(" gCO2/kWh")
        self._carbon_spin.setValue(current_values["carbon_intensity_g_per_kwh"])
        form.addRow("Grid carbon intensity", self._carbon_spin)

        self._currency_combo = QComboBox()
        self._currency_combo.addItems(["$", "€", "£", "¥"])
        self._currency_combo.setCurrentText(current_values["currency_symbol"])
        form.addRow("Currency symbol", self._currency_combo)

        self._price_spin = QDoubleSpinBox()
        self._price_spin.setRange(0.0, 5.0)
        self._price_spin.setDecimals(4)
        self._price_spin.setSuffix(" /kWh")
        self._price_spin.setValue(current_values["electricity_price_per_kwh"])
        form.addRow("Electricity price", self._price_spin)

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(250, 5000)
        self._poll_spin.setSingleStep(250)
        self._poll_spin.setSuffix(" ms")
        self._poll_spin.setValue(current_values["poll_interval_ms"])
        form.addRow("Poll interval", self._poll_spin)

        self._units_combo = QComboBox()
        self._units_combo.addItems(["W", "mW"])
        self._units_combo.setCurrentText(current_values["power_units"])
        form.addRow("Power display units", self._units_combo)

        self._energy_units_combo = QComboBox()
        self._energy_units_combo.addItems(ENERGY_UNIT_OPTIONS)
        self._energy_units_combo.setCurrentText(current_values["energy_units"])
        form.addRow("Energy display units", self._energy_units_combo)

        self._chart_window_combo = QComboBox()
        self._chart_window_combo.addItems([label for label, _ in CHART_WINDOW_OPTIONS])
        current_seconds = current_values["chart_window_seconds"]
        for label, seconds in CHART_WINDOW_OPTIONS:
            if seconds == current_seconds:
                self._chart_window_combo.setCurrentText(label)
                break
        form.addRow("Chart time window", self._chart_window_combo)

        self._alert_spin = QDoubleSpinBox()
        self._alert_spin.setRange(0.0, 1000.0)
        self._alert_spin.setDecimals(2)
        self._alert_spin.setSpecialValueText("Disabled")
        self._alert_spin.setValue(current_values["alert_cost_threshold"])
        form.addRow("Cost alert threshold", self._alert_spin)

        self._autostart_check = QCheckBox("Start EcoThread when Windows starts")
        self._autostart_check.setChecked(autostart.is_enabled())
        form.addRow("", self._autostart_check)

        layout.addLayout(form)

        hint = QLabel(
            "TDP scaling is a heuristic estimate, not a hardware power sensor reading."
        )
        hint.setWordWrap(True)
        hint.setObjectName("metricLabel")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_profile(self, profile_name: str):
        preset = POWER_PROFILES.get(profile_name)
        if preset is None:
            return
        tdp_watts, idle_watts = preset
        self._updating_from_profile = True
        self._tdp_spin.setValue(tdp_watts)
        self._idle_spin.setValue(idle_watts)
        self._updating_from_profile = False

    def _mark_custom_profile(self):
        if not self._updating_from_profile:
            self._profile_combo.setCurrentText("Custom")

    def values(self) -> dict:
        chart_window_seconds = SETTINGS_DEFAULTS["chart_window_seconds"]
        for label, seconds in CHART_WINDOW_OPTIONS:
            if label == self._chart_window_combo.currentText():
                chart_window_seconds = seconds
                break

        return {
            "tdp_watts": self._tdp_spin.value(),
            "idle_baseline_watts": self._idle_spin.value(),
            "carbon_intensity_g_per_kwh": self._carbon_spin.value(),
            "electricity_price_per_kwh": self._price_spin.value(),
            "currency_symbol": self._currency_combo.currentText(),
            "poll_interval_ms": self._poll_spin.value(),
            "power_units": self._units_combo.currentText(),
            "energy_units": self._energy_units_combo.currentText(),
            "alert_cost_threshold": self._alert_spin.value(),
            "chart_window_seconds": chart_window_seconds,
        }

    def start_with_windows(self) -> bool:
        return self._autostart_check.isChecked()
