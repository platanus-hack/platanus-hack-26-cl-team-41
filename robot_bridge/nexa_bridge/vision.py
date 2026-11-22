"""Detections for the behaviours.

The camera video is served on the Radxa by ustreamer (:8080/stream). The PC with the GPU reads it,
runs the YOLO model (pc_vision/vision_client.py) and sends the detections back to the bridge over
the WebSocket; ExternalVision holds them. Boxes are normalised to the image (x, y, w, h in 0..1),
which is what the behaviours steer on. With --mock, FakeVision places targets around the robot and
produces the boxes a camera would see from the robot's odometry.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
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
    """Holds the latest detections; subclasses fill them in."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.hfov = math.radians(cfg["camera"].get("hfov_deg", 62))
        self._lock = threading.Lock()
        self._dets: list[Det] = []
        self.stamp = 0.0
        self.running = False

    def detections(self) -> list[Det]:
        with self._lock:
            return list(self._dets)

    def alive(self, max_age: float = 2.0) -> bool:
        """True while detections keep arriving (an empty list counts: the model saw nothing)."""
        return self.running and time.monotonic() - self.stamp <= max_age

    def best(self, classes: set[str] | str, max_age: float = 1.0) -> Det | None:
        if time.monotonic() - self.stamp > max_age:
            return None
        cls = {classes} if isinstance(classes, str) else classes
        cands = [d for d in self.detections() if d.cls in cls]
        return max(cands, key=lambda d: d.h * d.confidence, default=None)

    def _publish(self, dets: list[Det]) -> None:
        with self._lock:
            self._dets = dets
            self.stamp = time.monotonic()

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False


class ExternalVision(Vision):
    """Detections sent by the PC vision client ({"type": "vision_detections", ...} on the WebSocket)."""

    def update(self, items: list[dict[str, Any]]) -> None:
        dets: list[Det] = []
        for d in items:
            try:
                x, y, w, h = (float(v) for v in d["bbox"])
                dets.append(Det(str(d["cls"]), float(d.get("confidence", 0.0)), (x, y, w, h)))
            except (KeyError, TypeError, ValueError):
                continue
        self._publish(dets)


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
