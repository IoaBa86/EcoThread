# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Continuous integration: tests run automatically on every push and pull request.
- Release workflow: pushing a `v*.*.*` tag builds and publishes a standalone
  Windows executable.
- Live per-process average and peak wattage, shown alongside the chart.
- Settings export/import, so a configuration can be shared as a file.

## [0.3.0]

### Added
- Power profile presets (typical laptop/desktop TDPs) alongside fully
  custom values.
- Configurable chart time window (1 to 30 minutes).
- Optional "start with Windows" toggle.
- Average/peak wattage summary appended to exported and auto-saved session
  CSVs, plus an "Open Sessions Folder" button.
- Test suite covering the energy model and process-tracking behavior.
- Standalone executable packaging (PyInstaller) with a proper app icon.

### Changed
- The full-system process scan now runs on its own background thread,
  separate from per-tracked-process polling, so a slow scan no longer
  pauses the live chart.
- Process table startup time cut from over ten seconds to well under a
  second by showing names immediately and backfilling CPU%/memory in the
  background.

## [0.2.0]

### Added
- Track multiple processes at once, each with its own chart line and
  independent energy accumulator.
- Track the whole system as a single combined target.
- Energy display units (J / Wh / kWh, explicit or auto-scaled).
- Estimated electricity cost, with configurable currency and price per kWh.
- Baseline capture, to compare current draw against an earlier snapshot.
- Pause/resume and reset-session controls.
- CSV export of the current session.
- System tray integration: minimizing keeps profiling running in the
  background; a tray notification can fire past a configurable cost
  threshold.
- Session CSV auto-saved on exit.
- Optional battery-discharge sanity check on laptops (via the `wmi`
  package, if installed).
- In-app Help and About dialogs.

### Fixed
- The live chart could go blank after any pan/zoom interaction, since the
  view stopped auto-ranging. Mouse interaction is now disabled and
  auto-range is re-applied on every update.
- CPU% for a tracked process always read 0%, because a fresh
  `psutil.Process` object was queried on every poll. `cpu_percent()` only
  returns meaningful values across repeated calls on the *same* object, so
  process handles are now cached and reused.

## [0.1.0]

### Added
- Initial dashboard: searchable process table, live wattage chart,
  running energy/carbon summary cards.
- CPU-usage-based wattage estimation model (configurable TDP and idle
  baseline).
- Dark theme UI.
- Settings dialog for the energy model parameters.
- About dialog.
