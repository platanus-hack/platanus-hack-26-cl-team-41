# Nexa · puente del robot

Programa en Python que corre en la **Radxa Zero 3W** y une la **consola web** con el robot. Habla el
protocolo WebSocket de la consola (`app/src/lib/robot/types.ts`), manda los servos y los motores a la
**Matek H743** por MAVLink, recibe las detecciones de YOLO desde el **PC** y ejecuta los modos
**ordenar zona**, **asistente** y **saludo**.

```
                 WebSocket :8765                        MAVLink 2, 115200 (SERIAL2 ↔ /dev/ttyS5)
consola (PC) ◀──────────────────▶ nexa_bridge (Radxa) ◀────────────────────▶ H743 + nexa.lua
                                     ▲                                       │  S1–S6  6 servos (50 Hz)
visión (PC, YOLO) ──vision_detections┘                                       │  S7–S10 IN1–IN4 del L298N (490 Hz)
      ▲                                                                      └  IMU → ATTITUDE, batería → SYS_STATUS
      └── video MJPEG ◀── ustreamer :8080/stream (Radxa) ◀── cámara USB 3.0
```

## Qué hace cada equipo

| Equipo | Hace |
|---|---|
| H743 (`h743/nexa.lua`) | Recibe las órdenes como sobreescrituras de canales RC, suma la compensación de la IMU, calibra y genera el PWM de servos y motores; frena las ruedas si deja de recibir |
| Radxa (`nexa_bridge`) | Consola, misiones, odometría (rumbo de la IMU), suavizado de articulaciones, arma y desarma la H743 |
| Radxa (ustreamer) | Video de la cámara sin recomprimir en `:8080/stream` y `:8080/snapshot` |
| PC (`pc_vision`) | YOLO en la GPU sobre ese video; envía las detecciones al puente |

## Conexiones

| Desde | Hacia | Nota |
|---|---|---|
| H743 TX1 / RX1 (SERIAL2) | Radxa pin 33 / pin 32 (`/dev/ttyS5`) | MAVLink 2, 115200, cruzado (TX→RX) |
| H743 GND | Radxa GND | tierra común |
| H743 S1–S6 | servos: base, hombro, codo, inclinación de muñeca, giro de muñeca, pinza | alimentados por el Vx a 6 V |
| H743 S7–S10 | L298N IN1, IN2, IN3, IN4 | ENA y ENB con jumper |
| LiPo 3S | H743 (entrada de batería) y L298N 12 V | con interruptor y fusible |
| H743 5 V (2 A) o power bank | Radxa | 0,8–1,4 A con la cámara |
| Cámara DECXIN | Radxa USB 3.0 | |

Parámetros de la H743 y calibración de servos y motores: [`h743/README.md`](../h743/README.md).

## Instalación en la Radxa

```bash
sudo apt install -y python3-venv ustreamer
cd ~/SOLIDCRAFT/robot_bridge
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # websockets + pymavlink
```

UART: activa el overlay del UART que usa los pines 32/33 (`/dev/ttyS5`) con `rsetup` y comprueba que no
lo ocupe una consola serie.

Video con ustreamer (servicio, por ejemplo `/etc/systemd/system/ustreamer.service`):

```bash
ustreamer --device /dev/video0 --format MJPEG --resolution 1280x720 --desired-fps 30 \
          --host 0.0.0.0 --port 8080
```

Deja el video en `http://<radxa>:8080/stream` y una foto en `/snapshot`, sin recomprimir (unos 15 Mbit/s).

## Uso

```bash
.venv/bin/python -m nexa_bridge                       # robot real (H743 en /dev/ttyS5)
.venv/bin/python -m nexa_bridge --device /dev/ttyACM0 # H743 por USB para probar en la mesa
.venv/bin/python -m nexa_bridge --mock                # en un PC: H743 y cámara simuladas
.venv/bin/python -m nexa_bridge --mock --vision external   # H743 simulada + detecciones reales del PC
```

1. En el PC: `python pc_vision/vision_client.py --show` (ver [`pc_vision/README.md`](../pc_vision/README.md)).
2. En el PC: la consola en local (`npm run dev` en `app/`). En **Ajustes → Robot real** pon `ws://<radxa>:8765`, y en **Visión** pon `http://<radxa>:8080/stream`.
3. En la barra superior deben aparecer **H743** y **Visión** en verde.

Arranque automático: `sudo cp nexa-bridge.service /etc/systemd/system/ && sudo systemctl enable --now nexa-bridge`
(ajusta el usuario y la ruta del archivo).

## Calibración (en este orden, con el brazo sin carga)

1. **Servos y compensación** en `h743/nexa.lua` (dirección, offset, µs/grado, pinza, signos de la compensación de inclinación).
2. **Ruedas.**
   - Si una rueda va al revés: `invert_left` / `invert_right` en `config.toml`.
   - Mide cuántos metros recorre en 5 s a fondo y pon esa velocidad en `max_wheel_speed`. La distancia de la odometría depende de este número; el rumbo lo da la IMU.
3. **Visión.**
   - `[camera] hfov_deg`: el campo de visión real de la cámara.
   - `pick_bbox_h`: alto del recuadro de un objeto cuando la pinza lo alcanza con la postura «Recoger».
   - `person_bbox_h_at_1m`: alto del recuadro de una persona a 1 m.
4. **Mapa.**
   - `start_pose`: dónde dejas el robot al encenderlo, en coordenadas del mapa de la consola.
   - En `[behaviors]`: la estación de herramientas y el contenedor.

## Seguridad

- **Parada de emergencia:** frena las ruedas, congela el brazo y desarma la H743.
- **En reposo** (`idle`): la H743 queda desarmada y los motores no reciben pulsos.
- **Si se cae el enlace con la Radxa:** las sobreescrituras expiran a los 0,5 s (`RC_OVERRIDE_TIME`) y el script frena las ruedas.
- **Si deja de llegar el mando manual:** el puente frena en `watchdog_s`.
- **Si se cae el WiFi:** el robot pierde la visión (la consola muestra «Visión» en rojo). La estabilización sigue, porque corre en la H743.

## Estructura

| Archivo | Qué hace |
|---|---|
| `nexa_bridge/__main__.py` | Arranque y opciones (`--mock`, `--vision`, `--device`, `--port`, `--config`) |
| `nexa_bridge/server.py` | Servidor WebSocket: consola y cliente de visión |
| `nexa_bridge/robot.py` | Estado, lazo de control a 50 Hz, odometría con rumbo de la IMU y primitivas de movimiento |
| `nexa_bridge/behaviors.py` | Los tres modos |
| `nexa_bridge/hardware.py` | `MavlinkController` (H743), `MockController`, brazo y tracción |
| `nexa_bridge/vision.py` | `ExternalVision` (detecciones del PC) y `FakeVision` (mundo falso de `--mock`) |
| `config.toml` | MAVLink, límites, velocidades, cámara y estaciones |
