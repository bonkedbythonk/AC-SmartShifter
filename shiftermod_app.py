import ac
import acsys
import ctypes
import math
import os
import json

SendInput = ctypes.windll.user32.SendInput
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

VK_NEXT_GEAR = 0x50
VK_PREV_GEAR = 0x4F
VK_MODE_CYCLE = 0x4D

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
    'mode_key_pressed': False,
    'redline_rpm': 3000,
    'redline_locked': False,
    'time_at_max_rpm': 0,
    'gear_ratios': {},
    'is_wheelspinning': False,
    'notification_timer': 0,
    'last_shift_dir': 0,
    'last_target': 0,
    'car_name': '',
    'drift_limiter_timer': 0,
    'mode_key_hold_time': 0.0
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

def get_config_path():
    return os.path.join(os.path.dirname(__file__), "calibrations.json")

def save_calibration():
    car = state['car_name']
    if not car: return
    path = get_config_path()
    data = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f: data = json.load(f)
        except: pass
    data[car] = state['redline_rpm']
    try:
        with open(path, 'w') as f: json.dump(data, f)
    except: pass

def load_calibration():
    car = state['car_name']
    if not car: return False
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if car in data:
                    state['redline_rpm'] = data[car]
                    state['redline_locked'] = True
                    return True
        except: pass
    return False

def delete_calibration():
    car = state['car_name']
    if not car: return
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f: data = json.load(f)
            if car in data:
                del data[car]
                with open(path, 'w') as f: json.dump(data, f)
        except: pass

def autoShiftTarget(rpm, gas, brake, gear, speed_kmh, steer):
    now = state['clock']
    cooldown = 0.5
    if brake > 0.2:
        cooldown = 0.3
    elif state['mode'] == MODE_SPORTPLUS and gas > 0.9:
        cooldown = 0.2
        
    if now - state['last_shift_time'] < cooldown:
        return gear
    
    if state['last_shift_dir'] != 0 and (now - state['last_shift_time']) < 1.5:
        pass

    if state['mode'] == MODE_MANUAL:
        return gear

    is_cornering = (abs(steer) > 90) and (speed_kmh > 40)

    REDLINE_RPM = state['redline_rpm']
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

    if is_cornering and state['mode'] != MODE_COMFORT:
        upRpm = 10000
        if brake < 0.2:
            downRpm = 0

    if state['mode'] != MODE_DRIFT:
        upRpm = min(upRpm, REDLINE_RPM * 0.98)

    if gas >= 0.95:
        if (rpm * 1.55) < upRpm and rpm < (REDLINE_RPM * 0.70) and gear > 2:
            target_gear = gear - 1
            if target_gear == 2 and speed_kmh > 35:
                return gear
            return target_gear

    if rpm > upRpm:
        if state['is_wheelspinning'] and state['mode'] != MODE_DRIFT:
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
    if not state['redline_locked']:
        ac.setText(state['modeLabel'], "CALIBRATE")
        ac.setFontColor(state['modeLabel'], 1.0, 1.0, 0.0, 1.0)
        try:
            ac.setText(state['notifLabel'], "Hold full throttle")
            ac.setFontColor(state['notifLabel'], 0.7, 0.7, 0.7, 0.8)
        except:
            pass
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
    state['appWindow'] = ac.newApp("Shifter Mod")
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
    
    state['car_name'] = ac.getCarName(0)
    load_calibration()
    update_ui_colors()
    
    return "Shifter Mod"

def acUpdate(deltaT):
    state['clock'] += deltaT
    
    ac.setBackgroundOpacity(state['appWindow'], 0)
    
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

    mode_key_state = ctypes.windll.user32.GetAsyncKeyState(VK_MODE_CYCLE)
    mode_key_down = (mode_key_state & 0x8000) != 0
    
    if mode_key_down:
        state['mode_key_hold_time'] += deltaT
        if state['mode_key_hold_time'] > 1.5 and state['redline_locked']:
            state['redline_locked'] = False
            state['redline_rpm'] = 3000
            state['gear_ratios'] = {}
            delete_calibration()
            update_ui_colors()
            show_notification("CALIBRATION WIPED", 3.0)
            state['mode_key_hold_time'] = -10.0
    else:
        state['mode_key_hold_time'] = 0.0

    if mode_key_down and not state['mode_key_pressed']:
        on_mode_click()
    state['mode_key_pressed'] = mode_key_down

    rpm = ac.getCarState(0, acsys.CS.RPM)
    gas = ac.getCarState(0, acsys.CS.Gas)
    brake = ac.getCarState(0, acsys.CS.Brake)
    gear = ac.getCarState(0, acsys.CS.Gear)
    speed_kmh = ac.getCarState(0, acsys.CS.SpeedKMH)
    steer = ac.getCarState(0, acsys.CS.Steer)

    if not state['redline_locked']:
        if gas > 0.8 and rpm > 2000:
            if rpm > state['redline_rpm']:
                state['redline_rpm'] = rpm
            state['time_at_max_rpm'] += deltaT
            if state['time_at_max_rpm'] > 1.5:
                state['redline_locked'] = True
                save_calibration()
                show_notification(str(int(state['redline_rpm'])) + " RPM", 3.0)
                update_ui_colors()
        else:
            state['time_at_max_rpm'] = 0

    if state['mode'] == MODE_DRIFT and rpm > (state['redline_rpm'] * 0.97):
        state['drift_limiter_timer'] += deltaT
    else:
        state['drift_limiter_timer'] = 0

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

    REDLINE_RPM = state['redline_rpm']
    if rpm < (REDLINE_RPM * 0.12) and gear > 2 and speed_kmh > 3:
        if (state['clock'] - state['last_shift_time']) > 0.3:
            tap_key_async(VK_PREV_GEAR)
            state['last_shift_time'] = state['clock']
            show_notification("ANTI-STALL", 1.0)
            return

    state['last_target'] = gear
    if state['mode'] != MODE_MANUAL:
        targetGear = autoShiftTarget(rpm, gas, brake, gear, speed_kmh, steer)
        
        if state['mode'] == MODE_DRIFT and state['drift_limiter_timer'] > 5.0:
            targetGear = gear + 1
            state['drift_limiter_timer'] = 0
            
        state['last_target'] = targetGear
        
        if targetGear > gear:
            if state['last_shift_dir'] == -1 and (state['clock'] - state['last_shift_time']) < 1.5:
                pass
            else:
                tap_key_async(VK_NEXT_GEAR)
                state['last_shift_time'] = state['clock']
                state['last_shift_dir'] = 1
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
