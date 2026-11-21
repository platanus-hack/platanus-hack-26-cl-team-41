"""The three autonomous modes, written with the primitives in robot.py.

ordenar   – sweep the zone (odometry), approach detected objects with the camera, pick, carry to the drop point.
asistente – keep a person in view at the follow distance; fetch tools from the station and receive materials.
saludo    – look for people, approach, wave and greet; the console's camera can also trigger a greeting.
"""

from __future__ import annotations

import math
import time

from .robot import Robot


async def pick(r: Robot, label: str) -> None:
    r.set("Agarrando", f"Tomando {label}")
    await r.arm_to("recoger", 1.0)
    await r.arm_to("recoger", 0.05)
    r.carrying = label
    remove = getattr(r.vision, "remove_nearest", None)
    if remove:
        remove(label)
    await r.arm_to("transportar")


async def release(r: Robot, pose: str = "recoger") -> str | None:
    await r.arm_to(pose)
    await r.arm_to(pose, 1.0)
    item, r.carrying = r.carrying, None
    return item


async def ordenar(r: Robot) -> None:
    cfg = r.mission["ordenar"]
    z, drop, classes = cfg["zone"], cfg["drop"], set(cfg["classes"])
    r.event("info", "Modo ordenar zona: inicio de barrido.")
    await r.arm_to("plegado", 0.4)

    pts: list[tuple[float, float]] = []
    y, row, m = z["y0"] + 0.2, 0, 0.2
    while y <= z["y1"] - m + 1e-6:
        xs = [z["x0"] + m, z["x1"] - m]
        if row % 2:
            xs.reverse()
        pts += [(xs[0], y), (xs[1], y)]
        y += 0.4
        row += 1

    def in_zone() -> bool:
        return z["x0"] - 0.3 <= r.odom.x <= z["x1"] + 0.3 and z["y0"] - 0.3 <= r.odom.y <= z["y1"] + 0.3

    def target():
        return r.vision.best(classes) if in_zone() else None

    i, misses = 0, 0
    while i < len(pts):
        r.set("Patrullando", f"Barrido {round(100 * i / len(pts))} % de la zona")
        hit = await r.goto(*pts[i], until=target if misses < 2 else None)
        if not hit:
            i, misses = i + 1, 0
            continue
        r.set("Objeto detectado", f"{hit.cls} ({hit.confidence:.0%})")
        r.event("info", f"Detecté: {hit.cls}.")
        r.set("Aproximando", f"Acercándome a {hit.cls}")
        got = await r.approach({hit.cls}, r.b["pick_bbox_h"])
        if not got or got.h < r.b["pick_bbox_h"]:
            misses += 1  # after two misses on this leg, finish it without stopping for detections
            r.event("warn", f"Perdí de vista {hit.cls}, sigo el barrido.")
            continue
        misses = 0
        await pick(r, got.cls)
        r.set("Transportando", f"Llevando {got.cls} al punto de entrega")
        await r.goto(drop["x"], drop["y"], tol=0.3)
        await r.face(drop["x"], drop["y"])
        r.set("Depositando", f"Dejando {got.cls}")
        await release(r)
        r.stats["collected"] += 1
        r.event("ok", f"{got.cls} guardado en el punto de entrega.")
        await r.arm_to("plegado", 0.4)
    r.set("Completado", "Zona ordenada")
    r.event("ok", "¡Zona ordenada!")
    await r.arm_to("home", 0.4)


async def asistente(r: Robot) -> None:
    r.event("info", "Modo asistente: te sigo y atiendo pedidos.")
    await r.arm_to("plegado", 0.4)
    person = {"persona"}

    async def come_to_person(distance: float) -> bool:
        if not r.vision.best(person) and not await r.search(person, timeout=10):
            r.event("warn", "No te encuentro: ponte frente a la cámara.")
            return False
        return bool(await r.approach(person, r.person_h(distance)))

    async def wait_confirm() -> None:
        r.confirm.clear()
        end = time.monotonic() + r.b["confirm_timeout"]
        while not r.confirm.is_set() and time.monotonic() < end:
            await r.tick()

    while True:
        if r.requests.empty():
            d = r.vision.best(person)
            follow = r.mission["asistente"]["followDistance"]
            if d is None:
                r.set("Acompañando", "Buscándote")
                await r.search(person, timeout=3)
            elif d.h < r.person_h(follow + 0.15) or abs(d.cx - 0.5) > 0.12:
                r.set("Acompañando", "Voy contigo")
                await r.approach(person, r.person_h(follow), timeout=1.0)
            else:
                r.stop()
                r.set("Acompañando", "A tu lado")
                await r.tick()
            continue

        req = r.requests.get_nowait()
        home = (r.odom.x, r.odom.y)
        item = req.get("item", "material")
        if req.get("action") == "entregar":
            ts = r.b["tool_station"]
            r.set("Buscando herramienta", f"Voy por: {item}")
            await r.goto(ts[0], ts[1], tol=0.3)
            await r.face(ts[0], ts[1])
            await pick(r, item)
            r.set("Llevando", f"Te llevo: {item}")
            await r.goto(*home, tol=0.15)
            await come_to_person(r.b["deliver_distance"])
            await r.arm_to("entregar")
            r.set("Entregando", f"Toma {item} y confirma")
            r.event("info", f"Aquí tienes: {item}.", f"Aquí tienes {item}")
            await wait_confirm()
            await release(r, "entregar")
            r.stats["delivered"] += 1
            r.event("ok", f"Entregado: {item}.")
        else:
            r.set("Recibiendo", "Voy a recibir el material")
            await come_to_person(r.b["deliver_distance"])
            await r.arm_to("entregar", 1.0)
            r.set("Esperando material", f"Pon «{item}» en la pinza y confirma")
            r.event("info", f"Listo para recibir: {item}.", "Pon el material en mi pinza")
            await wait_confirm()
            await r.arm_to("entregar", 0.1)
            r.carrying = item
            await r.arm_to("transportar")
            mb = r.b["material_bin"]
            r.set("Guardando", f"Llevando {item} al contenedor")
            await r.goto(mb[0], mb[1], tol=0.3)
            await r.face(mb[0], mb[1])
            await release(r)
            r.stats["received"] += 1
            r.event("ok", f"{item} guardado en el contenedor.")
            await r.goto(*home, tol=0.15)
        await r.arm_to("plegado", 0.4)


async def wave(r: Robot) -> None:
    base = r.arm.joints[0]
    for _ in range(3):
        await r.arm_to([base, 10, 60, -20, 35], 1.0)
        await r.arm_to([base, 10, 75, -35, -35], 1.0)
    await r.arm_to("plegado", 0.4)


async def saludo(r: Robot) -> None:
    r.event("info", "Modo saludo: buscando personas.")
    await r.arm_to("plegado", 0.4)
    person = {"persona"}
    quiet_until = 0.0
    seen_camera = r.person_seen_at
    w, h = 4.0, 3.0
    while True:
        greeting = r.mission["saludo"]["greeting"]
        if r.person_seen_at != seen_camera:
            seen_camera = r.person_seen_at
            r.set("Saludando", "Persona vista por la cámara de la consola")
            r.event("ok", "¡Hola! (persona detectada por la cámara)", greeting)
            r.stats["greeted"] += 1
            await wave(r)
            continue
        if time.monotonic() > quiet_until and r.vision.best(person):
            r.set("Acercándome", "Vi a una persona")
            got = await r.approach(person, r.person_h(r.b["greet_distance"]))
            if got:
                r.set("Saludando", "¡Hola!")
                r.event("ok", "Saludé a una persona.", greeting)
                r.stats["greeted"] += 1
                await wave(r)
                quiet_until = time.monotonic() + min(r.mission["saludo"]["cooldownS"], 15)
                # turn away so the same person is not greeted again right away
                await r.goto(r.odom.x - 0.3 * math.cos(r.odom.th), r.odom.y - 0.3 * math.sin(r.odom.th), tol=0.1, timeout=4)
            continue
        r.set("Buscando personas", "Recorriendo el área")
        gx = 0.4 + (time.monotonic() * 0.37 % 1) * (w - 0.8)
        gy = 0.4 + (time.monotonic() * 0.61 % 1) * (h - 0.8)
        await r.goto(gx, gy, tol=0.15, timeout=8,
                     until=lambda: (time.monotonic() > quiet_until and r.vision.best(person)) or r.person_seen_at != seen_camera)
        if not r.vision.best(person):
            await r.search(person, timeout=4)


BEHAVIOURS = {"ordenar": ordenar, "asistente": asistente, "saludo": saludo}
