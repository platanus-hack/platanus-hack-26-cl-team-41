-- nexa.lua: arm + drive for the Nexa robot on a Matek H743 (ArduPilot 4.5.x), 50 Hz.
--
-- The Radxa (nexa_bridge) sends RC overrides over MAVLink:
--   ch1..ch5  joint angle    = 1500 + deg * DEG_SCALE   (base, shoulder, elbow, wrist pitch, wrist roll)
--   ch6       gripper        = 1000 (closed) .. 2000 (open)
--   ch7, ch8  wheel duty     = 1500 + 500 * duty, duty in -1..1 (left, right)
-- This script adds the IMU tilt compensation, applies the servo calibration below and writes:
--   servos  -> outputs with SERVOx_FUNCTION = 94..99 (Script1..Script6)
--   L298N   -> IN1, IN2, IN3, IN4 on outputs with SERVOx_FUNCTION = 100..103 (Script7..Script10),
--              PWM on one input and 0 on the other, only while armed.
--   second shoulder MG995 (side B, outboard of the upper arm) -> SERVOx_FUNCTION = 104 (Script11).
--              Same shoulder angle with its own calibration, so the two servos can be trimmed not to fight.
-- No override (link lost, RC_OVERRIDE_TIME expired): wheels stop, the arm holds its last pose.

local DEG_SCALE = 5.0      -- must match [mavlink] deg_scale in robot_bridge/config.toml
local MAX_DUTY = 0.55      -- 0.55 of a 3S pack is ~6 V average on the TT motors
local PWM_PERIOD_US = 2040 -- 490 Hz on the motor timer group
local STAB_GAIN = 1.0      -- 0 disables the tilt compensation
-- signs of the compensation: check on the bench (tilt the base nose-up: the arm must stay vertical;
-- roll it: the gripper must stay level) and flip a sign here if it moves the wrong way
local SIGN_SHOULDER = 1
local SIGN_WRIST_ROLL = 1

-- servo calibration: pulse = 1500 + dir * (deg + offset) * us_per_deg, clamped to [min_us, max_us]
local JOINT = {
  { name = "base",        dir = 1, offset = 0, us_per_deg = 11.1, min_us = 500, max_us = 2500 },
  { name = "shoulder",    dir = 1, offset = 0, us_per_deg = 11.1, min_us = 500, max_us = 2500 },
  { name = "elbow",       dir = 1, offset = 0, us_per_deg = 11.1, min_us = 500, max_us = 2500 },
  { name = "wrist pitch", dir = 1, offset = 0, us_per_deg = 11.1, min_us = 500, max_us = 2500 },
  { name = "wrist roll",  dir = 1, offset = 0, us_per_deg = 10.6, min_us = 500, max_us = 2400 },
}
-- second shoulder servo: its shaft points the same way as the first one (+Y), so dir = 1. Trim offset
-- (degrees) until both servos are quiet (no buzzing, low current) holding the arm still.
local SHOULDER_B = { dir = 1, offset = 0, us_per_deg = 11.1, min_us = 500, max_us = 2500 }
local GRIPPER_CLOSED_US = 1050
local GRIPPER_OPEN_US = 1750

local SCRIPT_FN = 94 -- Script1; Script1..6 servos, Script7..10 IN1..IN4, Script11 shoulder B
local TIMEOUT_MS = 100

local chan = {}
for i = 1, 11 do
  chan[i] = SRV_Channels:find_channel(SCRIPT_FN + i - 1)
end

local hold = { 0, 0, 0, 0, 0 }
local hold_grip = 0.4

local function clamp(v, lo, hi)
  if v < lo then return lo end
  if v > hi then return hi end
  return v
end

local function out(i, us)
  if chan[i] then
    SRV_Channels:set_output_pwm_chan_timeout(chan[i], math.floor(us + 0.5), TIMEOUT_MS)
  end
end

local function motor(in_a, in_b, duty)
  duty = clamp(duty, -1, 1) * MAX_DUTY
  if math.abs(duty) < 0.02 then
    out(in_a, 0)
    out(in_b, 0)
  elseif duty > 0 then
    out(in_a, duty * PWM_PERIOD_US)
    out(in_b, 0)
  else
    out(in_a, 0)
    out(in_b, -duty * PWM_PERIOD_US)
  end
end

local function update()
  local have = rc:get_pwm(1) ~= nil and rc:get_pwm(1) >= 900
  local deg = {}
  local grip
  if have then
    for i = 1, 5 do
      hold[i] = (rc:get_pwm(i) - 1500) / DEG_SCALE
    end
    hold_grip = clamp((rc:get_pwm(6) - 1000) / 1000, 0, 1)
  end
  for i = 1, 5 do deg[i] = hold[i] end
  grip = hold_grip

  -- tilt compensation: split the base roll/pitch into the arm's plane (shoulder) and across it (wrist roll)
  if STAB_GAIN ~= 0 then
    local roll = ahrs:get_roll() or 0
    local pitch = ahrs:get_pitch() or 0
    local psi = math.rad(deg[1])
    local in_plane = pitch * math.cos(psi) + roll * math.sin(psi)
    local across = pitch * math.sin(psi) - roll * math.cos(psi)
    deg[2] = deg[2] + SIGN_SHOULDER * STAB_GAIN * math.deg(in_plane)
    deg[5] = deg[5] + SIGN_WRIST_ROLL * STAB_GAIN * math.deg(across)
  end

  for i = 1, 5 do
    local j = JOINT[i]
    out(i, clamp(1500 + j.dir * (deg[i] + j.offset) * j.us_per_deg, j.min_us, j.max_us))
  end
  local b = SHOULDER_B
  out(11, clamp(1500 + b.dir * (deg[2] + b.offset) * b.us_per_deg, b.min_us, b.max_us))
  out(6, GRIPPER_CLOSED_US + (GRIPPER_OPEN_US - GRIPPER_CLOSED_US) * grip)

  -- wheels: only while armed and while the bridge keeps sending
  local left, right = 0, 0
  if have and arming:is_armed() then
    left = (rc:get_pwm(7) - 1500) / 500
    right = (rc:get_pwm(8) - 1500) / 500
  end
  motor(7, 8, left)   -- IN1, IN2
  motor(9, 10, right) -- IN3, IN4

  return update, 20
end

gcs:send_text(6, "nexa.lua running")
return update()
