"""Background QThread worker: polls tracked target processes and emits energy stats.

Supports tracking multiple target PIDs simultaneously, each with its own
independent EnergyCalculator accumulator (so pausing/resetting/removing one
tracked process never affects another's running totals). The full-system
process list backing the picker table is handled separately by
ProcessScanner, so a slow full scan never delays these per-target updates.
"""

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

from core.energy_calculator import (
    DEFAULT_ELECTRICITY_PRICE_PER_KWH,
    DEFAULT_PACKAGE_TDP_WATTS,
    GRID_CARBON_INTENSITY_G_PER_KWH,
    IDLE_BASELINE_WATTS,
    EnergyCalculator,
)

CONFIG_KEYS = ("tdp_watts", "idle_baseline_watts", "carbon_intensity_g_per_kwh", "electricity_price_per_kwh")
_CONFIG_TO_ATTR = {
    "tdp_watts": "package_tdp_watts",
    "idle_baseline_watts": "idle_baseline_watts",
    "carbon_intensity_g_per_kwh": "carbon_intensity_g_per_kwh",
    "electricity_price_per_kwh": "electricity_price_per_kwh",
}

SYSTEM_WIDE_PID = -1
SYSTEM_WIDE_NAME = "Whole System (All Processes)"


class ProcessMonitor(QThread):
    """Polls tracked target processes every tick; emits CPU%, thread count, watts, joules, gCO2, cost.

    psutil.Process.cpu_percent(None) is only meaningful when called twice on the
    SAME Process instance (it diffs against the previous call). Creating a fresh
    Process object every tick always returns 0.0. So cached Process objects are
    kept alive across polls instead of re-querying psutil.Process(pid) each time.
    """

    stats_updated = pyqtSignal(dict)
    target_removed = pyqtSignal(int, str)

    DEFAULT_POLL_INTERVAL_MS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._paused = False
        self._poll_interval_ms = self.DEFAULT_POLL_INTERVAL_MS
        self._targets = {}
        self._config = {
            "tdp_watts": DEFAULT_PACKAGE_TDP_WATTS,
            "idle_baseline_watts": IDLE_BASELINE_WATTS,
            "carbon_intensity_g_per_kwh": GRID_CARBON_INTENSITY_G_PER_KWH,
            "electricity_price_per_kwh": DEFAULT_ELECTRICITY_PRICE_PER_KWH,
        }
        self._logical_cores = psutil.cpu_count(logical=True) or 1

    def apply_config(self, poll_interval_ms=None, **kwargs):
        for key in CONFIG_KEYS:
            value = kwargs.get(key)
            if value is None:
                continue
            self._config[key] = value
            attr = _CONFIG_TO_ATTR[key]
            for target in self._targets.values():
                setattr(target["calculator"], attr, value)
        if poll_interval_ms is not None:
            self._poll_interval_ms = poll_interval_ms

    def set_paused(self, paused: bool):
        if self._paused and not paused:
            for target in self._targets.values():
                target["calculator"].drop_last_sample_time()
        self._paused = paused

    def add_target(self, pid: int):
        if pid in self._targets or pid == 0:
            # PID 0 (System Idle Process) reports inverted CPU% semantics on
            # Windows and would produce nonsensical wattage if tracked like a
            # normal process. The UI never offers it, but guard here too.
            return

        calculator_kwargs = {_CONFIG_TO_ATTR[key]: value for key, value in self._config.items()}
        calculator = EnergyCalculator(logical_core_count=self._logical_cores, **calculator_kwargs)

        if pid == SYSTEM_WIDE_PID:
            psutil.cpu_percent(None)  # prime the system-wide counter
            self._targets[pid] = {"process": None, "calculator": calculator}
            return

        try:
            process = psutil.Process(pid)
            process.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
        self._targets[pid] = {"process": process, "calculator": calculator}

    def remove_target(self, pid: int):
        self._targets.pop(pid, None)

    def clear_targets(self):
        self._targets.clear()

    def reset_target(self, pid: int):
        target = self._targets.get(pid)
        if target:
            target["calculator"].reset()

    def reset_all_targets(self):
        for target in self._targets.values():
            target["calculator"].reset()

    def run(self):
        self._running = True
        while self._running:
            if not self._paused:
                self._emit_target_stats()
            self.msleep(self._poll_interval_ms)

    def stop(self):
        self._running = False
        self.wait()

    def _emit_target_stats(self):
        for pid in list(self._targets.keys()):
            target = self._targets[pid]
            process = target["process"]
            calculator = target["calculator"]

            if pid == SYSTEM_WIDE_PID:
                cpu_percent_system = psutil.cpu_percent(None)
                watts = calculator.estimate_watts_normalized(cpu_percent_system / 100.0)
                total_joules = calculator.accumulate(watts)
                self.stats_updated.emit({
                    "pid": pid,
                    "name": SYSTEM_WIDE_NAME,
                    "cpu_percent": cpu_percent_system,
                    "thread_count": len(psutil.pids()),
                    "memory_mb": psutil.virtual_memory().used / (1024 * 1024),
                    "watts": watts,
                    "total_joules": total_joules,
                    "carbon_grams": calculator.total_carbon_grams(),
                    "cost": calculator.total_cost(),
                })
                continue

            try:
                cpu_percent = process.cpu_percent(None)
                thread_count = process.num_threads()
                memory_mb = process.memory_info().rss / (1024 * 1024)
                name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                self.target_removed.emit(pid, str(exc))
                del self._targets[pid]
                continue

            watts = calculator.estimate_watts(cpu_percent)
            total_joules = calculator.accumulate(watts)
            carbon_grams = calculator.total_carbon_grams()
            cost = calculator.total_cost()

            self.stats_updated.emit({
                "pid": pid,
                "name": name,
                "cpu_percent": cpu_percent,
                "thread_count": thread_count,
                "memory_mb": memory_mb,
                "watts": watts,
                "total_joules": total_joules,
                "carbon_grams": carbon_grams,
                "cost": cost,
            })
