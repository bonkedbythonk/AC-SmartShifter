"""Longitudinal car sim fed by real Assetto Corsa car data files."""
import os, math, json, re

def read_ini(path):
    out, sec = {}, None
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            line = line.split(';')[0].split('//')[0].strip()
            if not line: continue
            if line.startswith('['):
                sec = line.strip('[]').strip()
                out.setdefault(sec, {})
            elif '=' in line and sec is not None:
                k, v = line.split('=', 1)
                out[sec][k.strip().upper()] = v.strip()
    return out

def read_lut(path):
    pts = []
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            line = line.split(';')[0].strip()
            if '|' in line:
                a, b = line.split('|')[:2]
                try: pts.append((float(a), float(b)))
                except ValueError: pass
    pts.sort()
    return pts

def lut_at(pts, x):
    if not pts: return 0.0
    if x <= pts[0][0]: return pts[0][1]
    if x >= pts[-1][0]: return pts[-1][1]
    for i in range(1, len(pts)):
        if pts[i][0] >= x:
            x0, y0 = pts[i-1]; x1, y1 = pts[i]
            if x1 == x0: return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]

class Car(object):
    def __init__(self, car_dir):
        self.name = os.path.basename(os.path.normpath(car_dir))
        d = os.path.join(car_dir, 'data')
        dt = read_ini(os.path.join(d, 'drivetrain.ini'))
        en = read_ini(os.path.join(d, 'engine.ini'))
        ty = read_ini(os.path.join(d, 'tyres.ini'))
        ca = read_ini(os.path.join(d, 'car.ini'))

        g = dt['GEARS']
        self.n_gears = int(g['COUNT'])
        self.ratios = [float(g['GEAR_%d' % i]) for i in range(1, self.n_gears + 1)]
        self.final = float(g['FINAL'])
        ed = en['ENGINE_DATA']
        self.limiter = float(ed.get('LIMITER', 0)) or 8000.0
        self.idle = float(ed.get('MINIMUM', 1000))
        self.torque_lut = read_lut(os.path.join(d, 'power.lut'))
        # turbos stack multiplicatively on torque in AC
        boost = 0.0
        for k in en:
            if k.upper().startswith('TURBO_'):
                boost += float(en[k].get('MAX_BOOST', 0) or 0)
        self.boost = boost
        # tyre radius: first RADIUS entry
        self.radius = 0.32
        for sec in ty.values():
            if 'RADIUS' in sec:
                self.radius = float(sec['RADIUS']); break
        self.mass = float(ca['BASIC']['TOTALMASS']) + 75.0

        # advertised specs, used to sanity-scale torque and to solve drag
        self.bhp = None; self.topspeed = None
        uic = os.path.join(car_dir, 'ui', 'ui_car.json')
        if os.path.exists(uic):
            try:
                with open(uic, 'r', errors='ignore') as f:
                    spec = json.load(f).get('specs', {})
                m = re.search(r'([\d.]+)', str(spec.get('bhp', '')))
                if m: self.bhp = float(m.group(1))
                m = re.search(r'([\d.]+)', str(spec.get('topspeed', '')))
                if m: self.topspeed = float(m.group(1))
            except Exception: pass

        self.torque_scale = 1.0
        if self.bhp:
            peak_kw = max((self.crank_torque(r, scale=1.0) * r * 2 * math.pi / 60.0) / 1000.0
                          for r in range(int(self.idle), int(self.limiter), 50))
            target_kw = self.bhp * 0.7457
            if peak_kw > 1:
                self.torque_scale = target_kw / peak_kw
        # solve CdA so top gear tops out near the advertised top speed
        self.CdA = 0.70
        if self.topspeed:
            self.CdA = self._solve_CdA(self.topspeed)

    def crank_torque(self, rpm, scale=None):
        t = lut_at(self.torque_lut, rpm) * (1.0 + self.boost)
        return t * (self.torque_scale if scale is None else scale)

    def rpm_for(self, gear_idx, speed_ms):
        """gear_idx is 1-based forward gear."""
        r = self.ratios[gear_idx - 1] * self.final
        return max(self.idle, speed_ms / (2 * math.pi * self.radius) * r * 60.0)

    def drive_force(self, gear_idx, rpm, gas):
        if rpm >= self.limiter: return 0.0
        r = self.ratios[gear_idx - 1] * self.final
        return self.crank_torque(rpm) * gas * r * 0.90 / self.radius

    def resist(self, speed_ms):
        return 0.5 * 1.2 * self.CdA * speed_ms ** 2 + 0.015 * self.mass * 9.81

    def _solve_CdA(self, topspeed_kmh):
        v = topspeed_kmh / 3.6
        best, err = 0.70, 1e18
        g = self.n_gears
        for cda in [x / 100.0 for x in range(20, 200)]:
            rpm = self.rpm_for(g, v)
            if rpm > self.limiter: continue
            f = self.crank_torque(rpm) * 1.0 * self.ratios[g-1] * self.final * 0.90 / self.radius
            r = 0.5 * 1.2 * cda * v ** 2 + 0.015 * self.mass * 9.81
            e = abs(f - r)
            if e < err: err, best = e, cda
        return best
