-- rampa_motores.lua
-- Rampa de velocidad para 2 motores DC via L298N (jumpers ENA/ENB puestos).
--   S7 -> IN1, S8 -> IN2 (motor izquierdo)
--   S9 -> IN3, S10 -> IN4 (motor derecho)
-- S7..S10 corren a Q_RC_SPEED = 490 Hz; el duty se fija con el ancho de pulso.
-- Disparo: poner SCR_USER1 = 1 (adelante) o -1 (atras). Vuelve solo a 0 al terminar.

local PWM_HZ    = 490
local PERIOD_US = 1000000 / PWM_HZ      -- ~2041 us
local MAX_DUTY  = 0.55                  -- ~6 V promedio con 3S (limite motores amarillos)
local RAMP_MS   = 10000                 -- 10 s de rampa
local CH_IN1, CH_IN2, CH_IN3, CH_IN4 = 6, 7, 8, 9   -- indices 0-based de S7..S10

local trig = Parameter("SCR_USER1")
local t0 = nil
local dir = 1
local last_report = -1
-- Picker app: RC15/16 signed wheel commands, RC7 alternating keepalive.
-- The bench uses RC_OVERRIDE_TIME=-1, so PWM presence alone is not freshness.
local last_token = nil
local last_edge = nil
local drive_ready = false
local last_advert = nil

local function out(ch, duty)
  SRV_Channels:set_output_pwm_chan_timeout(ch, math.floor(duty * PERIOD_US), 200)
end

local function motores(duty_izq, duty_der)
  -- duty con signo: + adelante, - atras. Nunca ambos IN en alto.
  if duty_izq >= 0 then out(CH_IN1, duty_izq); out(CH_IN2, 0)
  else out(CH_IN1, 0); out(CH_IN2, -duty_izq) end
  if duty_der >= 0 then out(CH_IN3, duty_der); out(CH_IN4, 0)
  else out(CH_IN3, 0); out(CH_IN4, -duty_der) end
end

local function app_drive(now)
  local token = rc:get_pwm(7)
  local left, right = rc:get_pwm(15), rc:get_pwm(16)
  if arming:is_armed() or (token ~= 1150 and token ~= 1850)
      or not left or not right or math.abs(left-1500)>450 or math.abs(right-1500)>450 then
    drive_ready, last_edge, last_token = false, nil, nil
    return false
  end
  if last_edge and (now-last_edge):tofloat() > 320 then drive_ready = false end
  if token ~= last_token then
    if last_token and left == 1500 and right == 1500 then drive_ready = true end
    last_token, last_edge = token, now
  end
  if drive_ready then motores((left-1500)/1000, (right-1500)/1000) end
  return drive_ready
end

function update()
  local now = millis()
  if not last_advert or (now-last_advert):tofloat() > 2000 then
    gcs:send_text(6, "PickerDrive v1 RC15/16 watchdog320")
    last_advert = now
  end
  if t0 == nil then
    local v = trig:get()
    if v == 0 and app_drive(now) then return update, 20 end
    motores(0, 0)
    if v == 1 or v == -1 then
      drive_ready, last_edge, last_token = false, nil, nil
      dir = v
      t0 = millis()
      last_report = -1
      gcs:send_text(6, string.format("Rampa: inicio (%s)", dir > 0 and "adelante" or "atras"))
    end
    return update, 20
  end

  local t = (millis() - t0):tofloat()
  if t >= RAMP_MS then
    motores(0, 0)
    trig:set_and_save(0)   -- guardar en flash: si no, al reiniciar vuelve a arrancar sola
    t0 = nil
    gcs:send_text(6, "Rampa: fin, motores detenidos")
    return update, 20
  end

  local duty = MAX_DUTY * t / RAMP_MS
  motores(dir * duty, dir * duty)

  local s = math.floor(t / 1000)
  if s ~= last_report then
    last_report = s
    gcs:send_text(6, string.format("Rampa t=%ds duty=%.0f%% pwm=%dus", s, duty * 100, math.floor(duty * PERIOD_US)))
  end
  return update, 20
end

-- Seguridad: nunca arrancar al encender aunque SCR_USER1 haya quedado guardado en 1
trig:set_and_save(0)
motores(0, 0)
gcs:send_text(6, "rampa_motores.lua cargado (SCR_USER1=1 para iniciar)")
return update, 1000
