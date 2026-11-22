"""WebSocket server speaking the console protocol (see app/src/lib/robot/types.ts)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .behaviors import BEHAVIOURS
from .hardware import POSE_PRESETS
from .robot import Robot

log = logging.getLogger("nexa.server")


class Bridge:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.clients: set[ServerConnection] = set()
        self.robot: Robot | None = None

    # robot -> every console
    def emit(self, msg: dict) -> None:
        if not self.clients:
            return
        data = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clients):
            asyncio.ensure_future(self._send(ws, data))

    async def _send(self, ws: ServerConnection, data: str) -> None:
        try:
            await ws.send(data)
        except ConnectionClosed:
            self.clients.discard(ws)

    def world(self) -> dict:
        b = self.cfg["behaviors"]
        return {
            "size": {"w": 4, "h": 3},
            "objects": [],
            "people": [],
            "toolStation": {"x": b["tool_station"][0], "y": b["tool_station"][1]},
            "materialBin": {"x": b["material_bin"][0], "y": b["material_bin"][1]},
        }

    async def publish_loop(self) -> None:
        r = self.robot
        assert r
        hz = float(self.cfg["server"].get("telemetry_hz", 15))
        n = 0
        while True:
            await asyncio.sleep(1 / hz)
            n += 1
            self.emit({"type": "telemetry", "telemetry": r.telemetry()})
            if n % max(1, int(hz / 5)) == 0:
                dets = [
                    {"id": f"d{i}", "cls": d.cls, "confidence": round(d.confidence, 3), "bbox": [round(v, 4) for v in d.bbox]}
                    for i, d in enumerate(r.vision.detections())
                ]
                self.emit({"type": "detections", "detections": dets})
                self.emit({"type": "stats", "stats": r.stats})

    async def handler(self, ws: ServerConnection) -> None:
        """Consoles get the telemetry; the PC vision client (hello client="nexa-vision") only sends detections."""
        r = self.robot
        assert r
        is_vision = False
        self.clients.add(ws)
        log.info("Client connected (%s)", ws.remote_address)
        await ws.send(json.dumps({"type": "world", "world": self.world()}))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "hello":
                    if msg.get("client") == "nexa-vision":
                        is_vision = True
                        self.clients.discard(ws)
                        r.event("ok", "Visión del PC conectada.")
                    else:
                        r.event("ok", f"{self.cfg['robot']['name']} conectado a la consola.")
                    continue
                if msg.get("type") == "vision_detections":
                    if not is_vision:
                        is_vision = True
                        self.clients.discard(ws)
                    update = getattr(r.vision, "update", None)
                    if update and isinstance(msg.get("detections"), list):
                        update(msg["detections"])
                    continue
                self.handle(msg)
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)
            if is_vision:
                r.event("warn", "Se desconectó la visión del PC.")
            log.info("Client left, %d consoles open", len(self.clients))
            if not is_vision and not self.clients and r.mode == "manual":
                r.start_mode("idle", BEHAVIOURS)  # nobody is driving any more

    def handle(self, msg: dict) -> None:
        r = self.robot
        assert r
        t = msg.get("type")
        if t == "set_mode":
            if isinstance(msg.get("config"), dict):
                r.mission = msg["config"]
            if not r.estop:
                r.start_mode(str(msg.get("mode", "idle")), BEHAVIOURS)
        elif t == "config" and isinstance(msg.get("config"), dict):
            r.mission = msg["config"]
        elif t == "stop":
            r.start_mode("idle", BEHAVIOURS)
        elif t == "estop":
            r.set_estop(bool(msg.get("engaged")))
        elif t == "drive":
            if r.mode != "manual":
                r.start_mode("manual", BEHAVIOURS)
            r.manual_cmd = (float(msg.get("v", 0)), float(msg.get("w", 0)))
            r.manual_until = time.monotonic() + self.cfg["drive"]["watchdog_s"]
        elif t == "joints":
            if r.mode != "manual":
                r.start_mode("manual", BEHAVIOURS)
            r.arm.set_target(list(msg.get("joints", [])))
        elif t == "gripper":
            r.arm.set_gripper(float(msg.get("open", 0)))
        elif t == "pose_preset" and msg.get("name") in POSE_PRESETS:
            r.arm.set_target(POSE_PRESETS[msg["name"]])
        elif t == "assistant_request" and isinstance(msg.get("request"), dict):
            r.requests.put_nowait(msg["request"])
            r.event("info", f"Pedido en cola: {msg['request'].get('action')} «{msg['request'].get('item')}».")
            if r.mode != "asistente" and not r.estop:
                r.start_mode("asistente", BEHAVIOURS)
        elif t == "assistant_confirm":
            r.confirm.set()
        elif t == "person_seen":
            r.person_seen_at = time.monotonic()
            r.event("info", f"La consola vio a una persona ({float(msg.get('confidence', 0)):.0%}).")

    async def run(self, robot: Robot) -> None:
        self.robot = robot
        host, port = self.cfg["server"]["host"], int(self.cfg["server"]["port"])
        async with serve(self.handler, host, port, ping_interval=10, ping_timeout=10):
            log.info("Bridge listening on ws://%s:%d", host, port)
            await asyncio.gather(robot.control_loop(), self.publish_loop())
