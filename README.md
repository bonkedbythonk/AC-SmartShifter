# SmartShifter

An automatic gearbox for Assetto Corsa that shifts on what the car is doing, not on a speed table.

- **Dynamic shift points** that scale with throttle and brake.
- **Holds gears** while cornering and while the driven wheels are spinning up.
- **Five modes:** Comfort (low revs, early upshifts), Sport, Sport+ (track), Drift (sits on the limiter) and Manual.
- **No calibration.** Redline, idle and gear count come straight from the sim.

## Requirements

[Custom Shaders Patch](https://acstuff.club/patch/) 0.2.x. The app reads the car's limiter, idle, gear count and wheel slip through CSP's Lua API and shifts through `ac.overrideCarControls`, so it works with any input device and on any server that runs CSP.

## Installation

Drag the release zip onto Content Manager, or copy `apps/lua/SmartShifter` into `assettocorsa/apps/lua/`. The app appears in the in-game app bar as **SmartShifter**.

## Usage

- Press **M** to cycle Comfort → Sport → Sport+ → Drift → Manual. The key is rebindable in Content Manager under **Settings → Controls → Patch → SmartShifter/Cycle Mode**.
- Clicking the app window also cycles modes.
- The selected mode is remembered between sessions.

## Python fallback (no CSP)

`apps/python/SmartShifter` is an older build for installs without CSP. It reads the redline from AC's shared memory, takes the shift keys from your `controls.ini`, and sends them as keypresses. Enable it under **Settings → Assetto Corsa → Python Apps**, and do **not** run it together with the Lua app. An optional `settings.json` next to it overrides the mode key: `{"mode_key": 77}` (decimal virtual-key code; 77 is M).

## Development

`tests/` contains an offline harness that runs the Python build's shift logic against real car data from your AC install. See [tests/README.md](tests/README.md).
