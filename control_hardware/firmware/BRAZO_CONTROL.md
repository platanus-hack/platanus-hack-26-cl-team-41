# Control del brazo: convenciones verificadas

Referencia para quien mande el brazo, persona o IA. Los sentidos de giro están **verificados en el robot real** (2026-11-21), mirando cada movimiento. Script: `scripts/brazo_estable.lua` en la Matek H743.

## 1. Convención de ángulos

- **0° en todas las articulaciones** = brazo recto hacia arriba, mandíbulas sin girar y base mirando al frente del rover. Cada servo está a 1500 µs, su centro, y en esa postura el brazo queda "bastante recto" (offsets en 0, sin ajuste fino).
- **Hombro, codo y muñeca:** los ángulos positivos inclinan hacia **adelante y abajo**, hacia el frente del rover. Los ángulos se suman: la dirección de la pinza respecto de la vertical es **hombro + codo + muñeca**.
  - Suma 0°: pinza hacia arriba.
  - Suma 90°: pinza horizontal hacia adelante.
  - Suma 180°: pinza vertical hacia abajo, para recoger del suelo.
- **Base:** positivo = giro **antihorario visto desde arriba**, hacia la **izquierda** del rover.
- **Giro de muñeca:** positivo = **antihorario mirando la pinza de frente**, desde la punta de las mandíbulas hacia la muñeca.

## 2. Salidas, sentido y límites

| Articulación | Salida H743 | Servo | `dir` en el script | + significa | Límite (grados) |
|---|---|---|---|---|---|
| Base | S2 | MG995 | 1 | Gira a la izquierda (antihorario desde arriba) | −90 … +90 (la compensación la aleja a lo más ±25° de lo pedido) |
| Hombro | S3 | MG995 | 1 | Inclina el brazo hacia adelante | −13 … +90; **hasta −30 si el codo está doblado ≥ 45°** |
| Codo | S4 | MG995 | **−1** | Dobla el antebrazo hacia adelante | **19 … 95** con el auxiliar activo (pedir menos lo deja en 19); no usar más de ~80, ver §5 |
| Muñeca (inclinación) | S5 | MG995 | **−1** | Dobla la pinza hacia adelante y abajo | −45 … +90 (no usar más de ~80) |
| Giro de muñeca | S6 | SG90 | 1 (hasta el 2026-11-22 era −1) | Gira las mandíbulas antihorario (vistas de frente) | −90 … +90 |
| Hombro auxiliar | S1 | MG995 | `BRH_DIR` = 1 | Copia el ángulo del hombro (no es una articulación aparte) | El del hombro; desfase `BRH_TRIM` = −57 |
| Codo auxiliar | **S12** | — | `BRE_DIR` = 1 | Copia el ángulo del codo | El del codo; desfase `BRE_TRIM` = −80 |
| Pinza | **S11** | SG90 | — | 0 = cerrada, 1 = abierta | `BRG_CLOSE` 950 µs (dedos apenas tocándose) … `BRG_OPEN` 1750 µs; ~60°/s (calibrada 2026-11-22) |

- **Hombro doble (2026-11-22):** un segundo MG995 en S1 (`SERVO1_FUNCTION = 100`, Script7) ayuda al hombro.
  - Pulso: `1500 + BRH_DIR × (hombro + BRO_HOMB + BRH_TRIM) × 11,1`. Hombro 0° → 945 µs; hombro −30° → 612 µs (su límite es 600); hacia adelante el hombro llega a ~74° porque S3 topa en 2400 µs.
  - Su horn quedó montado con un desfase grande porque la cámara no deja ponerlo más atrás. El ajuste fino (−57) lo encontró `tools/buscar_trim_hombro.py`, que busca la menor corriente (los dos servos sin pelearse).
  - `BRH_DIR = 0` deja el servo auxiliar sin pulso (suelto). **No cambiar `BRH_DIR` ni `BRH_TRIM` de golpe con el servo activo**: salta a toda velocidad. Para cambiarlos, poner antes `BRH_DIR = 0`.
  - Si se calienta o zumba, los dos se están peleando: `BRH_DIR = 0` y repetir la búsqueda del trim.
- **Codo doble (2026-11-22):** un segundo servo en S12 (`SERVO12_FUNCTION = 101`, Script8) ayuda al codo. Parámetros en `codo_doble.param`.
  - Pulso: `1500 − BRE_DIR × (codo + BRO_CODO + BRE_TRIM) × 11,1`, o sea S12 = S4 + 888 µs. Reposo (codo 60°): S4 1056, S12 1944 µs.
  - El horn quedó pegado, por eso el desfase es de −80 y S12 topa en 2400 µs con el codo en 19°: **el brazo no se puede estirar recto** con el auxiliar activo. `BRE_DIR = −1` hace que los servos se peleen.
  - Probado sin pelea de 48° a 78°: 0,11–0,29 A. El resto del recorrido (19–48° y 78–95°) no está probado.
  - `BRE_DIR = 0` manda pulso 0 (suelto). Solo con esta versión del script; antes ArduPilot mantenía el último pulso.

- **Offsets de calibración (a ojo, 2026-11-22), para que 0° sea brazo recto y vertical:** `BRO_BASE` −10, `BRO_HOMB` +7, `BRO_CODO` −20, `BRO_MUN` 0, `BRO_GIRO` −26. Se cambian en vivo y el servo se desplaza a 60°/s. El hombro auxiliar sigue al hombro ya corregido.
  - Ejemplo con todo en 0°: S1 945, S2 1389, S3 1578, S4 1722, S5 1500, S6 1224 µs. El script limita todos los pulsos a 600–2400 µs (la pinza a 800–2200) después de sumar el offset.
  - **Base comprobada (2026-11-22):** con el brazo estirado, +45° y −45° pedidos se vieron como 45° reales a cada lado, y + es la izquierda del rover. Por el offset y los límites de pulso, hacia la derecha llega a unos −71° y hacia la izquierda a 90°.
  - **Sentido del giro corregido (2026-11-22):** con `dir = −1`, +30° se vio horario desde arriba hacia la punta. Ahora `dir = 1`, y +30° se vio antihorario (verificado). Las posturas con giro distinto de 0 anteriores a esta fecha quedan al lado contrario, y la estabilización hay que volver a probarla.
- **Pulso:** `1500 + dir × (grados + offset) × us_por_grado`.
  - `us_por_grado` es 11,1 en los MG995 y 10,6 en el SG90.
  - Son valores nominales, sin medir: hacen que el ángulo real pueda no coincidir con el pedido.
- **Regla práctica:** mantener los pulsos entre 800 y 2200 µs. En 500 µs los servos topan, se traban y botan la alimentación (§5).
- **Por qué hay `dir` en −1:** el codo y la muñeca iban al revés en el robot y se corrigieron con `dir = −1`. **No cambiar `dir` con el brazo fuera de 0°**: el servo salta al lado opuesto. Para cambiar un `dir`, llevar primero esa articulación a 0°.

## 3. Cómo dar órdenes

1. **Sin el puente** (banco de pruebas): `SCR_USER2..6` en grados, en el orden base, hombro, codo, muñeca y giro. Desde el PC:
   ```
   python tools/mover.py COM4 hombro -30
   python tools/mover.py COM4 centro        # todas a 0
   ```
   Los valores quedan guardados y son la postura con que arranca el brazo.
2. **Con el puente** (`robot_bridge` en la Radxa): RC override por MAVLink.
   - Canales 1–5: `1500 + grados × 5`.
   - Canal 6: pinza, de 1000 (cerrada) a 2000 (abierta).
   - Solo se acepta si los 6 canales traen un pulso válido entre 900 y 2100. Si el puente deja de enviar, el brazo mantiene la última postura.
- Cada servo se mueve como máximo a **60°/s** (`MAX_RATE_DPS`): un cambio de 60° tarda 1 s. Hay que esperar a que llegue antes de pedir otra cosa.
- El script informa la postura cada 2 s por STATUSTEXT, por ejemplo `Brazo b0.0 h-30.0 c60.0 m50.0 g0.0 SIN-estab`, y se puede ver con `python tools/watch_brazo.py COM4 10`.

## 4. Posturas

| Postura | Base | Hombro | Codo | Muñeca | Giro | Estado |
|---|---|---|---|---|---|---|
| **Reposo** (al encender; encendido desde cero probado el 2026-11-22) | 0 | −30 | 60 | 50 | 0 | Probada con los offsets nuevos (0,23 A). Es el máximo atrás: el hombro auxiliar (S1) queda en 612 µs y su límite es 600. Para ir más atrás hay que mover su horn |
| Recto (calibración) | 0 | 0 | 0 | 0 | 0 | Probada |
| Recoger (punta a 5 mm del suelo, a 150 mm del eje, pinza vertical) | 0 | 65,2 | 61,3 | 53,5 | 0 | Solo en el CAD |
| Entregar | 0 | 48 | 30 | 12 | 0 | Solo en el CAD |
| Saludar | 0 | 10 | 60 | −20 | 0 | Solo en el CAD |
| ~~Plegado~~ | 0 | −10 | 95 | 80 | 0 | **No usar**: el codo pide 446 µs, fuera de rango |
| Abajo (2026-11-22) | 0 | −4,6 | 83,6 | 60 | 0 | Guardada a la vista en el robot; `firmware/posturas.json` |

Alcance con la punta en el suelo, medido desde el eje de la base:
- **Pinza vertical:** de 118 a 174 mm. Más cerca, el codo pasa su límite; más lejos, el hombro.
- **Pinza inclinada 30°:** de 186 a 241 mm.
- **Pinza inclinada 45°:** de 206 a 256 mm.

Geometría para la cinemática:

| Tramo | Medida |
|---|---|
| Eje de la base → hombro | 46 mm (el hombro está a 162 mm del suelo) |
| Hombro → codo | 90 mm |
| Codo → muñeca | 85 mm |
| Muñeca → punta de los dedos | 144 mm |
| Varilla de la cámara | 93 mm detrás del eje (borde del tubo) |

## 5. Reglas de seguridad (aprendidas con incidentes)

1. **Alimentación:** los MG995 piden de 0,5 a 2,5 A cada uno. Con la fuente limitada a 1 A el voltaje cayó a 5 V y los servos se soltaron: el brazo se cayó dos veces. Usar al menos 2,4 A (mejor 5 A o más) o la LiPo con el Vx a 6 V. Evitar mover varios MG995 con carga a la vez.
2. **Nunca mover de golpe.** Un giro brusco de la base de ~90° hizo caer la alimentación. Mantener `MAX_RATE_DPS` en 60 o menos.
3. **Nada de extremos:** ni pulsos de 500 o 2500 µs ni ángulos de codo o muñeca sobre ~80°.
4. **Varilla de la cámara detrás:**
   - Con el brazo recto, el hombro no puede ir más atrás de −13°.
   - Con la base girada, los límites hacia atrás no están verificados.
5. **Estabilización:** se ajusta en vivo, sin reiniciar el script, con `python tools/setp.py COM4 BRZ_STAB 0.3`.
   - **`BRZ_STAB`:** ganancia de roll y pitch, de 0 a 1. Por defecto 0; subirla de a poco.
   - **`BRZ_ROLLB = 1`:** con el brazo recto, la base gira hasta ±25° para compensar el roll.
   - **`BRZ_YAW = 1`:** mantiene el rumbo; sin brújula deriva.
   - **Límite en reposo:** con el hombro en −30° no queda margen para compensar hacia atrás (rover de nariz abajo), y esa parte se recorta.
6. **Para apagar todo:** `python tools/apply_params.py COM4 brazo_off.param --reboot` (`SCR_ENABLE = 0`; los servos quedan sin pulsos).

## 5b. Estado de la estabilización

**Actual (2026-11-22, H743 montada de lado):**
- **Orientación:** la placa quedó girada ~73° y se usa una rotación a medida: `AHRS_ORIENTATION` 101 con `CUST_ROT1` 72,27 / −4,42 / 92 (`imu_rotacion.param` + `imu_orientacion.param`, requiere reinicio). Apoyado marca roll 0° y pitch 0°. **Si se vuelve a mover la placa hay que medir otra vez** (quieto, nariz arriba, derecha abajo).
- **Signos verificados:** nariz arriba = pitch +, derecha abajo = roll +, giro a la derecha = yaw +.
- **Activa:** `BRZ_STAB` 1, `BRZ_YAW` 0, `BRZ_ROLLB` 0. Probada inclinando al 30% con sentidos correctos a la vista; al 100% solo comprobada quieta y en simulación.
- Se puede apagar con `BRZ_STAB` 0.

**Registro de la prueba anterior (2026-11-21, con la placa plana):**

- **Activa:** `BRZ_STAB = 1` y `BRZ_YAW = 1`; `BRZ_ROLLB = 0`.
- **Roll y pitch:** con roll lateral la base gira para seguir la punta, y el giro de muñeca deshace la rotación de la pinza. La punta se mantuvo en su lugar (verificado a la vista con la ganancia al 30%).
- **Yaw:** la base gira al revés que el rover, casi 1 a 1 (rover +20°, base +20,2°).
- **Limitación con nariz abajo:** en la postura de reposo el hombro está en su tope de −30°. Con el rover inclinado nariz abajo, el hombro no puede ir más atrás y esa compensación se pierde (se vio con 4–7° de pitch negativo).

## 6. Pendiente

- **Offsets finos:** que 0° sea exactamente vertical.
- **`us_por_grado` real de cada servo:** medir dos ángulos conocidos.
- **Recorrido útil de cada servo:** dónde topa.
- **Posturas solo verificadas en el CAD:** probar Recoger, Entregar y Saludar en el robot.
- **Estabilización:** probarla en el robot con el brazo calibrado.
