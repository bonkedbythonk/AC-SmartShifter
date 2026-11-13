# SmartShifter

A custom automatic transmission mod for Assetto Corsa. It reads telemetry to shift gears logically instead of relying on speed tables.

Since v2.0 it is a Custom Shaders Patch (CSP) Lua app. It shifts through CSP's car-controls override instead of fake keypresses, so it works with any key bindings, with any car, and online.

### Features
- **Dynamic shifting:** Shift points scale with how hard you press the gas and brake.
- **Wheelspin detection:** Won't shift up while you're doing a burnout or sliding (reads per-wheel slip from CSP).
- **Driving modes:** Press **M** (or click the app) to cycle between Comfort (cruising/low RPM), Sport, Sport+ (track), Drift (bounces limiter), and Manual.
- **Works with any car:** Redline, idle and gear count come from the car itself. Cars with no rev limiter fall back to the limiter in `engine.ini`, and if that has none either, you floor it once and it learns and saves the redline for that car.
- **Online-friendly:** Never touches reverse or neutral. Warns you if a server blocks the shifts, if AC's own auto-shift assist is on, or if auto-clutch is off.

### Requirements
- Custom Shaders Patch 0.2 or newer (most public servers require it anyway).
- In-game assists: turn **off** AC's automatic gearbox (SmartShifter does the shifting). Leave **auto-clutch on** if the server allows it; otherwise you have to work the clutch yourself at a stop.

### Installation
1. Copy the `SmartShifter` folder into `assettocorsa/apps/lua/`, so you end up with `apps/lua/SmartShifter/manifest.ini`.
2. In-game, open the app from the right-side app menu.

### Usage
- **M** or left-click the app: cycle modes. Rebind it in Content Manager under Controls → Patch → "SmartShifter/Cycle Mode".
- Right-click the app: forget a learned redline (only matters for cars without a limiter).

### Legacy Python version
The original Python app (v1, keypress-based) is in `legacy-python/`. It needs your gear-shift keys bound to P/O and the game window focused, so the Lua version is recommended.
