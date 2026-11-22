"""Seguir una lata con el brazo: YOLO en el PC sobre el video de la Radxa -> postura del brazo -> H743 por MAVLink.

El brazo "mira" la lata: la base gira hacia ella y la pinza apunta a la lata (muneca, y el codo si hace falta).
Hombro fijo en -20 (margen para la estabilizacion). La H743 (brazo_estable.lua) recibe la postura como RC override
(ch1..5 = 1500 + grados*5, ch6 = pinza) y le suma la estabilizacion; el script limita la velocidad a 60 grados/s.

Uso (desde la carpeta vision):
  .venv\\Scripts\\python seguir_lata.py                      # COM4 + stream de la Radxa
  .venv\\Scripts\\python seguir_lata.py --dry                # solo deteccion, sin mover el brazo
  .venv\\Scripts\\python seguir_lata.py --source 0           # webcam local (para probar la deteccion)
Teclas en la ventana: q = salir (el brazo vuelve al reposo), espacio = pausa (el brazo se queda quieto).

La geometria de la camara (--cam-h, --cam-tilt, --cam-back, --hfov) es aproximada: ajustarla mirando si la base
apunta bien a la lata (izquierda/derecha) y si la pinza apunta a su altura.
"""
import argparse, math, time
import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--source", default="http://172.16.0.127:8080/stream")
ap.add_argument("--port", default="udpout:172.16.0.127:14550",
                help="H743: por WiFi via el puente de la Pi (por defecto) o COM4 si esta por USB al PC")
ap.add_argument("--dry", action="store_true", help="no envia nada a la H743")
ap.add_argument("--model", default="yolov8s-worldv2.pt", help="YOLO-World (clases por texto) o un modelo COCO")
ap.add_argument("--classes", default="can,soda can,tin can,beverage can")
ap.add_argument("--coco", action="store_true", help="usar yolo11n.pt (COCO): la lata sale como bottle/cup")
ap.add_argument("--conf", type=float, default=0.15)
ap.add_argument("--hfov", type=float, default=62.0, help="campo de vision horizontal (grados)")
ap.add_argument("--cam-h", type=float, default=0.45, help="altura de la camara sobre el suelo (m)")
ap.add_argument("--cam-tilt", type=float, default=45.0, help="inclinacion hacia abajo (grados)")
ap.add_argument("--cam-back", type=float, default=0.08, help="distancia de la camara detras del eje del brazo (m)")
ap.add_argument("--obj-h", type=float, default=0.06, help="altura del centro de la lata (m)")
ap.add_argument("--smooth", type=float, default=0.3, help="filtro 0..1 (mas bajo = mas suave)")
args = ap.parse_args()

# ---------- brazo (convenciones de firmware/BRAZO_CONTROL.md) ----------
L1, L2, HS, Z_BASE = 0.090, 0.085, 0.046, 0.116   # m; Z_BASE = eje de la base sobre el suelo
REST = [0.0, -30.0, 60.0, 50.0, 0.0]               # reposo guardado en la H743
SHOULDER = -20.0
# codo y muneca hasta 70 grados (~720 us): lejos del tope del servo (ver BRAZO_CONTROL.md, regla 3)
ELBOW0, WRIST_MAX, ELBOW_MAX, WRIST_MIN, SHOULDER_MAX = 60.0, 70.0, 70.0, -45.0, 30.0
GRIP = 0.4                                          # 0 cerrada .. 1 abierta


def pose_hacia(base, dist, alto):
    """Postura que apunta la pinza a un punto a 'dist' m del eje y 'alto' m sobre el suelo.
    El angulo que falta se reparte: muneca, luego codo, luego hombro hacia adelante."""
    s, e = math.radians(SHOULDER), math.radians(ELBOW0)
    rw = L1 * math.sin(s) + L2 * math.sin(s + e)
    zw = Z_BASE + HS + L1 * math.cos(s) + L2 * math.cos(s + e)
    phi = math.degrees(math.atan2(dist - rw, alto - zw))      # direccion de la pinza desde la vertical
    extra = phi - SHOULDER - ELBOW0                             # lo que le toca a la muneca
    w = max(WRIST_MIN, min(WRIST_MAX, extra)); extra -= w
    e_deg = min(ELBOW_MAX, ELBOW0 + max(0.0, extra)); extra -= e_deg - ELBOW0
    s_deg = min(SHOULDER_MAX, SHOULDER + max(0.0, extra))
    return [max(-90.0, min(90.0, base)), s_deg, e_deg, w, 0.0]


import json, os
_cal = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib_camara.json")
CALIB = np.array(json.load(open(_cal))["homografia_pixel_a_mesa"]) if os.path.exists(_cal) else None
LATA_RADIO = 0.033


def mesa_desde_pixel(u, v_abajo):
    """Calibracion medida (homografia de 4 puntos): pixel del borde inferior -> (base_grados, distancia_m al centro)."""
    p = CALIB @ np.array([u, v_abajo, 1.0])
    X, Y = p[0] / p[2] + LATA_RADIO, p[1] / p[2]
    d = min(0.60, max(0.10, math.hypot(X, Y)))
    return math.degrees(math.atan2(Y, X)), d


def pixel_a_suelo(u, v, W, H):
    """Rayo de la camara -> punto a la altura de la lata. Devuelve (base_grados, distancia_m) o (base, None)."""
    fx = (W / 2) / math.tan(math.radians(args.hfov / 2))
    xn, yn = (u - W / 2) / fx, (v - H / 2) / fx
    t = math.radians(args.cam_tilt)
    a = np.array([math.cos(t), 0, -math.sin(t)])      # eje optico (X adelante, Y izquierda, Z arriba)
    b = np.array([-math.sin(t), 0, -math.cos(t)])     # "abajo" de la imagen
    c = np.array([0, -1, 0])                          # "derecha" de la imagen
    ray = a + xn * c + yn * b
    if ray[2] >= -1e-3:                               # sobre el horizonte: solo direccion
        return math.degrees(math.atan2(ray[1], ray[0])), None
    lam = -(args.cam_h - args.obj_h) / ray[2]
    X, Y = lam * ray[0] - args.cam_back, lam * ray[1]
    return math.degrees(math.atan2(Y, X)), math.hypot(X, Y)


# ---------- MAVLink ----------
mav = None
if not args.dry:
    from pymavlink import mavutil
    mav = mavutil.mavlink_connection(args.port, baud=115200, source_system=255)   # 255 = SYSID_MYGCS
    for _ in range(3):   # por UDP el puente de la Pi solo reenvia a quien ya le hablo
        mav.mav.heartbeat_send(6, 8, 0, 0, 0); time.sleep(0.2)
    if not mav.wait_heartbeat(timeout=10):
        raise SystemExit("La H743 no responde por %s" % args.port)
    # la camara gira con el rover: el rumbo fijo (BRZ_YAW) se apaga mientras se sigue la lata
    mav.mav.param_set_send(mav.target_system, mav.target_component, b"BRZ_YAW", 0.0,
                           mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    print("H743 conectada; BRZ_YAW = 0 (el brazo apunta relativo al rover)")


def enviar(pose, grip=GRIP):
    if mav is None:
        return
    ch = [int(round(1500 + max(-100, min(100, p)) * 5)) for p in pose]
    ch.append(int(round(1000 + grip * 1000)))
    mav.mav.rc_channels_override_send(mav.target_system, mav.target_component, *([65535] * 8), *ch)
    mav.mav.heartbeat_send(6, 8, 0, 0, 0)   # mantiene vivo el puente UDP


# ---------- detector ----------
from ultralytics import YOLO
if args.coco:
    model = YOLO("yolo11n.pt"); keep = {39, 41}            # bottle, cup
else:
    from ultralytics import YOLOWorld
    model = YOLOWorld(args.model); model.set_classes([c.strip() for c in args.classes.split(",")]); keep = None

src = int(args.source) if args.source.isdigit() else args.source
cap = cv2.VideoCapture(src)
if not cap.isOpened():
    raise SystemExit("No se pudo abrir el video: %s" % args.source)

pose = list(REST); last_seen = 0; paused = False; t_send = 0
print("q = salir, espacio = pausa")
while True:
    ok, frame = cap.read()
    if not ok:
        time.sleep(0.05); continue
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    Hh, Ww = frame.shape[:2]
    res = model.predict(frame, conf=args.conf, verbose=False)[0]
    best = None
    for bx in res.boxes:
        cls = int(bx.cls)
        if keep is not None and cls not in keep:
            continue
        x1, y1, x2, y2 = bx.xyxy[0].tolist()
        score = float(bx.conf) * (x2 - x1) * (y2 - y1)
        if best is None or score > best[0]:
            best = (score, x1, y1, x2, y2, float(bx.conf), res.names[cls])
    info = "sin lata"
    if best:
        _, x1, y1, x2, y2, conf, name = best
        u, v = (x1 + x2) / 2, (y1 + y2) / 2
        if CALIB is not None:
            base, dist = mesa_desde_pixel(u, y2)      # borde inferior = donde la lata toca la mesa
        else:
            base, dist = pixel_a_suelo(u, v, Ww, Hh)
        target = pose_hacia(base, dist, args.obj_h) if dist else [base] + pose[1:]
        a = args.smooth
        pose = [p + a * (t - p) for p, t in zip(pose, target)]
        last_seen = time.time()
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        info = "%s %.2f | base %+.0f  dist %s" % (name, conf, base, "%.2fm" % dist if dist else "?")
    if not paused and time.time() - t_send > 0.05:
        enviar(pose); t_send = time.time()
    cv2.putText(frame, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "b%+.0f h%+.0f c%+.0f m%+.0f%s" % (*pose[:4], "  PAUSA" if paused else ""),
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.imshow("seguir lata", frame)
    k = cv2.waitKey(1) & 0xFF
    if k == ord("q"):
        break
    if k == ord(" "):
        paused = not paused

print("Volviendo al reposo...")
for _ in range(40):
    enviar(REST); time.sleep(0.05)
cap.release(); cv2.destroyAllWindows()
