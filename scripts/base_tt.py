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
MT, MH = 18.8, 22.5                    # TT gearbox thickness (along the shaft) and height
MY_IN = MY_OUT - MT                    # 66.2
MZ0 = AXZ - MH / 2                     # 21.25
ARMX = -25.0                           # arm axis, set back for stability

def plate():
    P = "Base plate"
    box("Plate", P, [0, 0, ZB + T / 2], [LX, LY, T], new=True)
    cmd("solid.fillet", edges=[[sx * LX / 2, sy * LY / 2, ZB + T / 2] for sx in (1, -1) for sy in (1, -1)],
        radius=15, body=P, name="Plate corners")
    for sy in (1, -1):
        s = "L" if sy > 0 else "R"
        # motor wall (inner side) and front stop; motor body runs from x=+11.5 back to x=-58.5
        box(f"Motor wall {s}", P, [-17.75, sy * (MY_IN - 2), (MZ0 + ZB) / 2], [59.5, 4, ZB - MZ0])
        box(f"Motor front stop {s}", P, [14, sy * (MY_IN + MT / 2), (MZ0 + 4 + ZB) / 2], [4, MT, ZB - MZ0 - 4])
        # stiffening rib along the plate, continuing the wall
        box(f"Rib front {s}", P, [(12 + 85) / 2 + 4, sy * (MY_IN - 2), ZB - 3], [85 - 16, 4, 6])
        box(f"Rib rear {s}", P, [(-50 - 85) / 2, sy * (MY_IN - 2), ZB - 3], [35, 4, 6])
        # zip-tie slots just inside the wall
        for i, x in enumerate([-38, -54]):
            box(f"Tie slot {s}{i+1}", P, [x, sy * (MY_IN - 6), ZB + 1.5], [5, 3, 6], op="cut")
        cyl(f"Motor wire hole {s}", P, [-48, sy * (MY_IN - 14), ZB - 1], 10, 5, op="cut")
    # skids front and rear: post with a rounded tip 1 mm above the floor
    for sx, nm in ((1, "front"), (-1, "rear")):
        cyl(f"Skid {nm}", P, [sx * 80, 0, 1], 16, ZB - 1 + 0.01)
        cmd("solid.fillet", edges=[[sx * 80 + 8, 0, 1]], radius=7.5, body=P, name=f"Skid {nm} tip")
    # L298N standoffs (37 x 37 hole square), front
    for i, (dx, dy) in enumerate([(18.5, 18.5), (-18.5, 18.5), (18.5, -18.5), (-18.5, -18.5)]):
        cyl(f"L298N standoff {i+1}", P, [48 + dx, dy, ZB - 6], 6.5, 6.01)
        cyl(f"L298N pilot {i+1}", P, [48 + dx, dy, ZB - 7], 2.6, 8, op="cut")
    # battery strap slots (front, under the plate)
    for i, x in enumerate([-60, -20]):
        for sy in (1, -1):
            box(f"Strap slot {i+1}{'L' if sy > 0 else 'R'}", P, [x, sy * 32, ZB + 1.5], [22, 3, 6], op="cut")
    # arm: 4 x M4 on D150 at 45 deg, centre cable hole
    for i, (x, y) in enumerate([(53.03, 53.03), (-53.03, 53.03), (-53.03, -53.03), (53.03, -53.03)]):
        cyl(f"Arm bolt {i+1}", P, [ARMX + x, y, ZB - 1], 4.5, 5, op="cut")
    cyl("Arm cable hole", P, [ARMX, 0, ZB - 1], 24, 5, op="cut")
    # controller mounting holes (2 rows, 20 mm pitch) under the arm base, rear-left/right
    for i, (x, y) in enumerate([(-20, 40), (0, 40), (20, 40), (-20, -40), (0, -40), (20, -40)]):
        cyl(f"Mount hole {i+1}", P, [x, y, ZB - 1], 3.2, 5, op="cut")

def dummies():
    for sy in (1, -1):
        s = "L" if sy > 0 else "R"
        yc = sy * (MY_IN + MT / 2)
        box(f"TT gearbox {s}", f"TT motor {s}", [(11.5 - 48) / 2, yc, AXZ], [59.5, MT, MH], new=True)
        cyl(f"TT can {s}", f"TT motor {s}", [-48, yc, AXZ], 20, 10.5, axis=[-1, 0, 0])
        cyl(f"TT shaft {s}", f"TT motor {s}", [0, sy * MY_OUT, AXZ], 5.4, 9, axis=[0, sy, 0])
        cyl(f"Wheel {s}", f"Wheel {s}", [0, sy * (MY_OUT + 2), AXZ], 65, 26, axis=[0, sy, 0], new=True)
    box("L298N board", "L298N", [48, 0, ZB - 6 - 0.8], [43, 43, 1.6], new=True)
    box("L298N heatsink", "L298N", [48, 12, ZB - 7.6 - 12.5], [23, 16, 25])
    box("Battery 3S", "Battery", [-37, 0, ZB - 12.5], [70, 50, 25], new=True)

stage = sys.argv[1]
pre = []
if stage == "plate":
    pre = [{"tool": "new_design"}]
    plate()
elif stage == "dummies":
    dummies()
print(json.dumps(pre + [{"tool": "batch", "args": {"commands": S, "verbose": False}},
                        {"tool": "measure", "args": {"summary": True}}]))
