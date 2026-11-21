"""PC vision client: reads the robot's video (ustreamer on the Radxa), runs the YOLO model on the GPU
and sends the detections to the robot bridge over the WebSocket.

usage: python vision_client.py [--config config.toml] [--show]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import time
import tomllib
from pathlib import Path
from typing import Any

import cv2
import websockets
from ultralytics import YOLO

log = logging.getLogger("nexa.pc_vision")
HERE = Path(__file__).resolve().parent


class Grabber:
    """Keeps only the newest frame of the MJPEG stream, reconnecting when it drops."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.frame = None
        self.stamp = 0.0
        self.lock = threading.Lock()
        self.running = True
        threading.Thread(target=self._loop, name="grabber", daemon=True).start()

    def _loop(self) -> None:
        while self.running:
            cap = cv2.VideoCapture(self.url)
            if not cap.isOpened():
                log.warning("No video at %s, retrying", self.url)
                time.sleep(2)
                continue
            log.info("Video open: %s", self.url)
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    log.warning("Video dropped, reconnecting")
                    break
                with self.lock:
                    self.frame, self.stamp = frame, time.monotonic()
            cap.release()

    def latest(self):
        with self.lock:
            return self.frame, self.stamp


def detect(model: YOLO, frame, cfg: dict[str, Any], names: dict[int, str]) -> list[dict]:
    h, w = frame.shape[:2]
    res = model.predict(frame, conf=float(cfg["confidence"]), device=cfg.get("device", 0), verbose=False)[0]
    class_map: dict[str, str] = cfg.get("class_map", {})
    out = []
    for b in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
        name = names.get(int(b.cls[0]), str(int(b.cls[0])))
        out.append({
            "cls": class_map.get(name, name),
            "confidence": round(float(b.conf[0]), 3),
            "bbox": [round(x1 / w, 4), round(y1 / h, 4), round((x2 - x1) / w, 4), round((y2 - y1) / h, 4)],
        })
    return out


def draw(frame, dets: list[dict]) -> None:
    h, w = frame.shape[:2]
    for d in dets:
        x, y, bw, bh = d["bbox"]
        p1, p2 = (int(x * w), int(y * h)), (int((x + bw) * w), int((y + bh) * h))
        color = (180, 105, 255) if d["cls"] == "persona" else (238, 211, 34)
        cv2.rectangle(frame, p1, p2, color, 2)
        cv2.putText(frame, f"{d['cls']} {d['confidence']:.0%}", (p1[0] + 4, max(14, p1[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


async def run(cfg: dict[str, Any], show: bool) -> None:
    v = cfg["vision"]
    model_path = Path(v["model"])
    if not model_path.is_absolute():
        model_path = HERE / model_path
    model = YOLO(str(model_path))
    names = dict(model.names)
    log.info("Model %s (%d classes) on device %s", model_path.name, len(names), v.get("device", 0))
    grabber = Grabber(cfg["robot"]["video_url"])
    period = 1.0 / float(v.get("rate_hz", 10))

    while True:
        try:
            async with websockets.connect(cfg["robot"]["bridge_url"], open_timeout=5, ping_interval=10) as ws:
                await ws.send(json.dumps({"type": "hello", "client": "nexa-vision", "version": 1}))
                log.info("Connected to the bridge: %s", cfg["robot"]["bridge_url"])
                last_stamp = 0.0
                while True:
                    t0 = time.monotonic()
                    frame, stamp = grabber.latest()
                    if frame is not None and stamp != last_stamp and t0 - stamp < 1.0:
                        last_stamp = stamp
                        frame = frame.copy()
                        dets = await asyncio.to_thread(detect, model, frame, v, names)
                        await ws.send(json.dumps({"type": "vision_detections", "detections": dets}, ensure_ascii=False))
                        if show:
                            draw(frame, dets)
                            cv2.imshow("Nexa vision", frame)
                            if cv2.waitKey(1) & 0xFF == ord("q"):
                                grabber.running = False
                                return
                    await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))
        except (OSError, websockets.ConnectionClosed, asyncio.TimeoutError) as e:
            log.warning("Bridge not reachable (%s), retrying in 2 s", e)
            await asyncio.sleep(2)


def main() -> None:
    ap = argparse.ArgumentParser(description="YOLO on the PC for the Nexa robot")
    ap.add_argument("--config", default=str(HERE / "config.toml"))
    ap.add_argument("--show", action="store_true", help="show a preview window with the boxes (q to quit)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    try:
        asyncio.run(run(cfg, args.show))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
