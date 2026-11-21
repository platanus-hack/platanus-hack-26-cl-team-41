"""Entry point: python -m nexa_bridge [--mock] [--config config.toml]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from . import config as config_mod
from .hardware import Arm, Controller, Drive, MockController
from .robot import Robot
from .server import Bridge
from .vision import ExternalVision, FakeVision, Vision


def main() -> None:
    ap = argparse.ArgumentParser(prog="nexa_bridge", description="Bridge between the Nexa web console and the robot (Matek H743 over MAVLink).")
    ap.add_argument("--config", help="path to config.toml (default: the one next to the package)")
    ap.add_argument("--mock", action="store_true", help="no hardware: simulated H743 and a fake camera world (for a PC)")
    ap.add_argument("--vision", choices=["fake", "external"], default=None,
                    help="with --mock: 'fake' (default) simulates the camera, 'external' waits for the PC vision client")
    ap.add_argument("--port", type=int, help="override the WebSocket port")
    ap.add_argument("--device", help="override the MAVLink serial device (e.g. /dev/ttyS5)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger("nexa")
    cfg = config_mod.load(args.config)
    if args.port:
        cfg["server"]["port"] = args.port
    if args.device:
        cfg["mavlink"]["device"] = args.device

    arm = Arm(cfg["arm"])
    drive = Drive(cfg["drive"])
    bridge = Bridge(cfg)
    holder: dict[str, Robot] = {}

    fc: Controller
    vision: Vision
    if args.mock:
        fc = MockController(cfg, track=float(cfg["drive"]["track"]), max_v=float(cfg["drive"]["max_wheel_speed"]))
        if args.vision == "external":
            vision = ExternalVision(cfg)
        else:
            vision = FakeVision(cfg, lambda: (holder["r"].odom.x, holder["r"].odom.y, holder["r"].odom.th))
    else:
        from .hardware import MavlinkController  # needs pymavlink, only on the robot

        fc = MavlinkController(cfg["mavlink"])
        vision = ExternalVision(cfg)

    robot = Robot(cfg, arm, drive, fc, vision, bridge.emit)
    holder["r"] = robot
    vision.start()

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
        log.info("Stopping: wheels stopped, H743 disarmed")
        drive.stop()
        fc.close()
        vision.stop()


if __name__ == "__main__":
    main()
