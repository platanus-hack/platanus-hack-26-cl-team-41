"""Arm and drive, commanded through a flight controller (Matek H743 + ArduPilot) over MAVLink.

The bridge sends what it wants (joint angles in degrees, wheel duties -1..1) as RC override channels;
the Lua script on the H743 (h743/nexa.lua) adds the IMU tilt compensation, maps them to servo pulses
and drives the L298N inputs. The H743 sends back its attitude and the battery voltage.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from typing import Any, Protocol

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


class Controller(Protocol):
    """What the bridge needs from the real-time board."""

    connected: bool

    def send(self, joints: list[float], gripper: float, left: float, right: float) -> None: ...
    def set_armed(self, armed: bool) -> None: ...
    def attitude(self) -> tuple[float, float, float] | None: ...  # roll, pitch, yaw (rad)
    def voltage(self) -> float | None: ...
    def close(self) -> None: ...


# ---------------------------------------------------------------- MAVLink (real H743)

class MavlinkController:
    """RC override channels (see [mavlink] in config.toml):
    ch1..5  joint angle  = 1500 + deg * scale   (scale µs per degree, default 5 -> ±100°)
    ch6     gripper      = 1000 (closed) .. 2000 (open)
    ch7/ch8 left/right wheel duty = 1500 + duty * 500, duty in -1..1 (the Lua script caps it at MAX_DUTY)
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        from pymavlink import mavutil  # type: ignore[import-not-found]

        self.cfg = cfg
        self.mavutil = mavutil
        self.scale = float(cfg.get("deg_scale", 5.0))
        self.connected = False
        self._att: tuple[float, float, float] | None = None
        self._volt: float | None = None
        self._last_rx = 0.0
        self._lock = threading.Lock()
        self.m = mavutil.mavlink_connection(
            cfg["device"], baud=int(cfg.get("baud", 115200)), source_system=int(cfg.get("gcs_sysid", 255)), source_component=190
        )
        self._stop = False
        threading.Thread(target=self._rx, name="mavlink-rx", daemon=True).start()
        threading.Thread(target=self._heartbeat, name="mavlink-hb", daemon=True).start()
        log.info("MAVLink on %s @ %s", cfg["device"], cfg.get("baud", 115200))

    def _heartbeat(self) -> None:
        mav = self.mavutil.mavlink
        requested = False
        while not self._stop:
            self.m.mav.heartbeat_send(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            if self.connected and not requested:
                self._interval(mav.MAVLINK_MSG_ID_ATTITUDE, 20)
                self._interval(mav.MAVLINK_MSG_ID_SYS_STATUS, 2)
                requested = True
            if time.monotonic() - self._last_rx > 2.0:
                if self.connected:
                    log.warning("H743 silent: link lost")
                self.connected, requested = False, False
            time.sleep(1.0)

    def _interval(self, msg_id: int, hz: float) -> None:
        mav = self.mavutil.mavlink
        self.m.mav.command_long_send(self.m.target_system, self.m.target_component, mav.MAV_CMD_SET_MESSAGE_INTERVAL, 0, msg_id, 1e6 / hz, 0, 0, 0, 0, 0)

    def _rx(self) -> None:
        while not self._stop:
            msg = self.m.recv_match(blocking=True, timeout=0.5)
            if msg is None:
                continue
            t = msg.get_type()
            if t == "HEARTBEAT" and msg.get_srcComponent() == 1:
                if not self.connected:
                    self.m.target_system, self.m.target_component = msg.get_srcSystem(), 1
                    log.info("H743 found (sysid %d)", msg.get_srcSystem())
                self.connected = True
                self._last_rx = time.monotonic()
            elif t == "ATTITUDE":
                with self._lock:
                    self._att = (msg.roll, msg.pitch, msg.yaw)
                self._last_rx = time.monotonic()
            elif t == "SYS_STATUS" and msg.voltage_battery not in (0, 65535):
                self._volt = msg.voltage_battery / 1000.0

    def send(self, joints: list[float], gripper: float, left: float, right: float) -> None:
        if not self.connected:
            return
        ch = [int(clamp(1500 + j * self.scale, 1000, 2000)) for j in joints[:5]]
        ch.append(int(1000 + 1000 * clamp(gripper, 0, 1)))
        ch += [int(1500 + 500 * clamp(left, -1, 1)), int(1500 + 500 * clamp(right, -1, 1))]
        self.m.mav.rc_channels_override_send(self.m.target_system, self.m.target_component, *ch)

    def set_armed(self, armed: bool) -> None:
        if not self.connected:
            return
        mav = self.mavutil.mavlink
        # 21196 forces arming/disarming without the pre-arm checks meant for aircraft
        self.m.mav.command_long_send(self.m.target_system, self.m.target_component, mav.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1 if armed else 0, 21196, 0, 0, 0, 0, 0)

    def attitude(self) -> tuple[float, float, float] | None:
        with self._lock:
            return self._att

    def voltage(self) -> float | None:
        return self._volt

    def close(self) -> None:
        self.send([0, 0, 0, 0, 0], 0.4, 0, 0)
        self.set_armed(False)
        self._stop = True


# ---------------------------------------------------------------- mock (PC without hardware)

class MockController:
    """Stands in for the H743: integrates the wheel commands into a yaw and makes up a small tilt."""

    def __init__(self, cfg: dict[str, Any], track: float, max_v: float) -> None:
        self.connected = True
        self.armed = False
        self.track = track
        self.max_v = max_v
        self.yaw = 0.0
        self.pitch = 0.0
        self.last = time.monotonic()
        self.prev_v = 0.0

    def send(self, joints: list[float], gripper: float, left: float, right: float) -> None:
        now = time.monotonic()
        dt, self.last = now - self.last, now
        if not self.armed:
            left = right = 0.0
        vl, vr = left * self.max_v, right * self.max_v
        self.yaw = math.atan2(math.sin(self.yaw + (vr - vl) / self.track * dt), math.cos(self.yaw + (vr - vl) / self.track * dt))
        v = (vl + vr) / 2
        accel = (v - self.prev_v) / max(dt, 1e-3)
        self.prev_v = v
        self.pitch = 0.8 * self.pitch + 0.2 * clamp(-accel * 0.05, -0.08, 0.08)

    def set_armed(self, armed: bool) -> None:
        self.armed = armed

    def attitude(self) -> tuple[float, float, float] | None:
        return (random.gauss(0, 0.004), self.pitch + random.gauss(0, 0.004), self.yaw)

    def voltage(self) -> float | None:
        return 11.7

    def close(self) -> None:
        pass


# ---------------------------------------------------------------- arm and drive

class Arm:
    """Joint targets in degrees (0 = arm straight up), moved at a limited speed by update()."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.jmin = cfg["joint_min"]
        self.jmax = cfg["joint_max"]
        self.joints = [0.0] * 5
        self.target = [0.0] * 5
        self.gripper = 0.4
        self.gripper_target = 0.4
        self.speed = float(cfg.get("speed_dps", 90))

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
        for i in range(5):
            d = self.target[i] - self.joints[i]
            self.joints[i] = self.target[i] if abs(d) <= step else self.joints[i] + math.copysign(step, d)
        gd = self.gripper_target - self.gripper
        self.gripper = self.gripper_target if abs(gd) <= 2 * dt else self.gripper + math.copysign(2 * dt, gd)


class Drive:
    """Differential drive: set(v, w) in m/s and rad/s -> wheel duties -1..1 (sent to the H743)."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.v = 0.0
        self.w = 0.0
        self.left = 0.0
        self.right = 0.0
        self.max_v = float(cfg["max_wheel_speed"])

    def set(self, v: float, w: float) -> None:
        half = self.cfg["track"] / 2
        vl, vr = v - w * half, v + w * half
        peak = max(abs(vl), abs(vr), 1e-9)
        if peak > self.max_v:  # scale both wheels so the curve is kept
            vl, vr = vl * self.max_v / peak, vr * self.max_v / peak
        self.v, self.w = (vl + vr) / 2, (vr - vl) / (2 * half)
        self.left = clamp(vl / self.max_v, -1, 1) * (-1 if self.cfg.get("invert_left") else 1)
        self.right = clamp(vr / self.max_v, -1, 1) * (-1 if self.cfg.get("invert_right") else 1)

    def stop(self) -> None:
        self.set(0.0, 0.0)
