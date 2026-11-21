"""Robot state, the 50 Hz control loop and the motion primitives the behaviours are written with."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any, Awaitable, Callable

from .hardware import POSE_PRESETS, Arm, Controller, Drive, clamp
from .vision import Det, Vision

log = logging.getLogger("nexa.robot")


class Odometry:
    """Pose on the console map (metres, radians)."""

    def __init__(self, x: float, y: float, th: float) -> None:
        self.x, self.y, self.th = x, y, th

    def integrate(self, v: float, w: float, dt: float) -> None:
        self.th = math.atan2(math.sin(self.th + w * dt), math.cos(self.th + w * dt))
        self.x += v * math.cos(self.th) * dt
        self.y += v * math.sin(self.th) * dt

DEFAULT_MISSION = {
    "ordenar": {"zone": {"x0": 0.5, "y0": 0.4, "x1": 2.6, "y1": 2.0}, "drop": {"x": 3.4, "y": 2.5}, "classes": ["botella", "taza", "lata", "juguete"]},
    "asistente": {"followDistance": 0.7},
    "saludo": {"greeting": "¡Hola! Soy Nexa, encantado de conocerte.", "cooldownS": 30, "range": 1.6},
}


class Cancelled(Exception):
    pass


class Robot:
    def __init__(self, cfg: dict[str, Any], arm: Arm, drive: Drive, fc: Controller, vision: Vision, emit: Callable[[dict], None]) -> None:
        self.cfg = cfg
        self.b = cfg["behaviors"]
        self.arm = arm
        self.drive = drive
        self.fc = fc
        self.vision = vision
        self.emit = emit
        sx, sy, sth = cfg["robot"]["start_pose"]
        self.odom = Odometry(sx, sy, math.radians(sth))
        self._yaw0: float | None = None  # IMU yaw when the bridge started, aligned to start_pose
        self.armed = False
        self.mode = "idle"
        self.phase = "Listo"
        self.task = "Esperando instrucciones"
        self.estop = False
        self.carrying: str | None = None
        self.battery = 100.0
        self.mission: dict[str, Any] = DEFAULT_MISSION
        self.stats = {"collected": 0, "delivered": 0, "received": 0, "greeted": 0}
        self.requests: asyncio.Queue[dict] = asyncio.Queue()
        self.confirm = asyncio.Event()
        self.person_seen_at = 0.0
        self.manual_until = 0.0
        self.manual_cmd = (0.0, 0.0)
        self._cmd = (0.0, 0.0)
        self._task: asyncio.Task | None = None
        self._estop_clear = asyncio.Event()
        self._estop_clear.set()

    # ---------------- events / state ----------------

    def event(self, level: str, text: str, speak: str | None = None) -> None:
        log.info("[%s] %s", level, text)
        ev = {"t": int(time.time() * 1000), "level": level, "text": text}
        if speak:
            ev["speak"] = speak
        self.emit({"type": "event", "event": ev})

    def set(self, phase: str, task: str) -> None:
        self.phase, self.task = phase, task

    def telemetry(self) -> dict:
        att = self.fc.attitude()
        volt = self.fc.voltage()
        if volt:  # 3S LiPo: 9.9 V empty .. 12.6 V full
            self.battery = clamp((volt - 9.9) / (12.6 - 9.9) * 100, 0, 100)
        return {
            "t": time.monotonic(),
            "mode": self.mode,
            "phase": "Parada de emergencia" if self.estop else self.phase,
            "task": self.task,
            "pose": {"x": self.odom.x, "y": self.odom.y, "th": self.odom.th},
            "speed": {"v": self.drive.v, "w": self.drive.w},
            "joints": [round(j, 1) for j in self.arm.joints],
            "gripper": round(self.arm.gripper, 3),
            "battery": self.battery,
            "carrying": self.carrying,
            "estop": self.estop,
            "attitude": {"roll": math.degrees(att[0]), "pitch": math.degrees(att[1])} if att else None,
            "voltage": volt,
            "links": {"fc": bool(self.fc.connected), "vision": self.vision.alive()},
        }

    # ---------------- control loop ----------------

    async def control_loop(self) -> None:
        dt = 1 / 50
        last = time.monotonic()
        while True:
            await asyncio.sleep(dt)
            now = time.monotonic()
            step, last = now - last, now
            if self.estop:
                self.drive.stop()
            else:
                self.arm.update(step)
                if self.mode == "manual":
                    v, w = self.manual_cmd if now < self.manual_until else (0.0, 0.0)
                else:
                    v, w = self._cmd
                self.drive.set(v, w)
            want_armed = not self.estop and self.mode != "idle"
            if want_armed != self.armed:
                self.fc.set_armed(want_armed)
                self.armed = want_armed
            self.fc.send(self.arm.joints, self.arm.gripper, self.drive.left, self.drive.right)
            self._odometry(step)

    def _odometry(self, dt: float) -> None:
        """Distance from the commanded speed (no encoders); heading from the H743's IMU when it reports one."""
        att = self.fc.attitude()
        if att is not None:
            if self._yaw0 is None:
                self._yaw0 = att[2] - self.odom.th
            th = att[2] - self._yaw0
            self.odom.th = math.atan2(math.sin(th), math.cos(th))
            self.odom.integrate(self.drive.v, 0.0, dt)
        else:
            self.odom.integrate(self.drive.v, self.drive.w, dt)

    # ---------------- mode switching ----------------

    def set_estop(self, on: bool) -> None:
        self.estop = on
        if on:
            self._estop_clear.clear()
            self._cmd = (0.0, 0.0)
            self.drive.stop()
            self.arm.hold()
            self.event("error", "Parada de emergencia activada.")
        else:
            self._estop_clear.set()
            self.event("ok", "Parada de emergencia liberada.")

    def start_mode(self, mode: str, behaviours: dict[str, Callable[["Robot"], Awaitable[None]]]) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._cmd = (0.0, 0.0)
        self.mode = mode
        self.confirm.clear()
        if mode != "asistente":
            while not self.requests.empty():
                self.requests.get_nowait()
        if self.carrying:
            self.event("warn", f"Mantengo {self.carrying} en la pinza: suéltalo en manual si hace falta.")
        if mode == "idle":
            self.set("Listo", "Esperando instrucciones")
            self.arm.set_target(POSE_PRESETS["home"])
        elif mode == "manual":
            self.set("Control manual", "Mando por el operador")
        elif mode in behaviours:
            self._task = asyncio.create_task(self._run(mode, behaviours[mode]))

    async def _run(self, mode: str, fn: Callable[["Robot"], Awaitable[None]]) -> None:
        try:
            await fn(self)
        except asyncio.CancelledError:
            self._cmd = (0.0, 0.0)
            raise
        except Exception as e:  # keep the bridge alive whatever a behaviour does
            log.exception("Behaviour %s failed", mode)
            self._cmd = (0.0, 0.0)
            self.set("Error", str(e))
            self.event("error", f"Falló el modo {mode}: {e}")

    # ---------------- primitives ----------------

    async def tick(self) -> None:
        """One behaviour step (10 Hz); waits while the emergency stop is engaged."""
        await asyncio.sleep(0.1)
        if self.estop:
            self._cmd = (0.0, 0.0)
            await self._estop_clear.wait()

    def cmd(self, v: float, w: float) -> None:
        self._cmd = (v, w)

    def stop(self) -> None:
        self._cmd = (0.0, 0.0)

    async def arm_to(self, pose: str | list[float], grip: float | None = None, timeout: float = 6.0) -> None:
        self.arm.set_target(POSE_PRESETS[pose] if isinstance(pose, str) else pose)
        if grip is not None:
            self.arm.set_gripper(grip)
        end = time.monotonic() + timeout
        while not self.arm.at_target() and time.monotonic() < end:
            await self.tick()

    async def wait(self, s: float) -> None:
        end = time.monotonic() + s
        while time.monotonic() < end:
            await self.tick()

    async def goto(self, x: float, y: float, tol: float = 0.08, until: Callable[[], Any] | None = None, timeout: float = 40) -> Any:
        """Drive to (x, y) on the odometry map. `until` may interrupt and its value is returned."""
        end = time.monotonic() + timeout
        vmax = self.drive.max_v * 0.7
        while time.monotonic() < end:
            if until:
                hit = until()
                if hit:
                    self.stop()
                    return hit
            dx, dy = x - self.odom.x, y - self.odom.y
            d = math.hypot(dx, dy)
            if d <= tol:
                break
            err = math.atan2(math.sin(math.atan2(dy, dx) - self.odom.th), math.cos(math.atan2(dy, dx) - self.odom.th))
            w = clamp(2.5 * err, -2.0, 2.0)
            v = 0.0 if abs(err) > 0.9 else vmax * math.cos(err) * clamp(d / 0.4, 0.35, 1.0)
            self.cmd(v, w)
            await self.tick()
        self.stop()
        return None

    async def face(self, x: float, y: float) -> None:
        for _ in range(60):
            err = math.atan2(math.sin(math.atan2(y - self.odom.y, x - self.odom.x) - self.odom.th), math.cos(math.atan2(y - self.odom.y, x - self.odom.x) - self.odom.th))
            if abs(err) < 0.06:
                break
            self.cmd(0.0, clamp(2.5 * err, -1.5, 1.5))
            await self.tick()
        self.stop()

    async def search(self, classes: set[str], timeout: float = 12.0, turn: float | None = None) -> Det | None:
        """Turn in place until the camera sees one of `classes`."""
        end = time.monotonic() + timeout
        w = turn if turn is not None else self.b["search_turn_speed"]
        while time.monotonic() < end:
            d = self.vision.best(classes)
            if d:
                self.stop()
                return d
            self.cmd(0.0, w)
            await self.tick()
        self.stop()
        return None

    async def approach(self, classes: set[str], target_h: float, lost_s: float = 2.0, timeout: float = 25.0) -> Det | None:
        """Visual servoing: keep the target centred and drive until its box is target_h tall."""
        end = time.monotonic() + timeout
        last_seen = time.monotonic()
        last: Det | None = None
        while time.monotonic() < end:
            d = self.vision.best(classes, max_age=0.6)
            if not d:
                if time.monotonic() - last_seen > lost_s:
                    self.stop()
                    return None
                self.cmd(0.0, 0.0)
                await self.tick()
                continue
            last_seen, last = time.monotonic(), d
            err = d.cx - 0.5  # + : target is right of centre
            w = clamp(-2.2 * err, -1.2, 1.2)
            gap = target_h - d.h
            if gap <= 0.0 and abs(err) < 0.08:
                self.stop()
                return d
            v = 0.0 if abs(err) > 0.25 or gap <= 0 else clamp(self.b["approach_speed"] * (0.4 + 2 * gap), 0.05, self.b["approach_speed"])
            self.cmd(v, w)
            await self.tick()
        self.stop()
        return last

    def person_h(self, distance: float) -> float:
        return clamp(self.b["person_bbox_h_at_1m"] / max(distance, 0.2), 0.05, 0.98)
