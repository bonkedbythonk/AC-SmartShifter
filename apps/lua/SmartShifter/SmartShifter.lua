-- SmartShifter (CSP Lua build)
--
-- Reads what the earlier Python build had to guess: the rev limiter, idle,
-- gear count and per-wheel slip come straight from CSP, and shifts go through
-- ac.overrideCarControls() instead of synthetic keypresses. The shift logic
-- itself is carried over from the Python version.
--
-- Gear convention here is CSP's: -1 reverse, 0 neutral, 1..gearCount.

local MODE_COMFORT, MODE_SPORT, MODE_SPORTPLUS, MODE_DRIFT, MODE_MANUAL = 0, 1, 2, 3, 4
local MODE_NAMES = { 'COMFORT', 'SPORT', 'SPORT+', 'DRIFT', 'MANUAL' }
local MODE_COLORS = {
  rgbm(0.2, 0.9, 0.4, 1.0),
  rgbm(1.0, 0.55, 0.0, 1.0),
  rgbm(1.0, 0.15, 0.15, 1.0),
  rgbm(0.8, 0.3, 1.0, 1.0),
  rgbm(0.6, 0.6, 0.6, 1.0),
}

-- Mode survives between sessions.
local stored = ac.storage({ mode = MODE_MANUAL })

-- Bindable in Content Manager under Controls > Patch. Defaults to M.
local modeButton = ac.ControlButton('SmartShifter/Cycle Mode', {
  keyboard = { key = ui.KeyIndex.M },
})

local state = {
  mode = stored.mode,
  clock = 0,
  lastShiftTime = -10,
  lastShiftDir = 0,
  driftLimiterTimer = 0,
  learnedRedline = 0,
  notification = '',
  notificationTimer = 0,
  pendingDown = 0,        -- extra downshifts still to send (for a two-gear drop)
  pendingDownTimer = 0,
}

local controls = nil

local function getControls()
  if controls == nil then
    controls = ac.overrideCarControls(0)
    if controls ~= nil then
      -- Neutral values, so that taking the override changes nothing but gears.
      controls.steer = math.huge
      controls.gas = 0
      controls.brake = 0
      controls.handbrake = 0
      controls.clutch = 1
      controls.requestedGearIndex = 0
      controls.gearUp = false
      controls.gearDown = false
    end
  end
  return controls
end

local function notify(text, duration)
  state.notification = text
  state.notificationTimer = duration or 2.0
end

local function setMode(mode)
  state.mode = mode
  stored.mode = mode
  notify(MODE_NAMES[mode + 1], 1.5)
end

local function cycleMode()
  setMode((state.mode + 1) % #MODE_NAMES)
end

local function shiftUp()
  local c = getControls()
  if c == nil then return end
  c.gearUp = true
  state.lastShiftTime = state.clock
  state.lastShiftDir = 1
end

local function shiftDown()
  local c = getControls()
  if c == nil then return end
  c.gearDown = true
  state.lastShiftTime = state.clock
  state.lastShiftDir = -1
end

-- The car's redline. CSP reports the limiter directly; the fallback learns it
-- from the limiter actually cutting in, for the odd car that reports none.
local function redlineFor(car)
  if car.rpmLimiter and car.rpmLimiter > 0 then
    return car.rpmLimiter
  end
  if car.isEngineLimiterOn and car.rpm > state.learnedRedline then
    state.learnedRedline = car.rpm
  end
  return state.learnedRedline
end

local function idleFor(car)
  if car.rpmMinimum and car.rpmMinimum > 0 then
    return car.rpmMinimum
  end
  return 1000
end

-- Any wheel running ahead of the road under power counts as spinning up.
local function isWheelspinning(car)
  if car.gas < 0.3 then return false end
  local worst = 0
  for i = 0, 3 do
    local w = car.wheels[i]
    if w and w.slipRatio > worst then worst = w.slipRatio end
  end
  return worst > 0.20
end

local function autoShiftTarget(car, redline, idle, spinning)
  local now = state.clock
  local rpm, gas, brake, gear = car.rpm, car.gas, car.brake, car.gear
  local speed, steer = car.speedKmh, car.steer
  local mode = state.mode

  local cooldown = 0.5
  if brake > 0.2 then
    cooldown = 0.3
  elseif mode == MODE_SPORTPLUS and gas > 0.9 then
    cooldown = 0.2
  end
  if now - state.lastShiftTime < cooldown then return gear end
  if mode == MODE_MANUAL then return gear end

  local isCornering = math.abs(steer) > 90 and speed > 40
  local holdGear = false

  -- Rolling to a stop, an automatic walks back down to first regardless of rpm.
  if speed < 5.0 and gear > 1 then return gear - 1 end

  local upRpm, downRpm = redline, 1000

  if mode == MODE_COMFORT then
    upRpm = redline * (0.22 + (gas ^ 2) * 0.50)
    downRpm = redline * (0.10 + (gas ^ 3) * 0.35)
  elseif mode == MODE_SPORT then
    upRpm = redline * (0.65 + gas * 0.25)
    downRpm = redline * (0.45 + gas * 0.20)
    if brake > 0.05 then downRpm = math.max(downRpm, redline * (0.50 + brake * 0.20)) end
  elseif mode == MODE_SPORTPLUS then
    upRpm = redline * (0.80 + gas * 0.15)
    downRpm = redline * (0.45 + gas * 0.15)
    if brake > 0.05 then downRpm = math.max(downRpm, redline * (0.55 + brake * 0.15)) end
  elseif mode == MODE_DRIFT then
    upRpm = redline * 1.50
    downRpm = redline * (0.50 + gas * 0.15)
    if brake > 0.05 then downRpm = math.max(downRpm, redline * (0.60 + brake * 0.15)) end
  end

  if mode == MODE_SPORTPLUS and gas < 0.5 then
    upRpm = redline * 0.97
  elseif mode == MODE_SPORT and gas < 0.2 then
    upRpm = redline * 0.95
  end

  -- Downshift points stay above idle, or the box parks itself in top gear.
  downRpm = math.max(downRpm, idle * 1.15)

  -- Clamp before the corner check, or the clamp would undo it.
  if mode ~= MODE_DRIFT then upRpm = math.min(upRpm, redline * 0.98) end

  if isCornering and mode ~= MODE_COMFORT then
    holdGear = true
    if brake < 0.2 then downRpm = 0 end
  end

  -- Lifting off is not a reason to run up through the gearbox.
  if gas < 0.10 and rpm < redline * 0.45 then holdGear = true end

  -- Holding a gear is never worth bouncing off the limiter for.
  if rpm > redline * 0.985 and mode ~= MODE_DRIFT then holdGear = false end

  -- Kickdown on a floored pedal.
  if gas >= 0.95 and not isCornering then
    if rpm * 1.55 < upRpm and rpm < redline * 0.70 and gear > 1 then
      local target = gear - 1
      if target == 1 and speed > 35 then return gear end
      return target
    end
  end

  if rpm > upRpm and not holdGear then
    if spinning and mode ~= MODE_DRIFT then return gear end
    if gear >= car.gearCount then return gear end
    return gear + 1
  elseif rpm < downRpm and gear > 1 then
    local target
    if mode == MODE_SPORTPLUS and brake > 0.7 and gear > 2 and rpm < downRpm - 1000 then
      target = gear - 2
    else
      target = gear - 1
    end
    if target == 1 and speed > 20 then return gear end
    return target
  end

  return gear
end

function script.update(dt)
  state.clock = state.clock + dt

  if state.notificationTimer > 0 then
    state.notificationTimer = state.notificationTimer - dt
    if state.notificationTimer <= 0 then state.notification = '' end
  end

  if modeButton:pressed() then cycleMode() end

  -- Flags are one-shot for the next physics step; clear them so a stale
  -- request can never repeat.
  local c = controls
  if c ~= nil then
    c.gearUp = false
    c.gearDown = false
  end

  local sim = ac.getSim()
  if sim.isPaused or sim.isReplayActive or sim.isInMainMenu then return end

  local car = ac.getCar(0)
  if car == nil or not car.physicsAvailable or car.isRemote or car.isAIControlled then return end

  local redline = redlineFor(car)
  if redline <= 0 then return end
  local idle = idleFor(car)
  local gear = car.gear

  -- Second half of a two-gear drop.
  if state.pendingDown > 0 then
    state.pendingDownTimer = state.pendingDownTimer - dt
    if state.pendingDownTimer <= 0 then
      state.pendingDown = state.pendingDown - 1
      shiftDown()
      state.pendingDownTimer = 0.15
    end
  end

  if state.mode == MODE_DRIFT and car.rpm > redline * 0.97 then
    state.driftLimiterTimer = state.driftLimiterTimer + dt
  else
    state.driftLimiterTimer = 0
  end

  local spinning = isWheelspinning(car)

  -- Anti-stall, judged against real idle.
  if car.rpm < idle * 1.12 and gear > 1 and car.speedKmh > 3 then
    if state.clock - state.lastShiftTime > 0.3 then
      shiftDown()
      notify('ANTI-STALL', 1.0)
      return
    end
  end

  if state.mode == MODE_MANUAL then return end

  local target = autoShiftTarget(car, redline, idle, spinning)

  -- DRIFT deliberately sits on the limiter, so it needs its own way out.
  if state.mode == MODE_DRIFT and state.driftLimiterTimer > 5.0 then
    if gear < car.gearCount then target = gear + 1 end
    state.driftLimiterTimer = 0
  end

  if target > gear then
    if not (state.lastShiftDir == -1 and state.clock - state.lastShiftTime < 1.5) then
      shiftUp()
    end
  elseif target == gear - 1 then
    if not (state.lastShiftDir == 1 and state.clock - state.lastShiftTime < 1.5) then
      shiftDown()
    end
  elseif target <= gear - 2 then
    shiftDown()
    state.pendingDown = 1
    state.pendingDownTimer = 0.15
  end
end

function script.windowMain(dt)
  local car = ac.getCar(0)
  local label = MODE_NAMES[state.mode + 1]
  local color = MODE_COLORS[state.mode + 1]
  if car == nil or not car.physicsAvailable then
    label, color = '...', rgbm(1, 1, 0, 1)
  end

  -- Clicking the app cycles modes, so no key binding is ever required.
  ui.setCursor(vec2(0, 0))
  if ui.invisibleButton('smartshifter_cycle', vec2(300, 30)) then cycleMode() end

  ui.setCursor(vec2(5, 5))
  ui.dwriteText(label, 22, color)

  if state.notification ~= '' then
    ui.setCursor(vec2(5, 32))
    ui.dwriteText(state.notification, 14, rgbm(1, 1, 1, 0.9))
  end
end
