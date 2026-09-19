# Offline test harness

Runs the Python build's real `acUpdate()` loop outside the game. `ac` and `acsys` are stubbed, `SendInput` is intercepted and recorded, and a small longitudinal model is driven by an actual car's `drivetrain.ini`, `engine.ini`, `power.lut`, `tyres.ini` and `car.ini`, so shift points are checked against real gearing and a real limiter.

The Lua build is not covered here; CSP's Lua runs only inside the game.

## Setup

Any Python 3 works. On a machine without one, drop the [embeddable package](https://www.python.org/downloads/windows/) into `tests/py/` (ignored by git).

Point the harness at your install if it is not in the default Steam location:

```bash
set AC_ROOT=D:\SteamLibrary\steamapps\common\assettocorsa
```

The scenarios use a car with an unpacked `data/` folder. The default is `mlgz_prvvy_bmw_m340i_2023`; override with `AC_TEST_CAR=<car folder>`.

## Run

```bash
cd tests
python regress.py
```

`regress.py` covers full-throttle runs in every mode, coasting, part-throttle cruise, hard braking, cornering, a burnout, anti-stall, Manual sending nothing, Drift's limiter bounce and frame-rate independence from 30 to 240 fps. `repro_stop.py` is the standstill case that once locked the car in top gear.

## Files

| File | Purpose |
|---|---|
| `acstub.py` | fake `ac`/`acsys`, records every synthetic keypress instead of injecting it |
| `carsim.py` | reads a car's data files and integrates speed from torque, gearing, drag and brakes |
| `runner.py` | loads the app fresh with the stubs in place and steps app + sim together |
| `regress.py` | the scenario battery |
| `repro_stop.py` | roll-to-a-stop regression, including an engine that bogs below idle |
