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
--   98 Script5 giro muneca   99 Script6 pinza   100 Script7 hombro auxiliar   101 Script8 codo auxiliar
-- Cableado actual: S2..S6 = base..giro muneca, S11 pinza, S1 hombro auxiliar, S12 codo auxiliar.
-- Los servos van en salidas a 50 Hz (S1..S6, S11, S12), NO en S7..S10 que corren a 490 Hz para el L298N.
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

-- ===== SERVO DOBLE (Script7 = SERVOx_FUNCTION 100, en S1) =====
-- Un segundo servo en el mismo eje que una articulacion: sigue exactamente su angulo (mismo limite de
-- velocidad y recorrido); nunca es una articulacion aparte.
--   BRH_JNT   articulacion que acompana: 1 base, 2 hombro (por defecto), 3 codo, 4 muneca
--   BRH_DIR   0 = sin pulso (servo suelto, por defecto), 1 = mismo sentido, -1 = en espejo
--   BRH_TRIM  desfase en grados entre los dos servos (montaje del horn) + ajuste fino para que no se peleen
--             (el ajuste fino lo busca tools/buscar_trim_hombro.py). Hombro auxiliar actual: DIR 1, TRIM -57 (medido)
--             (servo auxiliar a -80 = hombro a -20; la camara impide montarlo mas atras).
local H2_KEY = 74
assert(param:add_table(H2_KEY, "BRH_", 3), "no se pudo crear la tabla BRH_")
param:add_param(H2_KEY, 1, "DIR", 0)
param:add_param(H2_KEY, 2, "TRIM", 0)
param:add_param(H2_KEY, 3, "JNT", 2)
local H2_TRIM_MAX = 90
-- Segundo servo del CODO (Script8 = SERVOx_FUNCTION 101, en S12): igual que el anterior, fijo a la articulacion 3.
--   BRE_DIR   0 = sin pulso (por defecto), 1 = mismo sentido que el servo del codo, -1 = en espejo
--   BRE_TRIM  desfase en grados. Al cambiarlo se aplica a MAX_RATE_DPS (sin saltos).
local E2_KEY = 77
assert(param:add_table(E2_KEY, "BRE_", 2), "no se pudo crear la tabla BRE_")
param:add_param(E2_KEY, 1, "DIR", 0)
param:add_param(E2_KEY, 2, "TRIM", 0)
-- dir/trim/jnt: parametros; chan: salida; fijo: articulacion fija (nil = usa jnt)
local AUX = {
  { tag = "doble", dir = Parameter("BRH_DIR"), trim = Parameter("BRH_TRIM"), jnt = Parameter("BRH_JNT"),
    chan = SRV_Channels:find_channel(100) },
  { tag = "doble", dir = Parameter("BRE_DIR"), trim = Parameter("BRE_TRIM"), fijo = 3,
    chan = SRV_Channels:find_channel(101) },
}

-- ===== OFFSETS DE CALIBRACION (en vivo) =====
-- Grados que se suman al angulo pedido antes de convertirlo a pulso, para que 0 = posicion real
-- (brazo recto/vertical). Al cambiar uno, el servo se desplaza a MAX_RATE_DPS (sin saltos).
--   BRO_BASE, BRO_HOMB, BRO_CODO, BRO_MUN, BRO_GIRO   (limite +-OFS_MAX)
local OFS_KEY = 75
assert(param:add_table(OFS_KEY, "BRO_", 5), "no se pudo crear la tabla BRO_")
local OFS_NAMES = { "BASE", "HOMB", "CODO", "MUN", "GIRO" }
local P_OFS = {}
for i = 1, 5 do
  param:add_param(OFS_KEY, i, OFS_NAMES[i], 0)
  P_OFS[i] = Parameter("BRO_" .. OFS_NAMES[i])
end
local OFS_MAX = 45

-- ===== PINZA (en vivo) =====
--   BRG_CLOSE / BRG_OPEN   pulso (us) con la pinza cerrada (0) y abierta (1). Se limitan a 800..2200.
local GRP_KEY = 76
assert(param:add_table(GRP_KEY, "BRG_", 2), "no se pudo crear la tabla BRG_")
param:add_param(GRP_KEY, 1, "CLOSE", 1050)
param:add_param(GRP_KEY, 2, "OPEN", 1750)
local P_GC, P_GO = Parameter("BRG_CLOSE"), Parameter("BRG_OPEN")
local GRIP_STEP_US = 13      -- maximo por ciclo de 20 ms (~60 grados/s)
local grip_us = nil
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
  { name = "giro",    dir = 1,  offset = 0, us_per_deg = 10.6, lo = -90,   hi = 90 },
}
local MIN_US, MAX_US = 500, 2500
local SAFE_MAX_US = 2400   -- margen al tope del servo: 600..2400 us (simetrico respecto de 1500)

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

-- cinematica inversa: punta p exacta, eje de pinza a en el plano del brazo, mandibulas j.
-- u = "arriba" del mundo visto desde el rover; az = componente vertical de la pinza en el mundo: la pinza
-- mantiene su inclinacion aunque la base gire para compensar el roll (si no, la muneca sube al rolar).
local function ik(p, a, j, qc, u, az)
  local rh = sqrt(p[1]*p[1] + p[2]*p[2])
  local d = wrap(deg(atan2(p[2], p[1])) - qc[1])
  if abs(d) > 90 then d = wrap(d - 180) end
  local k = clamp((rh - 20) / 40, 0, 1)          -- cerca del eje vertical la base no gira
  local psi = qc[1] + clamp(k*d, -BASE_COMP_MAX, BASE_COMP_MAX)   -- el tope entra en el calculo
  local c, s = cos(rad(psi)), sin(rad(psi))
  local r = p[1]*c + p[2]*s
  local phi = atan2(a[1]*c + a[2]*s, a[3])
  local A, B = u[1]*c + u[2]*s, u[3]
  local na, top = sqrt(A*A + B*B), atan2(A, B)
  local dphi = math.acos(clamp(az / math.max(na, 0.1), -1, 1))
  if wrap(deg(phi - top)) < 0 then dphi = -dphi end
  -- con la pinza casi vertical la inclinacion no define bien el angulo: ahi vale la proyeccion
  local w_inc = clamp((0.95 - abs(az)) / 0.25, 0, 1)
  phi = phi + w_inc * rad(wrap(deg(top + dphi - phi)))
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
local cur = { 0, 0, 0, 0, 0 }   -- angulo pedido, limitado en velocidad
local phys = { 0, 0, 0, 0, 0 }  -- angulo fisico enviado al servo (cur + offsets), limitado en velocidad

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
    for i = 1, 5 do
      cur[i] = hold[i]
      phys[i] = hold[i] + JOINT[i].offset + clamp(P_OFS[i]:get(), -OFS_MAX, OFS_MAX)
    end
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
      q = ik(to_body(p, roll, pitch), to_body(a, roll, pitch), to_body(j, roll, pitch), h,
        to_body({ 0, 0, 1 }, roll, pitch), a[3])
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
  -- angulo fisico = pedido + offset de calibracion; tambien limitado en velocidad (cambiar BRO_* no salta).
  -- Se limita DESPUES del offset para que el pulso quede en 600..2400 us. En la articulacion con
  -- servo doble el limite vale para los dos, asi nunca topa uno solo (se pelearian).
  for _, A in ipairs(AUX) do
    A.d = A.dir:get()
    A.k = A.fijo or math.floor(A.jnt:get() + 0.5)
    A.on = A.chan and (A.d == 1 or A.d == -1) and A.k >= 1 and A.k <= 4
    local t = clamp(A.trim:get(), -H2_TRIM_MAX, H2_TRIM_MAX)
    -- con el servo activo, un cambio de TRIM entra de a poco; suelto, se toma directo
    A.t = (A.on and A.t) and (A.t + clamp(t - A.t, -step, step)) or t
  end
  for i = 1, 5 do
    local J = JOINT[i]
    local target = q[i] + J.offset + clamp(P_OFS[i]:get(), -OFS_MAX, OFS_MAX)
    local span = (SAFE_MAX_US - 1500) / J.us_per_deg
    local tlo, thi = -span, span
    for _, A in ipairs(AUX) do
      if A.on and i == A.k then
        tlo, thi = math.max(tlo, -span - A.t), math.min(thi, span - A.t)
      end
    end
    target = clamp(target, tlo, thi)
    phys[i] = phys[i] + clamp(target - phys[i], -step, step)
    out(i, clamp(1500 + J.dir * phys[i] * J.us_per_deg, MIN_US, MAX_US))
  end
  -- pinza, con limite de velocidad (al cargar parte en lo pedido, sin recorrido)
  local gc, go = clamp(P_GC:get(), 800, 2200), clamp(P_GO:get(), 800, 2200)
  local gt = gc + (go - gc) * grip
  grip_us = grip_us and (grip_us + clamp(gt - grip_us, -GRIP_STEP_US, GRIP_STEP_US)) or gt
  out(6, grip_us)

  -- servos dobles: mismo angulo fisico que su articulacion (phys ya limitado en velocidad y recorrido).
  -- DIR es relativo al servo principal: 1 = mismo sentido, -1 = en espejo.
  for _, A in ipairs(AUX) do
    if A.on then
      local J = JOINT[A.k]
      local us = clamp(1500 + J.dir * A.d * (phys[A.k] + A.t) * J.us_per_deg, MIN_US, MAX_US)
      SRV_Channels:set_output_pwm_chan_timeout(A.chan, math.floor(us + 0.5), 200)
    elseif A.chan then
      -- apagado: pulso 0 (si solo se deja de escribir, ArduPilot mantiene el ultimo pulso y el servo no se suelta)
      SRV_Channels:set_output_pwm_chan_timeout(A.chan, 0, 200)
    end
  end

  if now - last_report > 2000 then
    last_report = now
    local dobles = ""
    for _, A in ipairs(AUX) do
      if A.on then dobles = dobles .. string.format(" %s j%d d%d t%.1f", A.tag, A.k, A.d, A.t) end
    end
    gcs:send_text(6, string.format("Brazo b%.1f h%.1f c%.1f m%.1f g%.1f %s%s%s", q[1], q[2], q[3], q[4], q[5],
      stab_on and "estab" or "SIN-estab", got_rc and " puente" or "", dobles))
  end
  return update, PERIOD_MS
end

gcs:send_text(6, "brazo_estable.lua cargado")
return update, 1000
