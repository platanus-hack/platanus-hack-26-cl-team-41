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
| Codo | S4 | MG995 | **−1** | Dobla el antebrazo hacia adelante | −20 … +95 (no usar más de ~80, ver §5) |
| Muñeca (inclinación) | S5 | MG995 | **−1** | Dobla la pinza hacia adelante y abajo | −45 … +90 (no usar más de ~80) |
| Giro de muñeca | S6 | SG90 | **−1** | Gira las mandíbulas antihorario (vistas de frente) | −90 … +90 |
| Pinza | S1 | SG90 | — | — | 1050 µs cerrada … 1750 µs abierta |

- **Pulso:** `1500 + dir × (grados + offset) × us_por_grado`.
  - `us_por_grado` es 11,1 en los MG995 y 10,6 en el SG90.
  - Son valores nominales, sin medir: hacen que el ángulo real pueda no coincidir con el pedido.
- **Regla práctica:** mantener los pulsos entre 800 y 2200 µs. En 500 µs los servos topan, se traban y botan la alimentación (§5).
- **Por qué hay `dir` en −1:** el codo, la muñeca y el giro iban al revés en el robot y se corrigieron con `dir = −1`. **No cambiar `dir` con el brazo fuera de 0°**: el servo salta al lado opuesto. Para cambiar un `dir`, llevar primero esa articulación a 0°.

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
| **Reposo** (elegida, al encender) | 0 | −30 | 60 | 50 | 0 | Probada en el robot |
| Recto (calibración) | 0 | 0 | 0 | 0 | 0 | Probada |
| Recoger (punta a 5 mm del suelo, a 150 mm del eje, pinza vertical) | 0 | 65,2 | 61,3 | 53,5 | 0 | Solo en el CAD |
| Entregar | 0 | 48 | 30 | 12 | 0 | Solo en el CAD |
| Saludar | 0 | 10 | 60 | −20 | 0 | Solo en el CAD |
| ~~Plegado~~ | 0 | −10 | 95 | 80 | 0 | **No usar**: el codo pide 446 µs, fuera de rango |

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

## 5b. Estado de la estabilización (probada en el robot el 2026-11-21)

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
