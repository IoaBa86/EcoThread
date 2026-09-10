"""Background QThread worker: scans the full system process list for the picker table.

Runs on its own thread, separate from ProcessMonitor's per-target polling, so
a slow full-system scan never delays the live chart for tracked processes.
"""

import psutil
from PyQt6.QtCore import QThread, pyqtSignal


class ProcessScanner(QThread):
    """Periodically lists every running process with CPU% and memory.

    Scanning every process for CPU%/memory costs roughly 6ms per process per
    attribute (Windows has no batch syscall for this via psutil), so a
    ~450-process machine costs several seconds for a full scan. That cost is
    isolated to this thread so it never blocks ProcessMonitor's target
    updates, which need to stay responsive every poll tick.
    """

    process_list_updated = pyqtSignal(list)

    DEFAULT_SCAN_INTERVAL_MS = 4000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._scan_interval_ms = self.DEFAULT_SCAN_INTERVAL_MS
        self._process_cache = {}
        self._logical_cores = psutil.cpu_count(logical=True) or 1

    def set_scan_interval_ms(self, interval_ms: int):
        self._scan_interval_ms = interval_ms

    def run(self):
        self._running = True
        self._emit_quick_initial_list()
        self._prime_process_cache()
        while self._running:
            self._emit_process_list()
            self.msleep(self._scan_interval_ms)

    def stop(self):
        self._running = False
        self.wait()

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
