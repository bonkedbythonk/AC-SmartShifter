import ac
import acsys
import ctypes
import os
import json
import mmap

PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Shared-memory static page. The sim publishes the real rev limiter here, so the
# app no longer has to guess the redline by watching the tacho.
class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('_smVersion', ctypes.c_wchar * 15),
        ('_acVersion', ctypes.c_wchar * 15),
        ('numberOfSessions', ctypes.c_int32),
        ('numCars', ctypes.c_int32),
        ('carModel', ctypes.c_wchar * 33),
        ('track', ctypes.c_wchar * 33),
        ('playerName', ctypes.c_wchar * 33),
        ('playerSurname', ctypes.c_wchar * 33),
        ('playerNick', ctypes.c_wchar * 33),
        ('sectorCount', ctypes.c_int32),
        ('maxTorque', ctypes.c_float),
        ('maxPower', ctypes.c_float),
        ('maxRpm', ctypes.c_int32),
        ('maxFuel', ctypes.c_float),
        ('suspensionMaxTravel', ctypes.c_float * 4),
        ('tyreRadius', ctypes.c_float * 4),
        ('maxTurboBoost', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('penaltiesEnabled', ctypes.c_int32),
        ('aidFuelRate', ctypes.c_float),
        ('aidTireRate', ctypes.c_float),
        ('aidMechanicalDamage', ctypes.c_float),
        ('aidAllowTyreBlankets', ctypes.c_int32),
        ('aidStability', ctypes.c_float),
        ('aidAutoClutch', ctypes.c_int32),
        ('aidAutoBlip', ctypes.c_int32),
        ('hasDRS', ctypes.c_int32),
        ('hasERS', ctypes.c_int32),
        ('hasKERS', ctypes.c_int32),
        ('kersMaxJ', ctypes.c_float),
        ('engineBrakeSettingsCount', ctypes.c_int32),
        ('ersPowerControllerCount', ctypes.c_int32),
        ('trackSPlineLength', ctypes.c_float),
        ('trackConfiguration', ctypes.c_wchar * 33),
        ('ersMaxJ', ctypes.c_float),
        ('isTimedRace', ctypes.c_int32),
        ('hasExtraLap', ctypes.c_int32),
        ('carSkin', ctypes.c_wchar * 33),
        ('reversedGridPositions', ctypes.c_int32),
        ('pitWindowStart', ctypes.c_int32),
        ('pitWindowEnd', ctypes.c_int32),
    ]

_shm = {'map': None, 'static': None}

def read_max_rpm(car_name, allow_mismatch=False):
    """Rev limiter for car_name, or 0 if the page does not describe that car yet.

    The page survives between sessions, so without the carModel check this can
    hand back the previous car's redline. allow_mismatch is for the case where
    the names never line up; by then the sim has certainly written this session.
    """
    try:
        if _shm['static'] is None:
            _shm['map'] = mmap.mmap(0, ctypes.sizeof(SPageFileStatic), "acpmf_static")
            _shm['static'] = SPageFileStatic.from_buffer(_shm['map'])
        st = _shm['static']
        rpm = int(st.maxRpm)
        if rpm <= 0:
            return 0
        model = str(st.carModel).strip().lower()
        if not allow_mismatch and car_name and model:
            if model != str(car_name).strip().lower():
                return 0
        return rpm
    except:
        return 0

VK_NEXT_GEAR = 0x50
VK_PREV_GEAR = 0x4F
VK_MODE_CYCLE = 0x4D

def load_key_bindings():
    """Take the shift keys from the player's own controls.ini instead of assuming O/P."""
    global VK_NEXT_GEAR, VK_PREV_GEAR, VK_MODE_CYCLE
    home = os.path.expanduser("~")
    for rel in (("Documents", "Assetto Corsa", "cfg", "controls.ini"),
                ("OneDrive", "Documents", "Assetto Corsa", "cfg", "controls.ini")):
        path = os.path.join(home, rel[0], rel[1], rel[2], rel[3])
        if not os.path.exists(path):
            continue
        try:
            section = ""
            f = open(path, "r")
            for line in f:
                line = line.split(";")[0].strip()
                if line.startswith("["):
                    section = line.strip("[]").strip().upper()
                elif line.upper().startswith("KEY=") and section in ("GEARUP", "GEARDN"):
                    try:
                        vk = int(line.split("=", 1)[1].strip(), 16)
                    except ValueError:
                        continue
                    if section == "GEARUP":
                        VK_NEXT_GEAR = vk
                    else:
                        VK_PREV_GEAR = vk
            f.close()
        except:
            pass
        break
    # Optional local override, for when the mode key collides with a game binding.
    try:
        cfg = os.path.join(os.path.dirname(__file__), "settings.json")
        if os.path.exists(cfg):
            f = open(cfg, "r")
            data = json.load(f)
            f.close()
            if "mode_key" in data:
                VK_MODE_CYCLE = int(data["mode_key"])
    except:
        pass

def press_key(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(hexKeyCode, 0, 0, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(hexKeyCode, 0, 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def game_has_focus():
    """Only react to the mode key while AC is the focused window."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == ctypes.windll.kernel32.GetCurrentProcessId()
    except:
        return True

MODE_COMFORT = 0
MODE_SPORT = 1
MODE_SPORTPLUS = 2
MODE_DRIFT = 3
MODE_MANUAL = 4

MODE_NAMES = ["COMFORT", "SPORT", "SPORT+", "DRIFT", "MANUAL"]

state = {
    'mode': MODE_MANUAL,
    'last_shift_time': 0,
    'clock': 0,
    'last_gear': 0,
    'appWindow': 0,
    'modeLabel': 0,
    'notifLabel': 0,
    'modeButton': 0,
    'mode_key_pressed': False,
    'redline_rpm': 0,
    'idle_rpm': 1000.0,
    'max_gear': 99,
    'pending_up': None,
    'up_fail': 0,
    'up_fail_gear': 0,
    'gear_ratios': {},
    'is_wheelspinning': False,
    'notification_timer': 0,
    'last_shift_dir': 0,
    'car_name': '',
    'drift_limiter_timer': 0
}

keys_to_release = []
scheduled_taps = []

def tap_key_async(hexKeyCode):
    press_key(hexKeyCode)
    keys_to_release.append({'key': hexKeyCode, 'timer': 0.05})

def schedule_tap(hexKeyCode, delay):
    scheduled_taps.append({'key': hexKeyCode, 'timer': delay})

def show_notification(text, duration=2.0):
    state['notification_timer'] = duration
    try:
        ac.setText(state['notifLabel'], text)
        ac.setFontColor(state['notifLabel'], 1.0, 1.0, 1.0, 0.9)
    except:
        pass

def request_upshift(gear):
    """Ask for an upshift and remember it, so a gearbox that refuses teaches us the top gear."""
    tap_key_async(VK_NEXT_GEAR)
    state['pending_up'] = {'gear': gear, 'deadline': state['clock'] + 0.45}
    state['last_shift_time'] = state['clock']
    state['last_shift_dir'] = 1

def autoShiftTarget(rpm, gas, brake, gear, speed_kmh, steer):
    now = state['clock']
    cooldown = 0.5
    if brake > 0.2:
        cooldown = 0.3
    elif state['mode'] == MODE_SPORTPLUS and gas > 0.9:
        cooldown = 0.2

    if now - state['last_shift_time'] < cooldown:
        return gear

    if state['mode'] == MODE_MANUAL:
        return gear

    is_cornering = (abs(steer) > 90) and (speed_kmh > 40)
    hold_gear = False

    # Rolling to a stop, an automatic walks back down to first no matter what
    # the rpm looks like. This cannot be defeated by a bad idle estimate.
    if speed_kmh < 5.0 and gear > 2:
        return gear - 1

    REDLINE_RPM = state['redline_rpm']
    IDLE_RPM = state['idle_rpm']
    upRpm = REDLINE_RPM
    downRpm = 1000

    if state['mode'] == MODE_COMFORT:
        upRpm = REDLINE_RPM * (0.22 + (gas**2) * 0.50)
        downRpm = REDLINE_RPM * (0.10 + (gas**3) * 0.35)

    elif state['mode'] == MODE_SPORT:
        upRpm = REDLINE_RPM * (0.65 + gas * 0.25)
        downRpm = REDLINE_RPM * (0.45 + gas * 0.20)
        if brake > 0.05:
            downRpm = max(downRpm, REDLINE_RPM * (0.50 + brake * 0.20))

    elif state['mode'] == MODE_SPORTPLUS:
        upRpm = REDLINE_RPM * (0.80 + gas * 0.15)
        downRpm = REDLINE_RPM * (0.45 + gas * 0.15)
        if brake > 0.05:
            downRpm = max(downRpm, REDLINE_RPM * (0.55 + brake * 0.15))

    elif state['mode'] == MODE_DRIFT:
        upRpm = REDLINE_RPM * 1.50
        downRpm = REDLINE_RPM * (0.50 + gas * 0.15)
        if brake > 0.05:
            downRpm = max(downRpm, REDLINE_RPM * (0.60 + brake * 0.15))

    if state['mode'] == MODE_SPORTPLUS and gas < 0.5:
        upRpm = REDLINE_RPM * 0.97
    elif state['mode'] == MODE_SPORT and gas < 0.2:
        upRpm = REDLINE_RPM * 0.95

    # An automatic has to be able to come back down to idle, otherwise it parks
    # itself in top gear and stays there: keep every downshift point above idle.
    downRpm = max(downRpm, IDLE_RPM * 1.15)

    # Clamp before the corner check, or the clamp would undo it.
    if state['mode'] != MODE_DRIFT:
        upRpm = min(upRpm, REDLINE_RPM * 0.98)

    if is_cornering and state['mode'] != MODE_COMFORT:
        hold_gear = True
        if brake < 0.2:
            downRpm = 0

    # Lifting off is not a reason to run up through the gearbox.
    if gas < 0.10 and rpm < (REDLINE_RPM * 0.45):
        hold_gear = True

    # Holding a gear is never worth bouncing off the limiter for.
    if rpm > (REDLINE_RPM * 0.985) and state['mode'] != MODE_DRIFT:
        hold_gear = False

    if gas >= 0.95 and not is_cornering:
        if (rpm * 1.55) < upRpm and rpm < (REDLINE_RPM * 0.70) and gear > 2:
            target_gear = gear - 1
            if target_gear == 2 and speed_kmh > 35:
                return gear
            return target_gear

    if rpm > upRpm and not hold_gear:
        if state['is_wheelspinning'] and state['mode'] != MODE_DRIFT:
            return gear
        if gear >= state['max_gear']:
            return gear
        return gear + 1

    elif rpm < downRpm and gear > 2:
        if state['mode'] == MODE_SPORTPLUS and brake > 0.7 and gear > 3 and rpm < (downRpm - 1000):
            target_gear = gear - 2
        else:
            target_gear = gear - 1

        if target_gear == 2 and speed_kmh > 20:
            return gear

        return target_gear

    return gear

def update_ui_colors():
    if state['redline_rpm'] <= 0:
        ac.setText(state['modeLabel'], "...")
        ac.setFontColor(state['modeLabel'], 1.0, 1.0, 0.0, 1.0)
        return

    mode = state['mode']
    ac.setText(state['modeLabel'], MODE_NAMES[mode])
    if mode == MODE_COMFORT:
        ac.setFontColor(state['modeLabel'], 0.2, 0.9, 0.4, 1.0)
    elif mode == MODE_SPORT:
        ac.setFontColor(state['modeLabel'], 1.0, 0.55, 0.0, 1.0)
    elif mode == MODE_SPORTPLUS:
        ac.setFontColor(state['modeLabel'], 1.0, 0.15, 0.15, 1.0)
    elif mode == MODE_DRIFT:
        ac.setFontColor(state['modeLabel'], 0.8, 0.3, 1.0, 1.0)
    elif mode == MODE_MANUAL:
        ac.setFontColor(state['modeLabel'], 0.6, 0.6, 0.6, 1.0)

def on_mode_click(*args):
    state['mode'] = (state['mode'] + 1) % len(MODE_NAMES)
    update_ui_colors()
    show_notification(MODE_NAMES[state['mode']], 1.5)

def acMain(ac_version):
    global state
    load_key_bindings()

    state['appWindow'] = ac.newApp("SmartShifter")
    ac.setSize(state['appWindow'], 300, 90)

    ac.setTitle(state['appWindow'], "")
    ac.setIconPosition(state['appWindow'], 0, -10000)

    ac.setBackgroundOpacity(state['appWindow'], 0)
    ac.drawBorder(state['appWindow'], 0)
    try:
        ac.drawBackground(state['appWindow'], 0)
    except:
        pass

    state['modeLabel'] = ac.addLabel(state['appWindow'], "")
    ac.setPosition(state['modeLabel'], 5, 5)
    ac.setFontSize(state['modeLabel'], 22)

    state['notifLabel'] = ac.addLabel(state['appWindow'], "")
    ac.setPosition(state['notifLabel'], 5, 32)
    ac.setFontSize(state['notifLabel'], 14)
    ac.setFontColor(state['notifLabel'], 1.0, 1.0, 1.0, 0.0)

    # Clicking the app cycles modes, so a keyboard binding is never required.
    try:
        state['modeButton'] = ac.addButton(state['appWindow'], "")
        ac.setPosition(state['modeButton'], 0, 0)
        ac.setSize(state['modeButton'], 300, 30)
        ac.addOnClickedListener(state['modeButton'], on_mode_click)
        ac.drawBorder(state['modeButton'], 0)
        ac.setBackgroundOpacity(state['modeButton'], 0)
    except:
        pass

    state['car_name'] = ac.getCarName(0)
    state['redline_rpm'] = read_max_rpm(state['car_name'])
    update_ui_colors()

    return "SmartShifter"

def acUpdate(deltaT):
    state['clock'] += deltaT

    ac.setBackgroundOpacity(state['appWindow'], 0)

    # The static page is not always populated by the time the app starts.
    if state['redline_rpm'] <= 0:
        rl = read_max_rpm(state['car_name'], state['clock'] > 5.0)
        if rl > 0:
            state['redline_rpm'] = rl
            update_ui_colors()
            show_notification(str(int(rl)) + " RPM", 2.0)

    global keys_to_release
    new_keys = []
    for k in keys_to_release:
        k['timer'] -= deltaT
        if k['timer'] <= 0:
            release_key(k['key'])
        else:
            new_keys.append(k)
    keys_to_release = new_keys

    global scheduled_taps
    new_scheduled = []
    for s in scheduled_taps:
        s['timer'] -= deltaT
        if s['timer'] <= 0:
            tap_key_async(s['key'])
        else:
            new_scheduled.append(s)
    scheduled_taps = new_scheduled

    if state['notification_timer'] > 0:
        state['notification_timer'] -= deltaT
        if state['notification_timer'] <= 0:
            try:
                ac.setText(state['notifLabel'], "")
            except:
                pass

    mode_key_down = False
    if game_has_focus():
        mode_key_state = ctypes.windll.user32.GetAsyncKeyState(VK_MODE_CYCLE)
        mode_key_down = (mode_key_state & 0x8000) != 0

    if mode_key_down and not state['mode_key_pressed']:
        on_mode_click()
    state['mode_key_pressed'] = mode_key_down

    rpm = ac.getCarState(0, acsys.CS.RPM)
    gas = ac.getCarState(0, acsys.CS.Gas)
    brake = ac.getCarState(0, acsys.CS.Brake)
    gear = ac.getCarState(0, acsys.CS.Gear)
    speed_kmh = ac.getCarState(0, acsys.CS.SpeedKMH)
    steer = ac.getCarState(0, acsys.CS.Steer)

    if state['redline_rpm'] <= 0:
        return

    if state['mode'] == MODE_DRIFT and rpm > (state['redline_rpm'] * 0.97):
        state['drift_limiter_timer'] += deltaT
    else:
        state['drift_limiter_timer'] = 0

    # Learn idle only in neutral, where the reading really is idle. Taking the
    # lowest rpm seen anywhere would latch onto a bogged engine and then sit
    # below true idle for the rest of the session.
    if gear == 1 and gas < 0.05 and 300 < rpm < (state['redline_rpm'] * 0.35):
        state['idle_rpm'] = rpm

    # An upshift that changed nothing means there was no gear left to take.
    pu = state['pending_up']
    if pu is not None and state['clock'] > pu['deadline']:
        if gear <= pu['gear']:
            # Only the same gear refusing twice counts, so one shift lost to a
            # clutch or a rev limiter does not convince us the gearbox is shorter
            # than it is.
            if state['up_fail_gear'] == pu['gear']:
                state['up_fail'] += 1
            else:
                state['up_fail_gear'] = pu['gear']
                state['up_fail'] = 1
            if state['up_fail'] >= 2:
                state['max_gear'] = pu['gear']
        else:
            state['up_fail'] = 0
            state['up_fail_gear'] = 0
        state['pending_up'] = None
    if gear > state['max_gear']:
        state['max_gear'] = gear

    if gear != state['last_gear']:
        state['last_gear'] = gear

    if gear >= 1 and speed_kmh > 15 and gas > 0.5 and brake < 0.1 and rpm > (state['redline_rpm'] * 0.4):
        if (state['clock'] - state['last_shift_time']) > 1.0:
            current_ratio = rpm / speed_kmh
            if gear not in state['gear_ratios']:
                state['gear_ratios'][gear] = current_ratio
            else:
                if current_ratio < state['gear_ratios'][gear]:
                    state['gear_ratios'][gear] = current_ratio

    state['is_wheelspinning'] = False
    if gear in state['gear_ratios'] and speed_kmh > 5:
        expected_rpm = state['gear_ratios'][gear] * speed_kmh
        if rpm > (expected_rpm * 1.25):
            state['is_wheelspinning'] = True

    # Anti-stall has to be judged against idle; a fixed slice of the redline
    # sits below idle on most cars and can never be reached.
    if rpm < (state['idle_rpm'] * 1.12) and gear > 2 and speed_kmh > 3:
        if (state['clock'] - state['last_shift_time']) > 0.3:
            tap_key_async(VK_PREV_GEAR)
            state['last_shift_time'] = state['clock']
            state['last_shift_dir'] = -1
            show_notification("ANTI-STALL", 1.0)
            return

    if state['mode'] != MODE_MANUAL:
        targetGear = autoShiftTarget(rpm, gas, brake, gear, speed_kmh, steer)

        # DRIFT deliberately sits on the limiter, so it needs its own way out.
        if state['mode'] == MODE_DRIFT and state['drift_limiter_timer'] > 5.0:
            if gear < state['max_gear']:
                targetGear = gear + 1
            state['drift_limiter_timer'] = 0

        if targetGear > gear:
            if state['last_shift_dir'] == -1 and (state['clock'] - state['last_shift_time']) < 1.5:
                pass
            else:
                request_upshift(gear)
        elif targetGear == gear - 1:
            if state['last_shift_dir'] == 1 and (state['clock'] - state['last_shift_time']) < 1.5:
                pass
            else:
                tap_key_async(VK_PREV_GEAR)
                state['last_shift_time'] = state['clock']
                state['last_shift_dir'] = -1
        elif targetGear <= gear - 2:
            tap_key_async(VK_PREV_GEAR)
            schedule_tap(VK_PREV_GEAR, 0.15)
            state['last_shift_time'] = state['clock']
            state['last_shift_dir'] = -1
