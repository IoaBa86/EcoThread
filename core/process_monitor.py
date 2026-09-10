"""Background QThread worker: polls psutil for process stats and emits signals.

Supports tracking multiple target PIDs simultaneously, each with its own
independent EnergyCalculator accumulator (so pausing/resetting/removing one
tracked process never affects another's running totals).
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
    process_list_updated = pyqtSignal(list)
    target_removed = pyqtSignal(int, str)

    DEFAULT_POLL_INTERVAL_MS = 1000
    # Scanning every process for CPU%/memory costs roughly 6ms per process
    # per attribute (Windows has no batch syscall for this via psutil), so a
    # ~450-process machine costs several seconds for a full scan. Tracked
    # targets are refreshed every poll_interval_ms; the full process list
    # backing the picker table is refreshed on this slower, separate cadence
    # so it doesn't dominate every tick.
    DEFAULT_LIST_REFRESH_INTERVAL_MS = 4000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._paused = False
        self._poll_interval_ms = self.DEFAULT_POLL_INTERVAL_MS
        self._list_refresh_interval_ms = self.DEFAULT_LIST_REFRESH_INTERVAL_MS
        self._ms_since_last_list_refresh = 0
        self._process_cache = {}
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
        if pid in self._targets:
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
        self._emit_quick_initial_list()
        self._prime_process_cache()
        self._emit_process_list()
        self._ms_since_last_list_refresh = 0
        while self._running:
            if not self._paused:
                self._emit_target_stats()
            self.msleep(self._poll_interval_ms)
            self._ms_since_last_list_refresh += self._poll_interval_ms
            if self._ms_since_last_list_refresh >= self._list_refresh_interval_ms:
                self._emit_process_list()
                self._ms_since_last_list_refresh = 0

    def _emit_quick_initial_list(self):
        """Populate the table almost instantly with names/PIDs only.

        proc.name() across every process costs ~20ms total; cpu_percent()
        and memory_info() each cost ~3s (real per-process Windows syscalls,
        not exception overhead). Showing names immediately and backfilling
        the expensive columns a moment later avoids a multi-second blank
        table on startup.
        """
        processes = []
        for proc in psutil.process_iter(["pid", "name"]):
            pid = proc.info["pid"]
            if pid == 0:
                continue
            processes.append({
                "pid": pid,
                "name": proc.info["name"] or "",
                "cpu_percent": 0.0,
                "cpu_percent_normalized": 0.0,
                "memory_mb": 0.0,
            })
        self.process_list_updated.emit(processes)

    def _prime_process_cache(self):
        """Warm every process's cpu_percent() baseline up front.

        cpu_percent(None) needs a prior call on the same Process object
        before it returns anything meaningful, so a newly-seen PID is
        skipped on the tick it's first discovered. Priming everything before
        the loop starts means the first full scan is already useful.
        """
        for proc in psutil.process_iter(["pid", "name"]):
            pid = proc.info["pid"]
            if pid == 0 or pid in self._process_cache:
                continue
            try:
                proc.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            self._process_cache[pid] = (proc, proc.info["name"] or "")

    def stop(self):
        self._running = False
        self.wait()

    def _emit_process_list(self):
        current_pids = set(psutil.pids())

        for stale_pid in list(self._process_cache.keys()):
            if stale_pid not in current_pids:
                del self._process_cache[stale_pid]

        processes = []
        for pid in current_pids:
            if pid == 0:
                # "System Idle Process": on Windows, psutil reports its CPU%
                # as idle time (not load), which is the inverse of every
                # other process and produces nonsensical wattage estimates.
                # Not a real app a user would want to profile, so it's excluded.
                continue

            cached = self._process_cache.get(pid)
            if cached is None:
                try:
                    proc = psutil.Process(pid)
                    name = proc.name()
                    proc.cpu_percent(None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                self._process_cache[pid] = (proc, name)
                continue

            proc, name = cached
            try:
                cpu_percent_raw = proc.cpu_percent(None)
                memory_mb = proc.memory_info().rss / (1024 * 1024)
                processes.append({
                    "pid": pid,
                    "name": name,
                    "cpu_percent": cpu_percent_raw,
                    "cpu_percent_normalized": cpu_percent_raw / self._logical_cores,
                    "memory_mb": memory_mb,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                del self._process_cache[pid]
                continue

        self.process_list_updated.emit(processes)

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
