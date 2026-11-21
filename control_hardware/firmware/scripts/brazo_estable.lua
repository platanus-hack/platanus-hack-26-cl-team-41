-- brazo_estable.lua
-- Estabilizacion del brazo completo (brazo_compacto: 4 MG995 + 2 SG90) con la IMU de la H743.
-- La H743 va fija en la base del rover (no gira con la base del brazo).
--
-- Idea: la postura pedida (base, hombro, codo, muneca, giro) se interpreta en un marco NIVELADO
-- (gravedad hacia abajo, rumbo del rover). Cada 20 ms se calcula donde debe quedar la punta, el eje
-- de la pinza y la orientacion de las mandibulas en ese marco, se pasan al marco inclinado del rover
-- con el roll/pitch de la IMU y se resuelve la cinematica inversa. Prioridad: la punta queda quieta;
-- el eje de la pinza se mantiene todo lo que permiten 5 articulaciones (inclinacion hacia adelante/atras:
-- exacto; inclinacion lateral: la base gira para seguir la punta y la pinza se ladea un poco).
-- Solo rotaciones: la IMU no mide desplazamientos.
--
-- Salidas (SERVOx_FUNCTION):
--   94 Script1 base   95 Script2 hombro   96 Script3 codo   97 Script4 inclinacion muneca
--   98 Script5 giro muneca   99 Script6 pinza
-- Cableado actual: S2..S6 = base..giro muneca. La pinza (Script6) va en una salida a 50 Hz
-- (S1 o S11/S12), NO en S7..S10 que corren a 490 Hz para el L298N.
--
-- Postura pedida (grados, 0 = brazo recto hacia arriba, + = hacia adelante/abajo):
--   - si llegan RC overrides del puente (nexa_bridge): ch1..ch5 = 1500 + grados*DEG_SCALE, ch6 pinza 1000..2000
--   - si no: SCR_USER2..SCR_USER6 = base, hombro, codo, muneca, giro ; SCR_USER1 queda para rampa_motores.lua
-- Ajuste: STAB = 0 apaga la estabilizacion (constante abajo).

local DEG_SCALE = 5.0
-- Canales RC del brazo: 9..14 (base, hombro, codo, muneca, giro, pinza). No usar 1..4: sin receptor,
-- el failsafe de radio de ArduPlane los fuerza al centro aunque lleguen por MAVLink (RC override).
local RC_BASE = 9
local PERIOD_MS = 20

-- ===== SEGURIDAD (ajustar con cuidado) =====
-- Velocidad maxima de cada servo: nunca salta, ni al arrancar ni al compensar.
-- (Un giro brusco de la base hizo caer el Vx y se soltaron todos los servos.)
local MAX_RATE_DPS = 60
-- La estabilizacion entra de a poco durante este tiempo despues de arrancar.
local STAB_RAMP_MS = 3000
-- Cuanto puede alejarse la base de lo pedido para compensar (grados).
local BASE_COMP_MAX = 25
-- Hombro hacia atras con el codo doblado (>= 45): el codo queda a ~70 mm de la varilla (que esta a 93 mm).
local SHOULDER_BACK_BENT = -30

-- ===== ESTABILIZACION (activar por partes, despues de calibrar dir/offset) =====
-- Se ajustan en vivo con parametros (se crean al cargar el script; valores por defecto = apagado):
--   BRZ_STAB  ganancia roll/pitch (0 = apagada, 1 = completa). Subir de a poco.
--   BRZ_ROLLB 1 = con el brazo recto compensar el roll girando la base (hasta BASE_COMP_MAX). Dejar en 0.
--   BRZ_YAW   1 = si el rover gira, la base gira al reves (rumbo fijo). Sin brujula deriva. Misiones con camara: 0.
local PARAM_KEY = 73
assert(param:add_table(PARAM_KEY, "BRZ_", 3), "no se pudo crear la tabla BRZ_")
param:add_param(PARAM_KEY, 1, "STAB", 0)
param:add_param(PARAM_KEY, 2, "ROLLB", 0)
param:add_param(PARAM_KEY, 3, "YAW", 0)
local P_STAB, P_ROLLB, P_YAW = Parameter("BRZ_STAB"), Parameter("BRZ_ROLLB"), Parameter("BRZ_YAW")
local STAB, ROLL_BASE, YAW_HOLD = 0, 0, 0

-- geometria del CAD (mm): eje base -> hombro, eslabones, muneca -> punta de los dedos
local HS, L1, L2, G = 46.0, 90.0, 85.0, 144.0

-- calibracion de servos: pulso = 1500 + dir*(grados + offset)*us_per_deg   (MEDIR offset/dir en el banco)
-- lo, hi = limites en grados (SPECS.md, calculados en el CAD con la base mirando adelante)
local JOINT = {
  { name = "base",    dir = 1, offset = 0, us_per_deg = 11.1, lo = -90,   hi = 90 },
  { name = "hombro",  dir = 1, offset = 0, us_per_deg = 11.1, lo = -13,   hi = 90 },
  { name = "codo",    dir = -1, offset = 0, us_per_deg = 11.1, lo = -20,   hi = 95 },
  { name = "muneca",  dir = -1, offset = 0, us_per_deg = 11.1, lo = -45,   hi = 90 },
  { name = "giro",    dir = -1, offset = 0, us_per_deg = 10.6, lo = -90,   hi = 90 },
}
local MIN_US, MAX_US = 500, 2500
local GRIP_CLOSED_US, GRIP_OPEN_US = 1050, 1750

local rad, deg, sin, cos, atan, sqrt, abs = math.rad, math.deg, math.sin, math.cos, math.atan, math.sqrt, math.abs
local function atan2(y, x) return atan(y, x) end
local function clamp(v, lo, hi) if v < lo then return lo elseif v > hi then return hi end return v end
local function wrap(a) return (a + 180) % 360 - 180 end
local function cross(a, b) return { a[2]*b[3]-a[3]*b[2], a[3]*b[1]-a[1]*b[3], a[1]*b[2]-a[2]*b[1] } end
local function dot(a, b) return a[1]*b[1] + a[2]*b[2] + a[3]*b[3] end

local chan = {}
for i = 1, 6 do chan[i] = SRV_Channels:find_channel(93 + i) end
local user = {}
for i = 2, 6 do user[i] = Parameter("SCR_USER" .. i) end

-- cinematica directa en el marco de la base del brazo (x adelante, y izquierda, z arriba; origen en el eje de la base)
local function fk(q)
  local c, s = cos(rad(q[1])), sin(rad(q[1]))
  local a2, a23, phi = rad(q[2]), rad(q[2] + q[3]), rad(q[2] + q[3] + q[4])
  local r = L1*sin(a2) + L2*sin(a23) + G*sin(phi)
  local z = HS + L1*cos(a2) + L2*cos(a23) + G*cos(phi)
  local p = { r*c, r*s, z }
  local a = { sin(phi)*c, sin(phi)*s, cos(phi) }
  local j0 = { cos(phi)*c, cos(phi)*s, -sin(phi) }
  local n = cross(a, j0)
  local cr, sr = cos(rad(q[5])), sin(rad(q[5]))
  local j = { j0[1]*cr + n[1]*sr, j0[2]*cr + n[2]*sr, j0[3]*cr + n[3]*sr }
  return p, a, j
end

-- marco nivelado -> marco del rover (roll/pitch de ArduPilot, en el marco x adelante, y izquierda, z arriba)
local function to_body(v, roll, pitch)
  local cp, sp = cos(pitch), sin(pitch)
  local x, y, z = v[1]*cp + v[3]*sp, v[2], -v[1]*sp + v[3]*cp
  local cr, sr = cos(roll), sin(roll)
  return { x, y*cr + z*sr, -y*sr + z*cr }
end

-- cinematica inversa: punta p exacta, eje de pinza a proyectado al plano del brazo, mandibulas j
local function ik(p, a, j, qc)
  local rh = sqrt(p[1]*p[1] + p[2]*p[2])
  local d = wrap(deg(atan2(p[2], p[1])) - qc[1])
  if abs(d) > 90 then d = wrap(d - 180) end
  local k = clamp((rh - 20) / 40, 0, 1)          -- cerca del eje vertical la base no gira
  local psi = qc[1] + k*d
  local c, s = cos(rad(psi)), sin(rad(psi))
  local r = p[1]*c + p[2]*s
  local phi = atan2(a[1]*c + a[2]*s, a[3])
  local wr, wz = r - G*sin(phi), p[3] - G*cos(phi) - HS
  local dd = clamp(sqrt(wr*wr + wz*wz), abs(L1 - L2) + 0.01, L1 + L2 - 0.01)
  local e = math.acos(clamp((dd*dd - L1*L1 - L2*L2) / (2*L1*L2), -1, 1))
  if qc[3] < 0 then e = -e end
  local sh = atan2(wr, wz) - atan2(L2*sin(e), L1 + L2*cos(e))
  local w = phi - sh - e
  local a2 = { sin(phi)*c, sin(phi)*s, cos(phi) }
  local j0 = { cos(phi)*c, cos(phi)*s, -sin(phi) }
  local n = cross(a2, j0)
  local rho = deg(atan2(dot(j, n), dot(j, j0)))
  return { psi, deg(sh), deg(e), wrap(deg(w)), qc[5] + wrap(rho - qc[5]) }
end

local hold = { 0, 0, 0, 0, 0 }
local grip = 0.4
local got_rc = false
local stab_on = false
local yaw_ref = nil
local lean_back = false
local last_report = 0
local t_start = nil
local cur = { 0, 0, 0, 0, 0 }   -- angulo que se esta enviando (arranca en el centro, 1500 us)

local function out(i, us)
  if chan[i] then SRV_Channels:set_output_pwm_chan_timeout(chan[i], math.floor(us + 0.5), 200) end
end

function update()
  -- 1) postura pedida
  -- sin receptor, ArduPilot igual reporta valores en algunos canales (ch1=1516, ch3=0...):
  -- solo se acepta como orden del puente si los 6 canales traen un pulso valido
  local valid = true
  for i = 1, 6 do
    local v = rc:get_pwm(RC_BASE + i - 1)
    if not v or v < 900 or v > 2100 then valid = false end
  end
  if valid then
    for i = 1, 5 do hold[i] = (rc:get_pwm(RC_BASE + i - 1) - 1500) / DEG_SCALE end
    grip = clamp((rc:get_pwm(RC_BASE + 5) - 1000) / 1000, 0, 1)
    got_rc = true
  elseif not got_rc then
    for i = 1, 5 do hold[i] = user[i + 1]:get() end
  end
  -- si el puente deja de enviar, el brazo mantiene la ultima postura recibida
  for i = 1, 5 do
    local lo = JOINT[i].lo
    if i == 2 and hold[3] >= 45 then lo = SHOULDER_BACK_BENT end
    hold[i] = clamp(hold[i], lo, JOINT[i].hi)
  end
  -- con el codo doblado >= 45 grados hacia adelante el codo queda lejos de la varilla de la camara:
  -- el hombro puede ir hasta SHOULDER_BACK_BENT hacia atras (con el brazo recto solo -13, la pinza toca la varilla)
  if hold[3] >= 45 then hold[2] = math.max(hold[2], SHOULDER_BACK_BENT) end

  -- 2) estabilizacion
  STAB = clamp(P_STAB:get(), 0, 1)
  ROLL_BASE = P_ROLLB:get()
  YAW_HOLD = clamp(P_YAW:get(), 0, 1)
  local now = millis():toint()
  if t_start == nil then
    t_start = now
    -- al (re)cargar el script se supone que el brazo ya esta en la postura pedida: no saltar al centro
    for i = 1, 5 do cur[i] = hold[i] end
  end
  local q = { hold[1], hold[2], hold[3], hold[4], hold[5] }
  local h = { hold[1], hold[2], hold[3], hold[4], hold[5] }
  -- ahrs:healthy() da falso sin GPS en ArduPlane; la actitud igual es valida (es la que usaba el Mount)
  stab_on = STAB ~= 0 and ahrs:get_roll() ~= nil
  if stab_on then
    local gain = STAB * clamp((now - t_start) / STAB_RAMP_MS, 0, 1)
    local roll, pitch = gain * ahrs:get_roll(), gain * ahrs:get_pitch()
    -- yaw: el brazo mantiene su rumbo en el mundo (la base gira al reves que el rover)
    if YAW_HOLD ~= 0 then
      local yaw = ahrs:get_yaw()
      if yaw_ref == nil then yaw_ref = yaw end
      h[1] = hold[1] + YAW_HOLD * wrap(deg(yaw - yaw_ref))
    end
    if abs(h[3]) < 8 and ROLL_BASE == 0 then
      -- brazo casi recto: solo el hombro compensa la inclinacion en el plano del brazo (sin mover la base)
      local psi = rad(h[1])
      q = { h[1], h[2] + deg(pitch*cos(psi) + roll*sin(psi)), h[3], h[4], h[5] }
    elseif abs(h[3]) < 8 then
      -- brazo casi recto: la base orienta el plano del brazo hacia donde se inclina el rover y el hombro
      -- lo endereza; el giro de muneca deshace el giro de la base para que las mandibulas no roten
      local u = to_body({ 0, 0, 1 }, roll, pitch)          -- "arriba" del mundo visto desde el rover
      local m = deg(math.asin(clamp(sqrt(u[1]*u[1] + u[2]*u[2]), 0, 1)))
      -- preferir inclinar el hombro hacia adelante (hasta 90) con la base en +-90; hacia atras solo llega a -13,
      -- se usa cuando el rover cae de nariz. Histeresis para que la base no salte 180 grados con ruido.
      local az = deg(atan2(u[2], u[1]))
      if lean_back then
        if abs(az) < 80 then lean_back = false end
      elseif abs(az) > 100 then
        lean_back = true
      end
      local target = lean_back and wrap(az - 180) or clamp(az, -90, 90)
      local d = wrap(target - h[1])
      local wgt = clamp((m - 2) / 4, 0, 1)                -- con poca inclinacion la base no se mueve
      local psi = h[1] + clamp(wgt * d, -BASE_COMP_MAX, BASE_COMP_MAX)
      local lean = deg(math.asin(clamp(u[1]*cos(rad(psi)) + u[2]*sin(rad(psi)), -1, 1)))
      q = { psi, h[2] + lean, h[3], h[4], h[5] - (psi - h[1]) }
    else
      local p, a, j = fk(h)
      q = ik(to_body(p, roll, pitch), to_body(a, roll, pitch), to_body(j, roll, pitch), h)
    end
    q[1] = clamp(q[1], h[1] - BASE_COMP_MAX, h[1] + BASE_COMP_MAX)
  end

  -- limite de velocidad: cada servo avanza como maximo MAX_RATE_DPS
  local step = MAX_RATE_DPS * PERIOD_MS / 1000
  for i = 1, 5 do
    local lo = JOINT[i].lo
    if i == 2 and hold[3] >= 45 then lo = SHOULDER_BACK_BENT end
    cur[i] = cur[i] + clamp(clamp(q[i], lo, JOINT[i].hi) - cur[i], -step, step)
    q[i] = cur[i]
  end

  -- 3) salidas
  for i = 1, 5 do
    local J = JOINT[i]
    local qi = q[i]   -- ya limitado arriba
    out(i, clamp(1500 + J.dir * (qi + J.offset) * J.us_per_deg, MIN_US, MAX_US))
    q[i] = qi
  end
  out(6, GRIP_CLOSED_US + (GRIP_OPEN_US - GRIP_CLOSED_US) * grip)

  if now - last_report > 2000 then
    last_report = now
    gcs:send_text(6, string.format("Brazo b%.1f h%.1f c%.1f m%.1f g%.1f %s%s", q[1], q[2], q[3], q[4], q[5],
      stab_on and "estab" or "SIN-estab", got_rc and " puente" or ""))
  end
  return update, PERIOD_MS
end

gcs:send_text(6, "brazo_estable.lua cargado")
return update, 1000
