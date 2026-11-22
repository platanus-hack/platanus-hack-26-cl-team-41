# Control del hardware real (banco de pruebas)

Lo que se configuró y probó sobre el robot físico: Matek H743 con ArduPilot, Raspberry Pi 5 a bordo, cámara y visión en el PC.

| Carpeta | Qué hay |
|---|---|
| `firmware/` | Parámetros y scripts Lua de la H743. **`BRAZO_CONTROL.md`** documenta sentidos verificados, límites, posturas y reglas de seguridad del brazo. `scripts/brazo_estable.lua` mueve el brazo (RC override en canales 9–14) con estabilización IMU opcional (`BRZ_STAB`, `BRZ_YAW`, `BRZ_ROLLB`) y límite de 60°/s, hombro con dos servos sincronizados (`BRH_*`), offsets de calibración (`BRO_*`) y pulsos de la pinza (`BRG_*`) ajustables en vivo; los valores están en `calibracion_brazo.param` y `reposo_encendido.param`. `scripts/rampa_motores.lua` prueba los motores del L298N. `tools/` tiene utilidades MAVLink para el PC, incluida `buscar_trim_hombro.py` (sincroniza los dos servos del hombro por corriente). `backups/` guarda respaldos de parámetros. |
| `rpi/` | Raspberry Pi 5 (reemplaza a la Radxa): grabación de la microSD con cloud-init, y el puente MAVLink UART↔UDP 14550 (`mav_puente.py`, servicio `mav-puente`). |
| `vision/` | PC con YOLO: `seguir_lata.py` (el brazo apunta a una lata vista por la cámara), `brazo_pose.py` (manda posturas por WiFi y saca fotos), `demo_brazo.py` y `demo_dinamica.py` (demos del brazo por USB, con `--port COM4`), `medir_lata.py` y `calib_camara.json` (calibración de la cámara). |
| `radxa/` | Scripts y servicio de cámara usados con la Radxa Zero 3W (hoy dañada); el servicio `camara.service` también se usa en la Pi. |
| `CLAUDE.md` | Resumen para el asistente: direcciones, servicios y reglas antes de mover el brazo. |

No incluido: entorno virtual (`vision/.venv`), pesos de YOLO (se descargan solos), fotos de la cámara y credenciales (quedan en el PC, en `~/.rover`).

**Demo sí / no con Claude:** escribe `/demo-si-no` en Claude Code; la guía está en [vision/DEMO_SI_NO.md](vision/DEMO_SI_NO.md).

Visión en el PC:

```
cd control_hardware/vision
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\python -m pip install ultralytics pymavlink scipy
.venv\Scripts\python seguir_lata.py --dry
```
