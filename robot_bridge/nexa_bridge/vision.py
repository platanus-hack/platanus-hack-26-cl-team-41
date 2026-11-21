"""Camera capture, the detection model and an MJPEG stream for the console.

Detections are reported with a bounding box normalised to the image (x, y, w, h in 0..1),
which is what the behaviours steer on. With --mock a fake world places targets around the
robot and produces the boxes a camera would see from the robot's odometry.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("nexa.vision")


@dataclass
class Det:
    cls: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x, y, w, h normalised

    @property
    def cx(self) -> float:
        return self.bbox[0] + self.bbox[2] / 2

    @property
    def h(self) -> float:
        return self.bbox[3]


class Vision:
    """Base: holds the latest detections and frame. Subclasses fill them in from a thread."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.hfov = math.radians(cfg["camera"].get("hfov_deg", 62))
        self._lock = threading.Lock()
        self._dets: list[Det] = []
        self._jpeg: bytes | None = None
        self.stamp = 0.0
        self.running = False

    def detections(self) -> list[Det]:
        with self._lock:
            return list(self._dets)

    def jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def best(self, classes: set[str] | str, max_age: float = 1.0) -> Det | None:
        if time.monotonic() - self.stamp > max_age:
            return None
        cls = {classes} if isinstance(classes, str) else classes
        cands = [d for d in self.detections() if d.cls in cls]
        return max(cands, key=lambda d: d.h * d.confidence, default=None)

    def _publish(self, dets: list[Det], jpeg: bytes | None = None) -> None:
        with self._lock:
            self._dets = dets
            if jpeg is not None:
                self._jpeg = jpeg
            self.stamp = time.monotonic()

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False


class CameraVision(Vision):
    """OpenCV camera + optional YOLO model, in a background thread."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        super().__init__(cfg)
        self.model: Any = None
        self.names: dict[int, str] = {}
        self.class_map: dict[str, str] = cfg["vision"].get("class_map", {})
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        import cv2  # noqa: F401  (fail early if OpenCV is missing)

        vcfg = self.cfg["vision"]
        if vcfg.get("backend") == "yolo":
            model_path = Path(vcfg["model"])
            if not model_path.is_absolute():
                model_path = Path(self.cfg["_dir"]) / model_path
            if model_path.exists():
                from ultralytics import YOLO  # type: ignore[import-not-found]

                self.model = YOLO(str(model_path))
                self.names = dict(self.model.names)
                log.info("Model loaded: %s (%d classes)", model_path.name, len(self.names))
            else:
                log.warning("Model %s not found: the camera runs without detections", model_path)
        super().start()
        self.thread = threading.Thread(target=self._loop, name="vision", daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        import cv2

        c = self.cfg["camera"]
        cap = cv2.VideoCapture(c.get("index", 0))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, c.get("width", 640))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, c.get("height", 480))
        cap.set(cv2.CAP_PROP_FPS, c.get("fps", 15))
        if not cap.isOpened():
            log.error("Could not open camera %s", c.get("index", 0))
            return
        period = 1.0 / float(self.cfg["vision"].get("rate_hz", 6))
        conf = float(self.cfg["vision"].get("confidence", 0.5))
        next_detect = 0.0
        dets: list[Det] = []
        while self.running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            h, w = frame.shape[:2]
            now = time.monotonic()
            if self.model is not None and now >= next_detect:
                next_detect = now + period
                dets = []
                res = self.model.predict(frame, conf=conf, verbose=False)[0]
                for b in res.boxes:
                    x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
                    name = self.names.get(int(b.cls[0]), str(int(b.cls[0])))
                    dets.append(Det(self.class_map.get(name, name), float(b.conf[0]), (x1 / w, y1 / h, (x2 - x1) / w, (y2 - y1) / h)))
            for d in dets:
                x, y, bw, bh = d.bbox
                color = (180, 105, 255) if d.cls == "persona" else (238, 211, 34)
                cv2.rectangle(frame, (int(x * w), int(y * h)), (int((x + bw) * w), int((y + bh) * h)), color, 2)
                cv2.putText(frame, f"{d.cls} {d.confidence:.0%}", (int(x * w) + 4, max(14, int(y * h) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            self._publish(dets, buf.tobytes() if ok else None)
        cap.release()


@dataclass
class FakeTarget:
    cls: str
    x: float
    y: float
    size: float  # bbox height at 1 m


class FakeVision(Vision):
    """For --mock: targets on the console map; boxes computed from where the robot is and where it looks."""

    def __init__(self, cfg: dict[str, Any], pose: Callable[[], tuple[float, float, float]]) -> None:
        super().__init__(cfg)
        self.pose = pose
        b = cfg["behaviors"]
        obj = b["pick_bbox_h"] * 0.28  # an object fills pick_bbox_h at 0.28 m
        self.targets = [
            FakeTarget("persona", 2.6, 1.2, b["person_bbox_h_at_1m"]),
            FakeTarget("persona", 1.2, 2.55, b["person_bbox_h_at_1m"]),
            FakeTarget("botella", 1.2, 1.2, obj),
            FakeTarget("taza", 2.0, 0.8, obj),
            FakeTarget("lata", 1.6, 1.7, obj),
        ]
        self.thread: threading.Thread | None = None

    def remove_nearest(self, cls: str) -> None:
        """Called after a pick: the object is no longer on the floor."""
        x, y, _ = self.pose()
        cands = [t for t in self.targets if t.cls == cls]
        if cands:
            self.targets.remove(min(cands, key=lambda t: math.hypot(t.x - x, t.y - y)))

    def start(self) -> None:
        super().start()
        self.thread = threading.Thread(target=self._loop, name="fake-vision", daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        while self.running:
            x, y, th = self.pose()
            dets = []
            for t in self.targets:
                d = math.hypot(t.x - x, t.y - y)
                bearing = math.atan2(math.sin(math.atan2(t.y - y, t.x - x) - th), math.cos(math.atan2(t.y - y, t.x - x) - th))
                if d < 0.1 or d > 3.0 or abs(bearing) > self.hfov / 2:
                    continue
                h = min(1.0, t.size / d)
                w = h * (0.45 if t.cls == "persona" else 0.8)
                cx = 0.5 - bearing / self.hfov  # left of the robot = left of the image
                dets.append(Det(t.cls, 0.9, (cx - w / 2, 0.5 - h / 2, w, h)))
            self._publish(dets)
            time.sleep(1 / 8)


class MjpegServer:
    """Serves the latest annotated frame at /stream.mjpg."""

    def __init__(self, vision: Vision, port: int) -> None:
        self.vision = vision
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None

    def start(self) -> None:
        vision = self.vision

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # quiet
                pass

            def do_GET(self) -> None:
                if self.path.split("?")[0] not in ("/stream.mjpg", "/"):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    while vision.running:
                        jpg = vision.jpeg()
                        if jpg:
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                        time.sleep(1 / 12)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        threading.Thread(target=self.httpd.serve_forever, name="mjpeg", daemon=True).start()
        log.info("Video at http://<robot>:%d/stream.mjpg", self.port)

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
