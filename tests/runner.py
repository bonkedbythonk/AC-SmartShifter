"""Load the Python build with stubs in place and step it against the car sim."""
import sys, os, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'apps', 'python', 'SmartShifter'))
import acstub, carsim

AC_ROOT = os.environ.get('AC_ROOT', r'C:\Program Files (x86)\Steam\steamapps\common\assettocorsa')
CARS = os.path.join(AC_ROOT, 'content', 'cars')
TEST_CAR = os.environ.get('AC_TEST_CAR', 'mlgz_prvvy_bmw_m340i_2023')

VK_UP, VK_DOWN, VK_MODE = 0x50, 0x4F, 0x4D


def load_app(car_name, mode, redline=None, idle=None):
    """Fresh import of the app with the AC stubs installed.

    The app reads its redline from shared memory, which does not exist here,
    so tests pass the car's real limiter in explicitly.
    """
    acstub.install()
    acstub.TELEM.car_name = car_name
    if 'SmartShifter' in sys.modules:
        del sys.modules['SmartShifter']
    app = importlib.import_module('SmartShifter')
    app.acMain(1.0)
    app.state['mode'] = mode
    if redline is not None:
        app.state['redline_rpm'] = redline
    if idle is not None:
        app.state['idle_rpm'] = idle
    return app


class Sim(object):
    def __init__(self, car, gear=1, speed_kmh=0.0):
        self.car = car
        self.gear = gear                # 1-based forward gear
        self.v = speed_kmh / 3.6
        self.cut = 0.0
        self.rpm_override = None
        self.wasted_up = 0
        self.wasted_down = 0
        self.shifts = []

    @property
    def rpm(self):
        if self.rpm_override is not None:
            return self.rpm_override
        return min(self.car.rpm_for(self.gear, self.v), self.car.limiter)

    def apply_keys(self, t):
        for kind, vk in acstub.KEY_EVENTS:
            if kind != 'down':
                continue
            if vk == VK_UP:
                if self.gear < self.car.n_gears:
                    self.shifts.append((t, self.gear, self.gear + 1, self.rpm, self.v * 3.6, 'UP'))
                    self.gear += 1
                    self.cut = 0.18
                else:
                    self.wasted_up += 1
            elif vk == VK_DOWN:
                if self.gear > 1:
                    self.shifts.append((t, self.gear, self.gear - 1, self.rpm, self.v * 3.6, 'DN'))
                    self.gear -= 1
                    self.cut = 0.18
                else:
                    self.wasted_down += 1
        del acstub.KEY_EVENTS[:]

    def step(self, dt, gas, brake):
        c = self.car
        f = 0.0 if self.cut > 0 else c.drive_force(self.gear, self.rpm, gas)
        f -= c.resist(self.v)
        f -= brake * 1.05 * c.mass * 9.81 * (1.0 if self.v > 0.5 else 0.0)
        self.v = max(0.0, self.v + (f / c.mass) * dt)
        self.cut = max(0.0, self.cut - dt)


def run(car, app, seconds, control, gear=1, speed_kmh=0.0, dt=1 / 60.0, mode_taps=()):
    """Step app and sim together. control(t, sim) -> (gas, brake, steer)."""
    sim = Sim(car, gear, speed_kmh)
    del acstub.KEY_EVENTS[:]
    t = 0.0
    trace = []
    taps = list(mode_taps)
    while t < seconds:
        gas, brake, steer = control(t, sim)
        acstub.USER32.async_keys[VK_MODE] = any(a <= t < b for a, b in taps)
        te = acstub.TELEM
        te.rpm = sim.rpm
        te.gas = gas
        te.brake = brake
        te.gear = sim.gear + 1            # AC python API: 0=R 1=N 2=1st
        te.speed_kmh = sim.v * 3.6
        te.steer = steer
        app.acUpdate(dt)
        sim.apply_keys(t)
        sim.step(dt, gas, brake)
        trace.append((t, sim.gear, sim.rpm, sim.v * 3.6, gas, brake))
        t += dt
    return sim, trace
