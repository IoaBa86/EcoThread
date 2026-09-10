"""Settings dialog: TDP/idle/carbon-intensity/poll-interval config and display units."""

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

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
}


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
    """Modal dialog exposing energy-model parameters and display units."""

    def __init__(self, current_values: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._tdp_spin = QDoubleSpinBox()
        self._tdp_spin.setRange(1.0, 500.0)
        self._tdp_spin.setSuffix(" W")
        self._tdp_spin.setValue(current_values["tdp_watts"])
        form.addRow("Package TDP", self._tdp_spin)

        self._idle_spin = QDoubleSpinBox()
        self._idle_spin.setRange(0.0, 100.0)
        self._idle_spin.setSuffix(" W")
        self._idle_spin.setValue(current_values["idle_baseline_watts"])
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

        self._alert_spin = QDoubleSpinBox()
        self._alert_spin.setRange(0.0, 1000.0)
        self._alert_spin.setDecimals(2)
        self._alert_spin.setSpecialValueText("Disabled")
        self._alert_spin.setValue(current_values["alert_cost_threshold"])
        form.addRow("Cost alert threshold", self._alert_spin)

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

    def values(self) -> dict:
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
        }
