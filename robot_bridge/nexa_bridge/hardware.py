"""Arm (6 servos on a PCA9685) and differential drive (2 TT motors on an L298N), with mock versions for a PC."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("nexa.hw")

POSE_PRESETS: dict[str, list[float]] = {
    "home": [0, 0, 0, 0, 0],
    "recoger": [0, 62, 78, 40, 0],
    "transportar": [0, -10, 110, 60, 0],
    "entregar": [0, 48, 30, 12, 0],
    "saludar": [0, 10, 60, -20, 0],
    "plegado": [0, -20, 120, 75, 0],
}


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class _MockServo:
    def __init__(self) -> None:
        self.angle: float | None = None


class Arm:
    """Joint targets in degrees (0 = arm straight up), moved at a limited speed by update()."""

    def __init__(self, cfg: dict[str, Any], mock: bool) -> None:
        self.cfg = cfg
        self.jmin = cfg["joint_min"]
        self.jmax = cfg["joint_max"]
        self.joints = [0.0] * 5
        self.target = [0.0] * 5
        self.gripper = 0.4
        self.gripper_target = 0.4
        self.speed = float(cfg.get("speed_dps", 90))
        self.mock = mock
        channels = list(cfg["channels"]) + [cfg["gripper_channel"]]
        if mock:
            self.servos = [_MockServo() for _ in channels]
        else:
            from adafruit_servokit import ServoKit  # type: ignore[import-not-found]

            kit = ServoKit(channels=16)
            self.servos = []
            for i, ch in enumerate(channels):
                s = kit.servo[ch]
                s.set_pulse_width_range(cfg["min_pulse"][i], cfg["max_pulse"][i])
                s.actuation_range = 180
                self.servos.append(s)
        self._write(force=True)

    def set_target(self, joints: list[float]) -> None:
        self.target = [clamp(float(j), self.jmin[i], self.jmax[i]) for i, j in enumerate(joints[:5])]

    def set_gripper(self, open01: float) -> None:
        self.gripper_target = clamp(float(open01), 0.0, 1.0)

    def hold(self) -> None:
        self.target = list(self.joints)
        self.gripper_target = self.gripper

    def at_target(self, tol: float = 0.6) -> bool:
        return all(abs(a - b) <= tol for a, b in zip(self.joints, self.target)) and abs(self.gripper - self.gripper_target) < 0.02

    def update(self, dt: float) -> None:
        step = self.speed * dt
        changed = False
        for i in range(5):
            d = self.target[i] - self.joints[i]
            if d:
                self.joints[i] = self.target[i] if abs(d) <= step else self.joints[i] + math.copysign(step, d)
                changed = True
        gd = self.gripper_target - self.gripper
        if gd:
            self.gripper = self.gripper_target if abs(gd) <= 2 * dt else self.gripper + math.copysign(2 * dt, gd)
            changed = True
        if changed:
            self._write()

    def _write(self, force: bool = False) -> None:
        c = self.cfg
        for i in range(5):
            angle = 90 + c["direction"][i] * self.joints[i] + c["offset"][i]
            self.servos[i].angle = clamp(angle, 0, 180)
        g = c["gripper_closed"] + (c["gripper_open"] - c["gripper_closed"]) * self.gripper
        self.servos[5].angle = clamp(g, 0, 180)

    def relax(self) -> None:
        if not self.mock:
            for s in self.servos:
                s.angle = None


@dataclass
class Odometry:
    """Dead reckoning from the commanded speeds (TT motors have no encoders): good for metres, drifts over time."""

    x: float
    y: float
    th: float
    trail: list[tuple[float, float]] = field(default_factory=list)

    def integrate(self, v: float, w: float, dt: float) -> None:
        self.th = math.atan2(math.sin(self.th + w * dt), math.cos(self.th + w * dt))
        self.x += v * math.cos(self.th) * dt
        self.y += v * math.sin(self.th) * dt


class Drive:
    """Differential drive. set(v, w) in m/s and rad/s; the speed is turned into PWM duty on each L298N channel."""

    def __init__(self, cfg: dict[str, Any], mock: bool) -> None:
        self.cfg = cfg
        self.v = 0.0
        self.w = 0.0
        self.mock = mock
        self.max_v = float(cfg["max_wheel_speed"])
        if mock:
            self.left = self.right = None
        else:
            from gpiozero import Motor  # type: ignore[import-not-found]

            self.left = Motor(forward=cfg["left_in1"], backward=cfg["left_in2"], enable=cfg["left_enable"], pwm=True)
            self.right = Motor(forward=cfg["right_in1"], backward=cfg["right_in2"], enable=cfg["right_enable"], pwm=True)

    def set(self, v: float, w: float) -> None:
        half = self.cfg["track"] / 2
        vl, vr = v - w * half, v + w * half
        # scale both wheels together so the curve is kept when one saturates
        peak = max(abs(vl), abs(vr), 1e-9)
        if peak > self.max_v:
            vl, vr = vl * self.max_v / peak, vr * self.max_v / peak
        self.v, self.w = (vl + vr) / 2, (vr - vl) / (2 * half)
        self._motor(self.left, vl, self.cfg["invert_left"])
        self._motor(self.right, vr, self.cfg["invert_right"])

    def stop(self) -> None:
        self.set(0.0, 0.0)

    def _motor(self, m: Any, speed: float, invert: bool) -> None:
        if m is None:
            return
        duty = clamp(speed / self.max_v, -1, 1) * self.cfg["max_duty"]
        if invert:
            duty = -duty
        if abs(duty) < 0.02:
            m.stop()
        elif duty > 0:
            m.forward(duty)
        else:
            m.backward(-duty)

    def close(self) -> None:
        self.stop()
        for m in (self.left, self.right):
            if m is not None:
                m.close()
