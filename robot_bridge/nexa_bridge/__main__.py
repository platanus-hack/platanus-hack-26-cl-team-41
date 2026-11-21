"""Entry point: python -m nexa_bridge [--mock] [--config config.toml]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from . import config as config_mod
from .hardware import Arm, Drive
from .robot import Robot
from .server import Bridge
from .vision import CameraVision, FakeVision, MjpegServer, Vision


def main() -> None:
    ap = argparse.ArgumentParser(prog="nexa_bridge", description="Bridge between the Nexa web console and the robot.")
    ap.add_argument("--config", help="path to config.toml (default: the one next to the package)")
    ap.add_argument("--mock", action="store_true", help="no hardware: fake servos, motors and camera (for a PC)")
    ap.add_argument("--port", type=int, help="override the WebSocket port")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger("nexa")
    cfg = config_mod.load(args.config)
    if args.port:
        cfg["server"]["port"] = args.port

    arm = Arm(cfg["arm"], mock=args.mock)
    drive = Drive(cfg["drive"], mock=args.mock)
    bridge = Bridge(cfg)
    holder: dict[str, Robot] = {}

    vision: Vision
    if args.mock:
        vision = FakeVision(cfg, lambda: (holder["r"].odom.x, holder["r"].odom.y, holder["r"].odom.th))
    elif cfg["camera"].get("enabled", True):
        vision = CameraVision(cfg)
    else:
        vision = Vision(cfg)

    robot = Robot(cfg, arm, drive, vision, bridge.emit)
    holder["r"] = robot
    try:
        vision.start()
        if isinstance(vision, CameraVision):
            MjpegServer(vision, int(cfg["camera"].get("mjpeg_port", 8080))).start()
    except Exception as e:  # camera or model problems must not stop the robot from driving
        log.error("Vision disabled: %s", e)

    async def run() -> None:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:  # Windows
                pass
        task = asyncio.create_task(bridge.run(robot))
        await asyncio.wait([task, asyncio.create_task(stop.wait())], return_when=asyncio.FIRST_COMPLETED)
        task.cancel()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Stopping: motors off")
        drive.close()
        vision.stop()


if __name__ == "__main__":
    main()
