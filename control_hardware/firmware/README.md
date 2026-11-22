# Matek H743: estabilización en S2 y S3

Usamos **ArduPilot Rover** (target `MatekH743`), sin escribir firmware propio.
El driver de *Mount* (gimbal por servo) ya lee la IMU, fusiona la actitud y mueve los servos para compensar la inclinación de la placa.
Más adelante el brazo y la IK se pueden hacer con scripts Lua sobre esta misma base, y Rover ya sabe manejar los motores del rover.

## Estado actual (21-11-2026)

- La placa ya trae **ArduPlane 4.5.7** (board id 1013, MatekH743) y el mount también funciona en Plane, así que **no se reflasheó**.
- Parámetros aplicados con `tools/apply_params.py`. El respaldo previo quedó en `backups/`.
- Verificado con `tools/watch.py COM4`: S2/S3 responden a la inclinación (`RCOut: PWM:1-6`).
- Pasar a Rover más adelante, cuando haya motores (paso 1).

Scripts (`pip install pymavlink`):
- `python tools/info.py COM4` → firmware y parámetros clave
- `python tools/apply_params.py COM4 estabilizador_S2_S3.param --reboot` → respalda y aplica
- `python tools/watch.py COM4 30` → roll/pitch y PWM de S2/S3 en vivo

## 1. Flashear (solo la primera vez)

1. Descarga desde `https://firmware.ardupilot.org/Rover/stable/MatekH743/` el archivo `ardurover_with_bl.hex`.
   (Es el mismo target para H743-WING, SLIM, MINI y WLITE).
2. Mantén apretado el botón **BOOT** de la placa y conecta el USB → entra en modo DFU.
3. Flashea el `.hex` con **STM32CubeProgrammer** (conexión USB) o con el botón *Load custom firmware* de Mission Planner / el flasheador de INAV o Betaflight en modo DFU.
4. Desconecta y vuelve a conectar. Las siguientes actualizaciones se hacen con el `.apj` desde Mission Planner.

## 2. Configurar

1. Conecta con **Mission Planner** (USB, 115200).
2. *Config → Full Parameter List → Load from file* → `estabilizador_S2_S3.param` → **Write Params** → reinicia.
3. Vuelve a cargar el archivo y escribir (algunos `MNT1_*` aparecen solo después de reiniciar con `MNT1_TYPE=1`) → reinicia.
4. *Setup → Mandatory Hardware → Accel Calibration → Calibrate Level* con la placa plana.
   Esto define qué es "nivelado" para la estabilización.

## 3. Conectar los servos

| Pad | Función ArduPilot | Timer |
|---|---|---|
| S2 | `SERVO2` = Mount1 Roll | TIM8 (comparte con S1) |
| S3 | `SERVO3` = Mount1 Pitch | TIM5 (comparte con S4–S6) |

- Señal al pad S2/S3, negativo a G y positivo a la fila de **4V5/Vx** del BEC de servos.
- **Los servos no se alimentan desde el USB.** Hay que conectar una batería (9–36 V) a la placa para que funcione el BEC de servos (5/6/7.2 V según la placa).
- No alimentes servos grandes desde el pin de 5 V de periféricos.

## 4. Probar

- Al arrancar, inclina la placa: S2 debe compensar el roll y S3 el pitch.
- En Mission Planner, pestaña *Servo/Relay Output* o *Status* (`servo2_raw`, `servo3_raw`), se ve cómo cambian los PWM.
- Si un servo corrige **hacia el lado equivocado**, cambia `SERVO2_REVERSED` o `SERVO3_REVERSED` a 1.
- Si el servo gira de más o de menos, ajusta `MNT1_ROLL_MIN/MAX` y `MNT1_PITCH_MIN/MAX` al recorrido real del servo (por ejemplo ±60 si es de 120°).
- Si se atrasa en movimientos rápidos, sube `MNT1_LEAD_RLL` / `MNT1_LEAD_PTCH` de a 0.02.

## Pendiente de verificar en la placa

- La página de Matek no estaba disponible. Que el pad S*n* corresponda a la salida *n* es lo habitual en las Matek H743, pero conviene confirmarlo con el pinout impreso o el diagrama de tu variante.
- Que el mount estabilice sin radio conectado está inferido del modo RC Targeting (objetivo 0°). Si no se mueve, revisa en Mission Planner (*Messages*) que el mount se detectó, confirma que `MNT1_DEFLT_MODE` es 3 y, si sigue quieto, conecta un receptor RC. No uses el modo Neutral (1): ese deja los servos fijos sin estabilizar.

## Brazo completo estabilizado (`scripts/brazo_estable.lua`)

- Salidas: S2 base, S3 hombro, S4 codo, S5 inclinación de muñeca, S6 giro de muñeca (funciones 94–98) y la pinza en **S1** (función 99). La pinza no puede ir en S7: S7–S10 son del L298N a 490 Hz.
- Cómo funciona: la postura pedida (RC override del puente, o `SCR_USER2..6` en grados) se toma en un marco nivelado. Cada 20 ms la H743 calcula con su IMU el roll y el pitch, pasa la punta, el eje de la pinza y las mandíbulas al marco del rover y resuelve la cinemática inversa (geometría del URDF de `brazo_compacto`).
- Prioridad: la punta queda quieta. La inclinación hacia adelante y atrás se compensa del todo; con inclinación lateral, la base gira para seguir la punta y la pinza se ladea un poco, porque 5 articulaciones no dan para más. Con el codo casi recto (|codo| < 8°) usa compensación rígida con el hombro.
- Instalar: `python tools/put_script.py COMx scripts/brazo_estable.lua` y `python tools/apply_params.py COMx brazo_estable.param --reboot`.
- Calibrar en el banco: en `JOINT` de `brazo_estable.lua`, `offset` (que 0° sea el eslabón recto hacia arriba) y `dir` (que + vaya hacia adelante y abajo). `STAB = 0` apaga la compensación.
- Validación: la cinemática coincide con el URDF (error 0) y el Lua da los mismos pulsos que la referencia en Python. En ±15° de inclinación, la punta queda a 0 mm en las posturas de trabajo, sin saltos.

### Seguridad (después del incidente del 2026-11-21)

Con la estabilización completa activada y los servos sin calibrar, la base giró casi 90° de golpe, el Vx se cayó y se soltaron todos los servos. El script ahora trae estos resguardos:
- `MAX_RATE_DPS = 60`: ningún servo se mueve más rápido que eso, ni al compensar ni al cambiar de postura.
- `STAB = 0` por defecto, y la estabilización entra de a poco durante 3 s (`STAB_RAMP_MS`).
- `BASE_COMP_MAX = 25`: la base no se aleja más de 25° de lo pedido.
- `ROLL_BASE = 0` y `YAW_HOLD = 0`: el giro de ±90° de la base con el brazo recto y la compensación de yaw quedan apagados.
- Al arrancar, el primer pulso es 1500 µs (el centro) y no se puede suavizar porque no se sabe dónde está el servo: antes de poner la batería, deja el brazo cerca de la posición recta.
- Para apagar todo: `SCR_ENABLE = 0` (`brazo_off.param`).
