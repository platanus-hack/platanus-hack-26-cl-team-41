# Nexa · puente del robot

Programa en Python que corre en el robot (Raspberry Pi 4/5 recomendada) y une la **consola web** con el
hardware: el brazo (PCA9685), las ruedas (L298N), la cámara y **su modelo de reconocimiento**.
Habla el protocolo WebSocket de la consola (`app/src/lib/robot/types.ts`) y ejecuta los modos
**ordenar zona**, **asistente** y **saludo** en el propio robot.

```
consola web ──WebSocket :8765──▶ nexa_bridge ──I2C──▶ PCA9685 ──▶ 4×MG995 + 2×SG90
   ▲                               │  └─GPIO PWM──▶ L298N ──▶ 2 motores TT
   └──── video MJPEG :8080 ◀── cámara + YOLO (best.pt)
```

## Cableado

| Desde | Hacia | Nota |
|---|---|---|
| Pi pin 3 (GPIO2, SDA) | PCA9685 SDA | |
| Pi pin 5 (GPIO3, SCL) | PCA9685 SCL | |
| Pi pin 1 (3,3 V) | PCA9685 VCC | lógica |
| Regulador 6 V **≥10 A** | PCA9685 V+ (borne de servos) | los 4 MG995 piden ~10 A de pico; nunca desde la Pi |
| PCA9685 canales 0–4 | base, hombro, codo, muñeca, giro de muñeca | ver `[arm] channels` |
| PCA9685 canal 5 | pinza (SG90) | |
| Pi GPIO12 (pin 32) | L298N **ENA** | quita el puente (jumper) de ENA |
| Pi GPIO5 / GPIO6 | L298N IN1 / IN2 | motor izquierdo |
| Pi GPIO13 (pin 33) | L298N **ENB** | quita el puente de ENB |
| Pi GPIO19 / GPIO26 | L298N IN3 / IN4 | motor derecho |
| Batería 3S | L298N 12 V | con interruptor y fusible |
| **Todas las tierras** | GND común | Pi, PCA9685, regulador y L298N |

La Pi se alimenta aparte, con un regulador de 5 V / 5 A desde la batería.

## Instalación (Raspberry Pi OS Bookworm, 64 bits)

```bash
sudo raspi-config nonint do_i2c 0           # activa I2C
sudo apt install -y python3-venv python3-lgpio
cd ~/SOLIDCRAFT/robot_bridge
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
mkdir -p models && cp /ruta/a/best.pt models/best.pt   # el modelo que entrenaron
```

Clases del modelo: en `config.toml`, `[vision.class_map]` traduce el nombre de cada clase de su
modelo al nombre que usa la consola (`persona`, `botella`, `taza`, `lata`, `juguete`, `tornillo`, `libro`).
La clase de las personas tiene que llegar como `persona`.

## Uso

```bash
.venv/bin/python -m nexa_bridge          # robot real
.venv/bin/python -m nexa_bridge --mock   # en un PC, sin hardware: servos, motores y cámara simulados
```

En la consola: **Ajustes → Robot real**, dirección `ws://<ip-del-robot>:8765`, y en **Visión** el video
`http://<ip-del-robot>:8080/stream.mjpg`.

**Consola en Vercel (https):** el navegador bloquea `ws://` hacia otra máquina. Expón el robot con un
túnel, por ejemplo `cloudflared tunnel --url http://localhost:8765`, y conéctate a la dirección
`wss://….trycloudflare.com` que te da. O usa la consola en local (`npm run dev` en `app/`), en la misma red que el robot.

Arranque automático al encender:

```bash
sudo cp nexa-bridge.service /etc/systemd/system/
sudo systemctl enable --now nexa-bridge
journalctl -u nexa-bridge -f      # ver el registro
```

## Calibración (hazla en este orden, con el brazo sin carga)

1. **Servos.** En la consola, **Control manual → Posturas → Recto**. Cada articulación debe quedar en 0°
   (el brazo recto hacia arriba). Corrige con `[arm] offset` (grados) y, si una gira al revés,
   pon `-1` en `direction`. Ajusta `gripper_closed` / `gripper_open` para la pinza.
2. **Ruedas.** Avanza con el joystick: si una rueda va al revés, usa `invert_left` / `invert_right`.
   Mide cuántos metros recorre en 5 s a fondo y pon esa velocidad en `max_wheel_speed`: la
   odometría (y por tanto la zona y las estaciones del mapa) depende de este número.
3. **Visión.**
   - `pick_bbox_h`: qué tan alto se ve un objeto en la imagen (fracción de la imagen) cuando la pinza lo alcanza con la postura «Recoger».
   - `person_bbox_h_at_1m`: altura del recuadro de una persona a 1 m.
   - Con ambos el robot calcula a qué distancia detenerse.
4. **Mapa.** `start_pose` es dónde dejas el robot al encenderlo, en las coordenadas del mapa de la
   consola. Las estaciones de herramientas y el contenedor van en `[behaviors]`.

## Cómo funcionan los modos

- **Ordenar zona:**
  - Barre la zona en zigzag usando la odometría.
  - Cuando el modelo ve una clase elegida, se acerca guiado por la cámara hasta que el recuadro alcanza `pick_bbox_h`.
  - Lo recoge, va al punto de entrega y lo suelta. Luego sigue el barrido.
- **Asistente:**
  - Mantiene a la persona centrada en la imagen y a la distancia de seguimiento.
  - Si le pides una herramienta: va a la estación, la toma, vuelve, te busca, te la extiende y espera tu confirmación.
  - Si le pasas un material: lo recibe y lo lleva al contenedor.
- **Saludo:**
  - Recorre el área. Cuando ve a una persona se acerca a `greet_distance`, saluda con el brazo y la consola habla.
  - Después espera un rato antes de volver a saludar.
  - Si la cámara de la consola ve a alguien, también saluda.

Seguridad:
- **Parada de emergencia:** frena los motores al instante y congela el brazo.
- **Sin mando en manual:** si deja de llegar el mando durante `watchdog_s`, el robot frena.
- **Al cerrar el programa:** apaga los motores.

**Límites conocidos:**
- Los motores TT no tienen encoders. La posición sale de la velocidad mandada y se desvía con el tiempo. Para recorridos largos conviene volver a la posición inicial o agregar encoders o un IMU.
- El modo asistente sigue a la persona más grande de la imagen, sin reconocer quién es.

## Estructura

| Archivo | Qué hace |
|---|---|
| `nexa_bridge/__main__.py` | Arranque y opciones (`--mock`, `--config`, `--port`) |
| `nexa_bridge/server.py` | Servidor WebSocket y protocolo de la consola |
| `nexa_bridge/robot.py` | Estado, lazo de control a 50 Hz y primitivas (ir a, buscar, acercarse, mover el brazo) |
| `nexa_bridge/behaviors.py` | Los tres modos |
| `nexa_bridge/hardware.py` | Brazo (PCA9685) y tracción (L298N), con versiones simuladas |
| `nexa_bridge/vision.py` | Cámara, modelo YOLO, video MJPEG y el mundo falso de `--mock` |
| `config.toml` | Pines, servos, velocidades, clases y estaciones |
