# Matek H743 · script y parámetros

`nexa.lua` es el script de referencia que entiende lo que envía el puente (`robot_bridge`). Va en la
carpeta `APM/scripts/` de la SD de la H743 (ArduPilot 4.5.x).

> **Si ya tienen su propio script verificado** (el de la estabilización y la rampa de motores que
> probaron en hardware), revisen si recibe las órdenes de la misma forma. El puente envía
> **sobreescrituras de canales RC por MAVLink** con esta codificación:
>
> | Canal | Contenido |
> |---|---|
> | 1–5 | ángulo de cada articulación: `1500 + grados × 5` (base, hombro, codo, inclinación y giro de muñeca) |
> | 6 | pinza: 1000 cerrada … 2000 abierta |
> | 7 / 8 | rueda izquierda / derecha: `1500 + 500 × ciclo de trabajo` (−1…1) |
>
> O adoptan `nexa.lua`, o adaptan su script a esta tabla. `deg_scale` se cambia en `[mavlink]` de
> `robot_bridge/config.toml`, y debe ser igual a `DEG_SCALE` en el script.

## Parámetros

| Parámetro | Valor | Para qué |
|---|---|---|
| `SCR_ENABLE` | 1 | Activa los scripts Lua (reiniciar la placa después) |
| `SERIAL2_PROTOCOL` | 2 | MAVLink 2 en TX1/RX1 hacia la Radxa |
| `SERIAL2_BAUD` | 115 | 115200 baudios |
| `SYSID_MYGCS` | 255 | Acepta las sobreescrituras del puente (sysid 255) |
| `RC_OVERRIDE_TIME` | 0.5 | Si el puente deja de enviar, a los 0,5 s el script deja de recibir órdenes: las ruedas paran |
| `SERVO1_FUNCTION`…`SERVO6_FUNCTION` | 94…99 | S1–S6: base, hombro, codo, inclinación de muñeca, giro de muñeca, pinza |
| `SERVO7_FUNCTION`…`SERVO10_FUNCTION` | 100…103 | S7–S10: IN1, IN2, IN3, IN4 del L298N (ENA y ENB con jumper) |
| `SERVO11_FUNCTION` | 104 | S11: segundo servo del hombro (lado B). Recibe el mismo ángulo que S2, con su propio `offset` en `SHOULDER_B` del script |
| Frecuencia del grupo de timer de S1–S6 | 50 Hz | Servos (por ejemplo `SERVO_GPIO`/`SERVO_RATE` según la placa) |
| Frecuencia del grupo de timer de S7–S10 | 490 Hz | Motores (por ejemplo `SERVO_RATE` del grupo o `ONESHOT_MASK` según la versión) |
| `ARMING_CHECK` | 0 | El puente arma la placa al iniciar un modo y la desarma en reposo o en parada de emergencia |

Mientras la placa está desarmada el script deja S7–S10 en 0, así que los motores no se mueven.

## Calibración (al principio de `nexa.lua`)

1. **Servos.** Para cada articulación: `dir` (1 o −1), `offset` en grados (para que 0° sea el brazo
   recto hacia arriba), `us_per_deg` y los límites `min_us`/`max_us` de pulso. La pinza usa
   `GRIPPER_CLOSED_US` y `GRIPPER_OPEN_US`.
2. **Compensación de inclinación.**
   - **Qué hace:** separa el roll y el pitch de la base en la componente del plano del brazo (la corrige el hombro) y la componente transversal (la corrige el giro de la muñeca), según el ángulo de la base.
   - **Cómo verificarla:** inclina la base hacia adelante; el brazo debe seguir vertical. Si se mueve al revés, cambia `SIGN_SHOULDER`. Haz lo mismo con el roll y `SIGN_WRIST_ROLL`.
   - **Para apagarla:** `STAB_GAIN = 0`.
3. **Motores.**
   - `MAX_DUTY = 0.55` limita el voltaje medio en los TT a unos 6 V con la 3S.
   - `PWM_PERIOD_US` debe corresponder a la frecuencia del grupo de timer (2040 µs a 490 Hz).
   - Verifica con el robot en el aire que adelante sea adelante; si una rueda va al revés, usa `invert_left`/`invert_right` en el puente.
