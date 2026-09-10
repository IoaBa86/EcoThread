# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.1]

### Fixed
- Replaced the generic rounded-square app icon with a distinctive leaf
  mark, and rebuilt the release executable with it (the v0.1.0 build still
  had the old placeholder icon baked in).

## [0.1.0]

First tagged release.

### Added
- Dashboard: searchable process table, live multi-process wattage chart,
  running energy/carbon/cost summary cards.
- CPU-usage-based wattage estimation model (configurable TDP and idle
  baseline), dark theme UI.
- Track multiple processes at once, each with its own chart line and
  independent energy accumulator, or track the whole system as a single
  combined target.
- Energy display units (J / Wh / kWh, explicit or auto-scaled) and
  estimated electricity cost with configurable currency and price per kWh.
- Baseline capture, pause/resume, reset-session, and CSV export.
- System tray integration: minimizing keeps profiling running in the
  background; a tray notification can fire past a configurable cost
  threshold. Session CSV auto-saved on exit.
- Optional battery-discharge sanity check on laptops (via the `wmi`
  package, if installed).
- Power profile presets (typical laptop/desktop TDPs), configurable chart
  time window, "start with Windows" toggle.
- Average/peak wattage summary in exports, and shown live per tracked
  process.
- Settings export/import as a JSON file.
- In-app Help and About dialogs.
- Test suite covering the energy model and process-tracking behavior.
- CI (tests on every push/PR) and a release workflow that builds a
  standalone Windows executable from a version tag.

### Fixed
- The live chart could go blank after any pan/zoom interaction, since the
  view stopped auto-ranging. Mouse interaction is now disabled and
  auto-range is re-applied on every update.
- CPU% for a tracked process always read 0%, because a fresh
  `psutil.Process` object was queried on every poll. `cpu_percent()` only
  returns meaningful values across repeated calls on the *same* object, so
  process handles are now cached and reused.
- Process table took over ten seconds to populate on startup (full-scan
  cost for every running process). Names now show immediately, with
  CPU%/memory backfilled in the background on a separate thread so it
  never blocks the live chart.
