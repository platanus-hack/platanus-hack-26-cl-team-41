"""Mide donde aparece la lata en la imagen (mediana de ~3 s) para calibrar la camara.
Uso: .venv\\Scripts\\python medir_lata.py [--coco] -> imprime u (centro x), v_abajo (borde inferior) y alto de la caja.
"""
import sys, time, statistics
import cv2
from ultralytics import YOLO, YOLOWorld

src = "http://172.16.0.127:8080/stream"
if "--coco" in sys.argv:
    m = YOLO("yolo11n.pt"); cls = [39, 41]
else:
    m = YOLOWorld("yolov8s-worldv2.pt"); m.set_classes(["can", "soda can", "tin can"]); cls = None
cap = cv2.VideoCapture(src)
us, vb, hs = [], [], []
t0 = time.time()
while time.time() - t0 < 3.5:
    for _ in range(3):
        cap.grab()
    ok, f = cap.read()
    if not ok:
        continue
    r = m.predict(f, conf=0.15, verbose=False, classes=cls)[0]
    if len(r.boxes):
        b = max(r.boxes, key=lambda b: float(b.conf))
        x1, y1, x2, y2 = b.xyxy[0].tolist()
        us.append((x1 + x2) / 2); vb.append(y2); hs.append(y2 - y1)
print("imagen %dx%d | detecciones %d" % (f.shape[1], f.shape[0], len(us)))
if us:
    print("u=%.0f v_abajo=%.0f alto_caja=%.0f" % (statistics.median(us), statistics.median(vb), statistics.median(hs)))
