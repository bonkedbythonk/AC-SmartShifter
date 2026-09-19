"""Roll to a stop in top gear. The car must end up in 1st, including when the
engine bogs below idle while stopped, which once poisoned the idle estimate."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner, carsim, acstub

CAR = carsim.Car(os.path.join(runner.CARS, runner.TEST_CAR))


def roll_to_stop(app, bog_rpm=None, gear=None, start=150.0, seconds=25.0):
    sim = runner.Sim(CAR, gear or CAR.n_gears, start)
    del acstub.KEY_EVENTS[:]
    t, dt = 0.0, 1 / 60.0
    while t < seconds:
        if bog_rpm is not None and sim.v * 3.6 < 1.0:
            sim.rpm_override = bog_rpm
        te = acstub.TELEM
        braking = 1.0 if sim.v > 0.3 else 0.0
        te.rpm, te.gas, te.brake = sim.rpm, 0.0, braking
        te.gear, te.speed_kmh, te.steer = sim.gear + 1, sim.v * 3.6, 0.0
        app.acUpdate(dt)
        sim.apply_keys(t)
        sim.step(dt, 0.0, braking)
        t += dt
    return sim


ok = True
for label, bog in (('engine holds idle', None), ('engine bogs to 700 rpm', 700.0)):
    app = runner.load_app(CAR.name, 0, redline=CAR.limiter, idle=CAR.idle)
    first = roll_to_stop(app, bog_rpm=bog)
    second = roll_to_stop(app)
    good = first.gear == 1 and second.gear == 1
    ok = ok and good
    print('%s %-24s first stop gear %d, second stop gear %d, idle estimate %.0f'
          % ('ok  ' if good else 'FAIL', label, first.gear, second.gear, app.state['idle_rpm']))
sys.exit(0 if ok else 1)
