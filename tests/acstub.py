"""Stub AC runtime + SendInput interceptor so SmartShifter.py can run off-game."""
import ctypes as _ct
import sys, types

# ---- capture keyboard events instead of injecting them into Windows ----
KEY_EVENTS = []   # list of (kind, vk) ; kind = 'down' | 'up'

class _FakeUser32(object):
    def __init__(self):
        self.async_keys = {}          # vk -> bool, controlled by the test
    def SendInput(self, n, p, size):
        inp = p.contents
        vk = inp.ii.ki.wVk
        flags = inp.ii.ki.dwFlags
        KEY_EVENTS.append(('up' if flags & 0x0002 else 'down', vk))
        return 1
    def GetAsyncKeyState(self, vk):
        return 0x8000 if self.async_keys.get(vk) else 0

class _FakeWinDLL(object):
    def __init__(self):
        self.user32 = _FakeUser32()

USER32 = None
def patch_ctypes():
    global USER32
    fake = _FakeWinDLL()
    USER32 = fake.user32
    _ct.windll = fake
    return fake.user32

# ---- telemetry the stubbed ac module serves ----
class Telemetry(object):
    def __init__(self):
        self.rpm = 0.0
        self.gas = 0.0
        self.brake = 0.0
        self.gear = 1          # AC convention: 0=R, 1=N, 2=1st
        self.speed_kmh = 0.0
        self.steer = 0.0
        self.car_name = 'test_car'

TELEM = Telemetry()

# ---- fake acsys ----
acsys = types.ModuleType('acsys')
class _CS(object):
    RPM = 'RPM'; Gas = 'Gas'; Brake = 'Brake'; Gear = 'Gear'
    SpeedKMH = 'SpeedKMH'; Steer = 'Steer'
acsys.CS = _CS

# ---- fake ac ----
ac = types.ModuleType('ac')
LABELS = {}        # id -> {'text':..., 'color':...}
_next_id = [100]

def _nid():
    _next_id[0] += 1
    return _next_id[0]

ac.CALLS = []
def _rec(name):
    def f(*a, **k):
        ac.CALLS.append((name, a))
        return 0
    return f

ac.newApp   = lambda name: _nid()
ac.addButton = lambda w, t: _nid()
ac.addLabel = lambda w, t: (lambda i: (LABELS.__setitem__(i, {'text': t, 'color': None}), i)[1])(_nid())
def _setText(i, t):
    LABELS.setdefault(i, {})['text'] = t
def _setFontColor(i, r, g, b, a):
    LABELS.setdefault(i, {})['color'] = (r, g, b, a)
ac.setText = _setText
ac.setFontColor = _setFontColor
for _n in ('setSize','setTitle','setIconPosition','setBackgroundOpacity','drawBorder',
           'drawBackground','setPosition','setFontSize','log','console','addOnClickedListener'):
    setattr(ac, _n, _rec(_n))

def _getCarState(car, which):
    t = TELEM
    return {'RPM': t.rpm, 'Gas': t.gas, 'Brake': t.brake, 'Gear': t.gear,
            'SpeedKMH': t.speed_kmh, 'Steer': t.steer}[which]
ac.getCarState = _getCarState
ac.getCarName = lambda car: TELEM.car_name

def install():
    """Put the stubs in sys.modules and neuter ctypes.windll."""
    sys.modules['ac'] = ac
    sys.modules['acsys'] = acsys
    return patch_ctypes()
