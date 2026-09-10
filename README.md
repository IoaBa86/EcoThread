# EcoThread

A desktop power and carbon profiler for Windows. Pick one or more running
processes (or the whole system) and watch estimated wattage, energy use,
carbon output, and electricity cost update live.

## Why

CPU and memory tools are everywhere. Nothing on Windows shows you an
estimate of what a process is actually costing in watts, kWh, or money
while it runs. EcoThread is a small dashboard for that.

## Features

- Track multiple processes at once, each with its own line on the chart
- Track the whole system as a single combined reading
- Running totals for energy (J / Wh / kWh), estimated CO2, and estimated
  electricity cost, in your own currency and price per kWh
- Pause, reset, and CSV export for a session, with an average/peak wattage
  summary included
- Baseline capture, so you can compare "now" against a snapshot from
  earlier in the session
- Adjustable chart time window (1 to 30 minutes)
- Power profile presets (typical laptop/desktop TDPs) or fully custom values
- Minimizes to the system tray instead of quitting, and keeps profiling
  in the background
- Optional "start with Windows" toggle
- Session CSV auto-saved to `Documents/EcoThread/sessions` on exit
- Optional cost alert (tray notification past a threshold you set)
- Optional battery-discharge sanity check on laptops, if the `wmi`
  package is installed

## Installing

```
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+ and Windows (uses `psutil` and, optionally, `wmi`
for the battery check; the process model relies on Windows-specific
`psutil` behavior).

## How the numbers are estimated

There's no per-process power sensor on a consumer PC. EcoThread estimates
wattage from a process's CPU usage against a configurable package TDP and
idle baseline (`Settings > Preferences`). It's a reasonable heuristic for
comparing processes against each other, not a hardware measurement. The
in-app Help menu and About dialog cover this in more detail, and the
"Whole System" chart will show a real battery discharge reading next to
the estimate on a laptop, if `wmi` is installed, as a sanity check.

## Project layout

```
main.py                    entry point
core/
  process_monitor.py       per-target polling thread (psutil), one energy
                            calculator per tracked process
  process_scanner.py       separate thread that scans the full process list
                            for the picker table, so it never blocks the
                            live chart
  energy_calculator.py     CPU% -> watts/joules/carbon/cost model
  battery_sensor.py        optional battery-discharge reading (WMI)
  autostart.py             "start with Windows" registry toggle
gui/
  main_window.py           dashboard: table, chart, controls, tray icon
  settings_dialog.py       energy model + units + alerts configuration
  help_dialog.py           in-app instructions
  about_dialog.py          app info
  styles.py                dark theme stylesheet
tests/                     pytest suite for the energy model and the
                            process-monitor CPU% caching behavior
assets/icon.ico            app icon (taskbar, tray, packaged exe)
```

## Development

```
pip install -r requirements-dev.txt
pytest
```

## Building a standalone executable

```
pip install -r requirements-dev.txt
pyinstaller ecothread.spec
```

The executable is written to `dist/EcoThread.exe`. It's a single file with
no console window and the app icon bundled in.

## License

MIT. See [LICENSE](LICENSE).

## Author

Ioannis Bakas, [ibakas.com](https://ibakas.com)
