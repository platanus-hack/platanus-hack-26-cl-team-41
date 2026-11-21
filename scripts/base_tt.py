"""Fast-print mobile base: one plate, 2 yellow TT gear motors (1:48), L298N, two skids, arm on top.
World: X forward, Y left, Z up, floor z=0. TT wheels D65 -> axle z=32.5. Everything hangs under the plate
(z 44.5..47.5) so the plate prints upside down without supports.
usage: python gen4.py <stage>
"""
import json, sys

S = []
def cmd(c, **p): S.append({"command": c, "params": p})
def box(name, body, c, size, op="join", new=False):
    p = {"length": size[0], "width": size[1], "height": size[2], "center": list(c), "name": name}
    if new: p.update(body_name=body, operation="new")
    else: p.update(operation=op, targets=[body])
    S.append({"command": "solid.box", "params": p})
def cyl(name, body, base, d, h, axis="Z", op="join", new=False):
    p = {"diameter": d, "height": h, "base": list(base), "axis": axis, "name": name}
    if new: p.update(body_name=body, operation="new")
    else: p.update(operation=op, targets=[body])
    S.append({"command": "solid.cylinder", "params": p})

LX, LY, T = 178.0, 170.0, 3.0          # plate
ZB = 44.5                              # plate underside
AXZ = 32.5                             # wheel axle height (D65 wheels)
MY_OUT = LY / 2                        # motor outer face flush with the plate edge
MT, MH = 18.6, 22.44                   # TT gearbox thickness (along the shaft) and height (Adafruit 3777 drawing)
MY_IN = MY_OUT - MT                    # 66.4  motor inner face
WY = MY_IN                             # 66.4  wall face, the motor sits flush on it
NUB_X = -11.25                         # locating nub (D4 x 1.9) on the motor face -> window in the wall
WX0, WX1 = -28.0, 19.0                 # wall only where the motor is screwed
HOLE_X, HOLE_DZ = -22.55, 8.8          # stacked M3 holes: 22.55 mm behind the shaft, 17.6 mm apart
TAB_X = 14.0                           # front ear hole, 14 mm ahead of the shaft
MZ0 = AXZ - MH / 2                     # 21.25
ARMX = 0.0                             # arm axis centred on the plate
BALLX = 73.0                           # caster posts

def plate():
    P = "Base plate"
    cmd("parameters.add", name="bola", expression="16 mm")
    box("Plate", P, [0, 0, ZB + T / 2], [LX, LY, T], new=True)
    cmd("solid.fillet", edges=[[sx * LX / 2, sy * LY / 2, ZB + T / 2] for sx in (1, -1) for sy in (1, -1)],
        radius=15, body=P, name="Plate corners")
    for sy in (1, -1):
        s = "L" if sy > 0 else "R"
        ys = [0, sy, 0]
        # motor wall, only along the screwed part of the gearbox; motor face sits flush on it
        box(f"Motor wall {s}", P, [(WX0 + WX1) / 2, sy * (WY - 2), (18 + ZB) / 2], [WX1 - WX0, 4, ZB - 18])
        # screw holes (M3 through wall + gearbox, nut outside), ear slot, shaft stub and nub windows
        for k, dz in enumerate((-HOLE_DZ, HOLE_DZ)):
            cyl(f"Motor screw hole {s}{k+1}", P, [HOLE_X, sy * (WY - 6), AXZ + dz], 3.4, 10, axis=ys, op="cut")
        box(f"Motor ear slot {s}", P, [TAB_X, sy * (WY - 1), AXZ], [3.4, 10, 16], op="cut")
        cyl(f"Shaft stub hole {s}", P, [0, sy * (WY - 6), AXZ], 10, 10, axis=ys, op="cut")
        box(f"Nub window {s}", P, [NUB_X, sy * (WY - 1), AXZ], [6, 10, 14], op="cut")
    # ball casters front and rear: post with a spherical socket that wraps the ball past its equator,
    # 4 slits make flexible fingers so the ball snaps in. Ball bottom 0.5 mm above the floor.
    for sx, nm in ((1, "front"), (-1, "rear")):
        x = sx * BALLX
        cyl(f"Caster post {nm}", P, [x, 0, "0.5 mm + 0.3*bola"], "bola + 8 mm", "44.01 mm - 0.3*bola")
        S.append({"command": "solid.sphere", "params": {"diameter": "bola + 0.4 mm", "center": [x, 0, "0.5 mm + bola/2"],
                  "operation": "cut", "targets": [P], "name": f"Ball socket {nm}"}})
        box(f"Socket slit X {nm}", P, [x, 0, "0.5 mm + 0.475*bola"], ["bola + 10 mm", 1.6, "0.35*bola"], op="cut")
        box(f"Socket slit Y {nm}", P, [x, 0, "0.5 mm + 0.475*bola"], [1.6, "bola + 10 mm", "0.35*bola"], op="cut")
    # L298N standoffs (37 x 37 hole square), front
    for i, (dx, dy) in enumerate([(18.5, 18.5), (-18.5, 18.5), (18.5, -18.5), (-18.5, -18.5)]):
        cyl(f"L298N standoff {i+1}", P, [38 + dx, dy, ZB - 6], 6.5, 6.01)
        cyl(f"L298N pilot {i+1}", P, [38 + dx, dy, ZB - 7], 2.6, 8, op="cut")
    # battery strap slots (front, under the plate)
    for sy in (1, -1):
        box(f"Strap slot {'L' if sy > 0 else 'R'}", P, [-32, sy * 37.5, ZB + 1.5], [22, 3, 6], op="cut")
    # arm: 4 x M4 on D150 at 45 deg, centre cable hole
    for i, (x, y) in enumerate([(53.03, 53.03), (-53.03, 53.03), (-53.03, -53.03), (53.03, -53.03)]):
        cyl(f"Arm bolt {i+1}", P, [ARMX + x, y, ZB - 1], 4.5, 5, op="cut")
    cyl("Arm cable hole", P, [6, 0, ZB - 1], 24, 5, op="cut")

def dummies():
    for sy in (1, -1):
        s = "L" if sy > 0 else "R"
        yc = sy * (MY_IN + MT / 2)
        box(f"TT gearbox {s}", f"TT motor {s}", [-7.5, yc, AXZ], [37, MT, MH], new=True)
        box(f"TT motor can {s}", f"TT motor {s}", [-40.1, yc, AXZ], [28.2, 18.6, 20.38])
        box(f"TT ear {s}", f"TT motor {s}", [13.4, sy * (MY_IN + 1.5), AXZ], [4.8, 3, 8])
        cyl(f"TT nub {s}", f"TT motor {s}", [NUB_X, sy * MY_IN, AXZ], 4, 1.9, axis=[0, -sy, 0])
        cyl(f"TT shaft in {s}", f"TT motor {s}", [0, sy * MY_IN, AXZ], 5.4, 8.7, axis=[0, -sy, 0])
        cyl(f"TT shaft {s}", f"TT motor {s}", [0, sy * MY_OUT, AXZ], 5.4, 9, axis=[0, sy, 0])
        cyl(f"Wheel {s}", f"Wheel {s}", [0, sy * (MY_OUT + 2), AXZ], 65, 26, axis=[0, sy, 0], new=True)
    box("L298N board", "L298N", [38, 0, ZB - 6 - 0.8], [43, 43, 1.6], new=True)
    box("L298N heatsink", "L298N", [38, 12, ZB - 7.6 - 12.5], [23, 16, 25])
    box("Battery 3S", "Battery", [-32, 0, ZB - 12.5], [50, 70, 25], new=True)
    for sx, nm in ((1, "front"), (-1, "rear")):
        S.append({"command": "solid.sphere", "params": {"diameter": "bola", "center": [sx * BALLX, 0, "0.5 mm + bola/2"],
                  "body_name": f"Ball {nm}", "name": f"Ball {nm}"}})

stage = sys.argv[1]
pre = []
if stage == "plate":
    pre = [{"tool": "new_design"}]
    plate()
elif stage == "coves":
    import math
    P = "Base plate"
    def cove(r, n=10):
        """quarter-round cove profile in (u, v): corner at (0,0), u away from the wall, v down from the plate"""
        pts = [(0, -r)] + [(r - r * math.cos(t), -r + r * math.sin(t)) for t in
               [math.pi / 2 * i / n for i in range(1, n)]] + [(r, 0), (0, 0)]
        return pts
    def along_x(name, yf, d, r, x0, x1):
        # sketch on YZ (sketch x=+Y, y=+Z) at X=x0, extrude +X
        pts = [(yf + d * u, ZB + v) for u, v in cove(r)]
        S.append({"command": "sketch.create", "params": {"plane": "YZ", "offset": x0, "name": name + " sk"}})
        S.append({"command": "sketch.line", "params": {"points": [[round(a, 4), round(b, 4)] for a, b in pts], "closed": True}})
        S.append({"command": "sketch.finish", "params": {}})
        S.append({"command": "solid.extrude", "params": {"sketch": name + " sk", "distance": x1 - x0, "operation": "join",
                  "targets": [P], "name": name}})
    def along_y(name, xf, d, r, y0, y1):
        # sketch on XZ (sketch x=+X, y=-Z) at Y=y0, extrude +Y
        pts = [(xf + d * u, ZB + v) for u, v in cove(r)]
        S.append({"command": "sketch.create", "params": {"plane": "XZ", "offset": y0, "name": name + " sk"}})
        S.append({"command": "sketch.line", "params": {"points": [[round(a, 4), round(-b, 4)] for a, b in pts], "closed": True}})
        S.append({"command": "sketch.finish", "params": {}})
        S.append({"command": "solid.extrude", "params": {"sketch": name + " sk", "distance": y1 - y0, "operation": "join",
                  "targets": [P], "name": name}})
    for sy in (1, -1):
        sd = "L" if sy > 0 else "R"
        along_x(f"Cove wall inner {sd}", sy * (WY - 4), -sy, 3, WX0, WX1)
        y0 = min(sy * (WY - 4), sy * WY)
        along_y(f"Cove wall front {sd}", WX1, 1, 3, y0, y0 + 4)
        along_y(f"Cove wall rear {sd}", WX0, -1, 3, y0, y0 + 4)
    for sx, nm in ((1, "front"), (-1, "rear")):
        R = 12.0; r = 3.0
        pts = [(sx * BALLX + R + u, ZB + v) for u, v in cove(r)]
        S.append({"command": "sketch.create", "params": {"plane": "XZ", "name": f"Cove post {nm} sk"}})
        S.append({"command": "sketch.line", "params": {"points": [[round(a, 4), round(-b, 4)] for a, b in pts], "closed": True}})
        S.append({"command": "sketch.finish", "params": {}})
        S.append({"command": "solid.revolve", "params": {"sketch": f"Cove post {nm} sk",
                  "axis": {"origin": [sx * BALLX, 0, 0], "dir": [0, 0, 1]}, "operation": "join", "targets": [P],
                  "name": f"Cove post {nm}"}})
elif stage == "gussets":
    P = "Base plate"
    for sy in (1, -1):
        sd = "L" if sy > 0 else "R"
        yf = sy * (WY - 4)                     # wall inner face
        tri = [(yf, ZB), (yf, 22.0), (yf - sy * 15.0, ZB)]
        for k, xc in enumerate((-16.5, 8.5)):
            nm = f"Gusset {sd}{k+1}"
            S.append({"command": "sketch.create", "params": {"plane": "YZ", "offset": xc - 2, "name": nm + " sk"}})
            S.append({"command": "sketch.line", "params": {"points": [[round(a, 4), round(b, 4)] for a, b in tri], "closed": True}})
            S.append({"command": "sketch.finish", "params": {}})
            S.append({"command": "solid.extrude", "params": {"sketch": nm + " sk", "distance": 4, "operation": "join",
                      "targets": [P], "name": nm}})
elif stage.startswith("fillet"):
    P = "Base plate"
    picks = {
      "fillet_in":   ([[sy * 0 - 15, sy * (WY - 4), ZB] for sy in (1, -1)], 3),
      "fillet_rf":   ([[52.5, sy * (WY - 4), ZB] for sy in (1, -1)] + [[52.5, sy * WY, ZB] for sy in (1, -1)], 3),
      "fillet_rr":   ([[-67.5, sy * (WY - 4), ZB] for sy in (1, -1)] + [[-67.5, sy * WY, ZB] for sy in (1, -1)], 3),
      "fillet_out":  ([[-38, sy * WY, ZB] for sy in (1, -1)] + [[-3, sy * WY, ZB] for sy in (1, -1)], 1.5),
      "fillet_post": ([[sx * BALLX, 12, ZB] for sx in (1, -1)], 4),
      "fillet_so":   ([[38 + dx, dy + 3.25, ZB] for dx in (18.5, -18.5) for dy in (18.5, -18.5)], 1.5),
    }[stage]
    S.append({"command": "solid.fillet", "params": {"edges": picks[0], "radius": picks[1], "body": P,
              "name": "Root " + stage.split("_")[1]}})
elif stage == "tray":
    # Electronics tray: a disc clamped between the plate and the arm's base flange by the same 4 M4 bolts,
    # so the plate keeps printing upside down in one piece. It carries the Matek H743 (close to the arm
    # axis, for its IMU) and the Radxa Zero 3W, both inside the arm's hollow base. Printed flat, standoffs up.
    TR = "Bandeja electronica"
    TT_ = 2.4
    z0 = ZB + T                                    # plate top, 47.5
    FC = (38.0, 0.0); FC_DX = FC_DY = 30.5         # H743 hole pattern: MEASURE your board and change these
    RX = (-36.0, 0.0)                              # Radxa Zero 3W, long side along Y, Pi Zero pattern 58 x 23 (M2.5)
    cyl("Tray disc", TR, [ARMX, 0, z0], 160, TT_, new=True)
    for i, (x, y) in enumerate([(53.03, 53.03), (-53.03, 53.03), (-53.03, -53.03), (53.03, -53.03)]):
        cyl(f"Tray arm bolt {i+1}", TR, [ARMX + x, y, z0 - 1], 4.5, TT_ + 2, op="cut")
    cyl("Tray cable hole", TR, [6, 0, z0 - 1], 24, TT_ + 2, op="cut")
    for sy in (1, -1):
        box(f"Tray window {'L' if sy > 0 else 'R'}", TR, [ARMX, sy * 45, z0 + TT_ / 2], [50, 18, TT_ + 2], op="cut")
    for i, (dx, dy) in enumerate([(1, 1), (-1, 1), (1, -1), (-1, -1)]):
        x, y = FC[0] + dx * FC_DX / 2, FC[1] + dy * FC_DY / 2
        cyl(f"FC standoff {i+1}", TR, [x, y, z0 + TT_ - 0.01], 6.5, 5.01)
        cyl(f"FC pilot {i+1}", TR, [x, y, z0 + 0.8], 2.6, 7, op="cut")
    for i, (dx, dy) in enumerate([(1, 1), (-1, 1), (1, -1), (-1, -1)]):
        x, y = RX[0] + dx * 23 / 2, RX[1] + dy * 58 / 2
        cyl(f"Radxa standoff {i+1}", TR, [x, y, z0 + TT_ - 0.01], 5.5, 4.01)
        cyl(f"Radxa pilot {i+1}", TR, [x, y, z0 + 0.8], 2.2, 6, op="cut")
    # reference boards (for collision checks)
    box("H743 board", "Matek H743", [FC[0], FC[1], z0 + TT_ + 5 + 0.8], [36, 36, 1.6], new=True)
    box("H743 parts", "Matek H743", [FC[0], FC[1], z0 + TT_ + 5 + 1.6 + 3], [30, 30, 6])
    box("Radxa board", "Radxa Zero 3W", [RX[0], RX[1], z0 + TT_ + 4 + 0.8], [30, 65, 1.6], new=True)
    box("Radxa parts", "Radxa Zero 3W", [RX[0], RX[1], z0 + TT_ + 4 + 1.6 + 1.5], [24, 55, 3])
elif stage == "dummies":
    dummies()
print(json.dumps(pre + [{"tool": "batch", "args": {"commands": S, "verbose": False}},
                        {"tool": "measure", "args": {"summary": True}}]))
