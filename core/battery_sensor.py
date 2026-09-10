"""Optional sanity-check against real battery discharge rate (laptops only, best-effort).

The TDP-scaling heuristic in EnergyCalculator has no hardware power sensor
backing it. On a laptop running on battery, Windows exposes an actual
discharge rate (mW) via WMI's root\\wmi BatteryStatus class. When available,
this gives the user a real number to compare the heuristic against. Requires
the optional `wmi` package (pip install wmi pywin32); silently unavailable
otherwise. Never a hard dependency, never raises.
"""

try:
    import wmi
    _WMI_AVAILABLE = True
except ImportError:
    _WMI_AVAILABLE = False


def is_available() -> bool:
    return _WMI_AVAILABLE


def get_battery_discharge_watts():
    """Return current system-wide battery discharge rate in watts, or None if unavailable."""
    if not _WMI_AVAILABLE:
        return None
    try:
        connection = wmi.WMI(namespace="root\\wmi")
        battery_statuses = connection.BatteryStatus()
        if not battery_statuses:
            return None
        status = battery_statuses[0]
        if not getattr(status, "Discharging", False):
            return None
        discharge_rate_mw = getattr(status, "DischargeRate", None)
        if not discharge_rate_mw:
            return None
        return abs(discharge_rate_mw) / 1000.0
    except Exception:
        return None
