"""Regression tests for the CPU% caching bug: cpu_percent(None) only means
anything when called twice on the SAME psutil.Process object. A rewrite that
starts constructing a fresh Process() per tick would silently break this."""

import os
import time

from core.process_monitor import SYSTEM_WIDE_PID, ProcessMonitor


def test_add_target_keeps_the_same_process_object_across_calls():
    monitor = ProcessMonitor()
    pid = os.getpid()
    monitor.add_target(pid)

    process_obj = monitor._targets[pid]["process"]
    monitor._emit_target_stats()
    monitor._emit_target_stats()

    assert monitor._targets[pid]["process"] is process_obj


def test_emit_target_stats_reports_nonzero_cpu_for_a_busy_process():
    monitor = ProcessMonitor()
    monitor.apply_config(poll_interval_ms=10)
    pid = os.getpid()
    monitor.add_target(pid)

    received = []
    monitor.stats_updated.connect(lambda stats: received.append(stats))

    # Burn CPU on this process so cpu_percent(None) has something to diff
    # against; a regression to fresh Process()-per-tick would report 0.0
    # here regardless of load.
    monitor._emit_target_stats()  # primes the diff baseline
    deadline = time.monotonic() + 1.0
    x = 0
    while time.monotonic() < deadline:
        x += 1
    monitor._emit_target_stats()

    # _emit_target_stats() always emits, even on the priming call (which
    # reports 0.0% since it has no prior sample to diff against yet).
    assert len(received) == 2
    assert received[0]["cpu_percent"] == 0.0
    assert received[1]["cpu_percent"] > 0.0


def test_each_target_gets_an_independent_energy_calculator():
    monitor = ProcessMonitor()
    pid_a = os.getpid()
    pid_b = os.getppid()
    monitor.add_target(pid_a)
    monitor.add_target(pid_b)

    assert monitor._targets[pid_a]["calculator"] is not monitor._targets[pid_b]["calculator"]


def test_remove_target_stops_tracking():
    monitor = ProcessMonitor()
    pid = os.getpid()
    monitor.add_target(pid)
    assert pid in monitor._targets

    monitor.remove_target(pid)
    assert pid not in monitor._targets


def test_system_wide_target_uses_normalized_cpu_percent():
    monitor = ProcessMonitor()
    monitor.add_target(SYSTEM_WIDE_PID)

    received = []
    monitor.stats_updated.connect(lambda stats: received.append(stats))
    monitor._emit_target_stats()

    assert len(received) == 1
    stats = received[0]
    assert stats["pid"] == SYSTEM_WIDE_PID
    assert 0.0 <= stats["cpu_percent"] <= 100.0


def test_pid_zero_system_idle_process_is_never_a_valid_target():
    # System Idle Process reports inverted CPU% semantics on Windows and
    # would produce nonsensical wattage if treated like a normal process.
    monitor = ProcessMonitor()
    monitor.add_target(0)
    assert 0 not in monitor._targets
