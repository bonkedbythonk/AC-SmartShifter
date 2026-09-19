"""Scenario battery for the Python build, against a real car's data files."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner, carsim

CAR = carsim.Car(os.path.join(runner.CARS, runner.TEST_CAR))
NM = ['COMFORT', 'SPORT', 'SPORT+', 'DRIFT', 'MANUAL']
failures = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        failures.append(msg)


def load(mode):
    return runner.load_app(CAR.name, mode, redline=CAR.limiter, idle=CAR.idle)


print('car %s: %d gears, limiter %.0f, idle %.0f' % (CAR.name, CAR.n_gears, CAR.limiter, CAR.idle))

print('\n== decisions from the field reports (top gear, 6-speed car, redline 8266, idle 1000) ==')
app = load(0)
app.state['redline_rpm'], app.state['idle_rpm'], app.state['max_gear'] = 8266.0, 1000.0, 7
app.state['last_shift_time'] = -99
check(app.autoShiftTarget(2590, 0.43, 0.0, 7, 103.5, 0.0) == 7, 'cruising in top gear does not request a gear that does not exist')
check(app.autoShiftTarget(1000, 0.0, 0.0, 7, 0.0, 0.0) < 7, 'stopped in top gear downshifts')

print('\n== full-throttle runs ==')
for mode in (0, 1, 2):
    app = load(mode)
    sim, tr = runner.run(CAR, app, 45.0, lambda t, s: (1.0, 0.0, 0.0), gear=1, speed_kmh=5)
    ups = [s[3] for s in sim.shifts if s[5] == 'UP']
    check(len(ups) >= 5 and sim.wasted_up == 0,
          '%-7s %d upshifts, none wasted, %.0f-%.0f rpm' % (NM[mode], len(ups), min(ups), max(ups)))
    if mode == 2:
        check(min(ups) > CAR.limiter * 0.9, 'SPORT+ shifts above 90%% of redline (%.0f)' % min(ups))
    if mode == 0:
        check(max(ups) < CAR.limiter * 0.8, 'COMFORT shifts below 80%% of redline (%.0f)' % max(ups))

print('\n== coasting and cruising in COMFORT (the P-spam case) ==')
app = load(0)
sim, tr = runner.run(CAR, app, 40.0, lambda t, s: (0.0, 0.0, 0.0), gear=6, speed_kmh=180)
check(sim.wasted_up <= 2, 'coast from 180: at most 2 refused upshifts while learning top gear (got %d)' % sim.wasted_up)
app = load(0)
sim, tr = runner.run(CAR, app, 20.0, lambda t, s: (0.15, 0.0, 0.0), gear=6, speed_kmh=100)
check(sim.wasted_up <= 2, 'cruise at 100: at most 2 refused upshifts (got %d)' % sim.wasted_up)

print('\n== braking to a stop ==')
for mode in (0, 1, 2):
    app = load(mode)
    sim, tr = runner.run(CAR, app, 9.0, lambda t, s: (0.0, 1.0, 0.0), gear=7, speed_kmh=200)
    check(sim.gear == 1 and sim.wasted_up == 0, '%-7s ends in 1st with no wasted taps (gear %d)' % (NM[mode], sim.gear))

print('\n== cornering at full throttle holds until near the limiter ==')
for mode in (1, 2):
    app = load(mode)
    sim, tr = runner.run(CAR, app, 12.0, lambda t, s: (1.0, 0.0, 120.0), gear=2, speed_kmh=60)
    ups = [s[3] for s in sim.shifts if s[5] == 'UP']
    check(ups and min(ups) > CAR.limiter * 0.97, '%-7s first upshift while cornering at %.0f rpm' % (NM[mode], ups[0] if ups else 0))

print('\n== the rest ==')
app = load(4)
sim, tr = runner.run(CAR, app, 20.0, lambda t, s: (1.0, 0.0, 0.0), gear=1, speed_kmh=5)
check(len(sim.shifts) + sim.wasted_up == 0, 'MANUAL sends nothing')

app = load(3)
sim, tr = runner.run(CAR, app, 45.0, lambda t, s: (1.0, 0.0, 0.0), gear=1, speed_kmh=5)
ups = [s for s in sim.shifts if s[5] == 'UP']
check(len(ups) >= 3, 'DRIFT still upshifts off the limiter every ~5 s (%d upshifts)' % len(ups))

app = load(1)
sim, tr = runner.run(CAR, app, 4.0, lambda t, s: (0.0, 0.0, 0.0), gear=4, speed_kmh=8)
check(sim.gear == 1, 'rolling at 8 km/h in 4th comes down to 1st')

first = None
for fps in (30, 60, 144, 240):
    app = load(1)
    sim, tr = runner.run(CAR, app, 40.0, lambda t, s: (1.0, 0.0, 0.0), gear=1, speed_kmh=5, dt=1.0 / fps)
    ups = [s for s in sim.shifts if s[5] == 'UP']
    if first is None:
        first = len(ups)
    check(len(ups) == first, '%3d fps: %d upshifts, first at %.0f rpm' % (fps, len(ups), ups[0][3]))

print('\n%d failure(s)' % len(failures))
sys.exit(1 if failures else 0)
