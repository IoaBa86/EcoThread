"""Estimate instantaneous wattage and carbon output from CPU utilization.

No direct per-process power sensor exists on consumer Windows hardware, so
this uses a TDP-scaling heuristic: idle draw plus a share of package TDP
proportional to (process CPU% / logical core count), non-linearly biased
toward higher draw at high utilization (thermal/frequency scaling is not
linear with load).
"""

import time


DEFAULT_PACKAGE_TDP_WATTS = 65.0
IDLE_BASELINE_WATTS = 4.0
GRID_CARBON_INTENSITY_G_PER_KWH = 400.0
DEFAULT_ELECTRICITY_PRICE_PER_KWH = 0.15


ENERGY_UNIT_OPTIONS = ["Auto", "J", "Wh", "kWh"]


def format_energy_auto(joules: float) -> str:
    """Auto-scale joules to the most readable unit: J, Wh, or kWh."""
    magnitude = abs(joules)
    if magnitude < 1000:
        return f"{joules:.1f} J"
    watt_hours = joules / 3600.0
    if watt_hours < 1000:
        return f"{watt_hours:.3f} Wh"
    return f"{watt_hours / 1000.0:.4f} kWh"


def format_energy(joules: float, unit: str = "Auto") -> str:
    """Format joules in an explicit unit ('J', 'Wh', 'kWh'), or auto-scale."""
    if unit == "J":
        return f"{joules:.1f} J"
    if unit == "Wh":
        return f"{joules / 3600.0:.4f} Wh"
    if unit == "kWh":
        return f"{joules / 3_600_000.0:.6f} kWh"
    return format_energy_auto(joules)


class EnergyCalculator:
    """Converts CPU usage into estimated watts, joules, gCO2, and electricity cost."""

    def __init__(
        self,
        package_tdp_watts: float = DEFAULT_PACKAGE_TDP_WATTS,
        idle_baseline_watts: float = IDLE_BASELINE_WATTS,
        carbon_intensity_g_per_kwh: float = GRID_CARBON_INTENSITY_G_PER_KWH,
        electricity_price_per_kwh: float = DEFAULT_ELECTRICITY_PRICE_PER_KWH,
        logical_core_count: int = 1,
    ):
        self.package_tdp_watts = package_tdp_watts
        self.idle_baseline_watts = idle_baseline_watts
        self.carbon_intensity_g_per_kwh = carbon_intensity_g_per_kwh
        self.electricity_price_per_kwh = electricity_price_per_kwh
        self.logical_core_count = max(logical_core_count, 1)

        self._total_joules = 0.0
        self._last_sample_time = None

    def estimate_watts(self, cpu_percent: float) -> float:
        """Return estimated instantaneous watts for a process CPU% (0-100, can exceed 100 on multi-core)."""
        core_fraction = max(cpu_percent, 0.0) / 100.0 / self.logical_core_count
        return self.estimate_watts_normalized(core_fraction)

    def estimate_watts_normalized(self, load_fraction: float) -> float:
        """Same model as estimate_watts, but for a load already normalized to 0-1 (e.g. system-wide CPU%)."""
        load_fraction = min(max(load_fraction, 0.0), 1.0)
        # Bias curve: sqrt weighting means low load still draws a meaningful
        # share of TDP (frequency floors, non-parked cores), while it still
        # saturates at full TDP under sustained full load.
        load_factor = load_fraction ** 0.5
        dynamic_watts = load_factor * self.package_tdp_watts
        return self.idle_baseline_watts + dynamic_watts

    def accumulate(self, watts: float) -> float:
        """Integrate watts over elapsed wall-clock time since last call; returns total joules so far."""
        now = time.monotonic()
        if self._last_sample_time is not None:
            elapsed_seconds = now - self._last_sample_time
            self._total_joules += watts * elapsed_seconds
        self._last_sample_time = now
        return self._total_joules

    def total_carbon_grams(self) -> float:
        """Convert accumulated joules to grams of CO2 using the configured grid intensity."""
        kwh = self._total_joules / 3_600_000.0
        return kwh * self.carbon_intensity_g_per_kwh

    def total_cost(self) -> float:
        """Convert accumulated joules to an estimated electricity cost using the configured price/kWh."""
        kwh = self._total_joules / 3_600_000.0
        return kwh * self.electricity_price_per_kwh

    def reset(self):
        self._total_joules = 0.0
        self._last_sample_time = None

    def drop_last_sample_time(self):
        """Discard the last sample timestamp without resetting accumulated totals.

        Call after a pause so the next accumulate() doesn't bill the paused
        duration as active wattage.
        """
        self._last_sample_time = None
