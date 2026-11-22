"""Compact enclosed robot arm (4x MG995, 2x SG90). usage: python gen2.py <stage>
World: Z up, home pose straight up, pitch axes along Y. Links are 48 mm stadium shells
(y -24..24, main body y -21..24 + lid y -24..-21); the upper arm and wrist are forks (cheeks y +-28..33).
"""
import json, sys

def e(base, off):
    if isinstance(base, (int, float)):
        return round(base + off, 4)
    if off == 0:
        return base
    return f"{base} + {off}" if off > 0 else f"{base} - {abs(off)}"

S = []
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

def fillet(name, body, pts, r, chain=True):
    S.append({"command": "solid.fillet", "params": {"edges": pts, "radius": r, "body": body,
              "name": name, "tangent_chain": chain}})

def mid(a, b):
    return f"({a} + {b}) / 2"

# numeric values of the parameters (for picks, which must be numbers)
V = dict(zS=112, L1=90, L2=85)
V["zE"] = V["zS"] + V["L1"]; V["zW"] = V["zE"] + V["L2"]

def stadium(tag, body, z0, z1, y0, y1, r, op="join", new=False, flat_bottom=None):
    """Rounded-end slab along Z between axes z0 and z1 (semicircles of radius r), y from y0 to y1.
    flat_bottom: a z expression where the slab starts flat instead of the z0 semicircle."""
    w = y1 - y0
    if flat_bottom is not None:
        box(f"{tag} body", body, [0, (y0 + y1) / 2, mid(flat_bottom, z1)], [2 * r, w, f"{z1} - ({flat_bottom})"], op=op, new=new)
    else:
        box(f"{tag} body", body, [0, (y0 + y1) / 2, mid(z0, z1)], [2 * r, w, f"{z1} - ({z0})"], op=op, new=new)
        cyl(f"{tag} end 1", body, [0, y0, z0], 2 * r, w, axis="Y", op=op)
    cyl(f"{tag} end 2", body, [0, y0, z1], 2 * r, w, axis="Y", op=op)

def servo_seat(tag, body, zc, d):
    """Ribs and pilot holes for an MG995 whose shaft (+Y, tip y=27.5) sits at zc and whose body runs
    along d*Z. Tabs y[11,13.5] are screwed from -Y into ribs y[13.5,21] joined to the +Y wall."""
    far = sorted([d * 30.9, d * 37.4]); near = sorted([d * -17.1, d * -10.6])
    box(f"{tag} rib far", body, [0, 17.25, e(zc, (far[0] + far[1]) / 2)], [24, 7.5, 6.5])
    box(f"{tag} rib near", body, [0, 17.25, e(zc, (near[0] + near[1]) / 2)], [24, 7.5, 6.5])
    k = 1
    for dz in (d * 34.9, d * -14.6):
        for dx in (-5, 5):
            cyl(f"{tag} rib hole {k}", body, [dx, 13, e(zc, dz)], 2.2, 8.5, axis="Y", op="cut"); k += 1
    cyl(f"{tag} shaft hole", body, [0, 20, zc], 14, 5, axis="Y", op="cut")

def lid_bosses(tag, body, pts):
    for i, (x, z) in enumerate(pts):
        cyl(f"{tag} boss {i+1}", body, [x, -21, z], 7, 42, axis="Y")
    for i, (x, z) in enumerate(pts):
        cyl(f"{tag} boss hole {i+1}", body, [x, -22, z], 2.2, 13, axis="Y", op="cut")

def lid(tag, body, z0, z1, pivots, screws, flat_bottom=None, cable=None):
    stadium(tag, body, z0, z1, -24, -21, 24, new=True, flat_bottom=flat_bottom)
    for i, z in enumerate(pivots):
        cyl(f"{tag} pivot boss {i+1}", body, [0, -21, z], 12, 4.5, axis="Y")
        cyl(f"{tag} pivot hole {i+1}", body, [0, -25, z], 5.2, 10, axis="Y", op="cut")
    for i, (x, z) in enumerate(screws):
        cyl(f"{tag} screw hole {i+1}", body, [x, -25, z], 2.8, 5, axis="Y", op="cut")
    if cable:
        cyl(f"{tag} cable hole", body, [0, -25, cable], 10, 5, axis="Y", op="cut")

def horn_holes(tag, body, zc, y=27):
    cyl(f"{tag} horn centre", body, [0, y, zc], 3.5, 7, axis="Y", op="cut")
    for i, (dx, dz) in enumerate([(8, 0), (-8, 0), (0, 8), (0, -8)]):
        cyl(f"{tag} horn hole {i+1}", body, [dx, y, e(zc, dz)], 2.2, 7, axis="Y", op="cut")

def cheek_b_pivot(tag, body, zc):
    cyl(f"{tag} pivot boss", body, [0, -28, zc], 12, 3.5, axis="Y")
    cyl(f"{tag} pivot hole", body, [0, -34, zc], 5.2, 11, axis="Y", op="cut")

# ---------- servo dummies ----------
def mg995_pitch(name, zc, d):
    box(f"{name} case", name, [0, 2.6, e(zc, d * 10.15)], [19.7, 36, 40.7], new=True)
    box(f"{name} tabs", name, [0, 12.25, e(zc, d * 10.15)], [19.7, 2.5, 54.5])
    cyl(f"{name} shaft", name, [0, 20.6, zc], 6, 6.9, axis="Y")

def mg995_base(name):
    box(f"{name} case", name, [10.15, 0, 40.5], [40.7, 19.7, 36], new=True)
    box(f"{name} tabs", name, [10.15, 0, 49.75], [54.5, 19.7, 2.5])
    cyl(f"{name} shaft", name, [0, 0, 58.5], 6, 6.9)

def sg90_roll(name, zb):
    box(f"{name} case", name, [5.4, 0, e(zb, 11.35)], [22.8, 12.2, 22.7], new=True)
    box(f"{name} tabs", name, [5.4, 0, e(zb, 16.95)], [32.2, 12.2, 2.5])
    cyl(f"{name} gear bump", name, [0, 0, e(zb, 22.7)], 11.8, 4)
    cyl(f"{name} shaft", name, [0, 0, e(zb, 26.7)], 4.8, 2.8)

def sg90_grip(name, gx, Gz):
    box(f"{name} case", name, [gx, -6.85, e(Gz, -5.4)], [12.2, 22.7, 22.8], new=True)
    box(f"{name} tabs", name, [gx, -1.25, e(Gz, -5.4)], [12.2, 2.5, 32.2])
    cyl(f"{name} gear bump", name, [gx, 4.5, Gz], 11.8, 4, axis="Y")
    cyl(f"{name} shaft", name, [gx, 8.5, Gz], 4.8, 2.8, axis="Y")

GX = 10.6
P = "zW + 62"      # palm bottom (roll SG90 shaft tip at zW + 61.5)
GZ = "zW + 89"     # gear axis (P + 27)

def jaw(side):
    body = f"Jaw{side}"; s = 1 if side == "R" else -1; cx = s * GX
    cyl(f"{body} hub", body, [cx, 12, GZ], 17.4, 5, axis="Y", new=True)
    if side == "R":
        box(f"{body} tooth root", body, [cx, 14.5, e(GZ, 9.45)], [2.3, 5, 2.1])
        box(f"{body} tooth tip", body, [cx, 14.5, e(GZ, 11.25)], [1.4, 5, 1.5])
    else:
        box(f"{body} tooth root", body, [cx + 9.45, 14.5, GZ], [2.1, 5, 2.3])
        box(f"{body} tooth tip", body, [cx + 11.25, 14.5, GZ], [1.5, 5, 1.4])
    S.append({"command": "solid.pattern.circular", "params": {
        "features": [f"{body} tooth root", f"{body} tooth tip"],
        "axis": {"origin": [cx, 0, GZ], "dir": [0, 1, 0]}, "count": 14, "name": f"{body} teeth"}})
    box(f"{body} finger", body, [cx, 14.5, e(GZ, 27.5)], [8, 5, 55])
    box(f"{body} pad", body, [cx - s * 5.8, 14.5, e(GZ, 46.5)], [3.6, 5, 17])
    if side == "R":
        cyl("JawR horn screw hole", body, [cx, 11, GZ], 2.2, 7, axis="Y", op="cut")
        cyl("JawR horn hub recess", body, [cx, 11, GZ], 7.5, 3, axis="Y", op="cut")
    else:
        cyl("JawL axle hole", body, [cx, 11, GZ], 3.3, 7, axis="Y", op="cut")

stage = sys.argv[1]
pre = []
if stage == "1":
    pre = [{"tool": "new_design"}]
    for n, ex in [("zS", "112 mm"), ("L1", "90 mm"), ("L2", "85 mm"), ("zE", "zS + L1"), ("zW", "zE + L2")]:
        S.append({"command": "parameters.add", "params": {"name": n, "expression": ex}})
    # --- conical base: revolved profile (r, z) -> sketch (x, -z) on XZ
    prof = [(0, 51), (0, 55), (52, 55), (70, 4), (80, 4), (80, 0), (68.23, 0), (50.23, 51)]
    S.append({"command": "sketch.create", "params": {"plane": "XZ", "name": "Base profile"}})
    S.append({"command": "sketch.line", "params": {"points": [[r, -z] for r, z in prof], "closed": True}})
    S.append({"command": "sketch.finish", "params": {}})
    S.append({"command": "solid.revolve", "params": {"sketch": "Base profile", "axis": "Z", "name": "Base shell", "body_name": "Base"}})
elif stage == "1b":
    B = "Base"
    fillet("Base top round", B, [[52, 0, 55]], 4)
    box("Base servo opening", B, [10.15, 0, 53], [41.5, 20.5, 6], op="cut")
    for i, (x, y) in enumerate([(-14.6, -5), (-14.6, 5), (34.9, -5), (34.9, 5)]):
        cyl(f"Base tab hole {i+1}", B, [x, y, 50], 4.5, 6, op="cut")
    cyl("Base cable pass", B, [-26, 0, 50], 16, 6, op="cut")
    for i, (x, y) in enumerate([(53.03, 53.03), (-53.03, 53.03), (-53.03, -53.03), (53.03, -53.03)]):
        cyl(f"Base flange hole {i+1}", B, [x, y, -1], 4.5, 6, op="cut")
    cyl("Base cable exit", B, [-80, 0, 14], 12, 20, axis="X", op="cut")
    # turntable cap with skirt hiding the joint
    T = "Turntable"
    cyl("Cap", T, [0, 0, 56], 104, 15, new=True)
    cyl("Cap hollow", T, [0, 0, 55], 98, 11, op="cut")
    fillet("Cap top round", T, [[52, 0, 71]], 3)
    cyl("Cap horn centre", T, [0, 0, 65], 3.5, 7, op="cut")
    for i, (x, y) in enumerate([(8, 0), (-8, 0), (0, 8), (0, -8)]):
        cyl(f"Cap horn hole {i+1}", T, [x, y, 65], 2.2, 7, op="cut")
    cyl("Cap cable hole", T, [0, -15, 65], 10, 7, op="cut")
elif stage == "2":
    TW = "Tower"
    stadium("Tower", TW, None, "zS", -21, 24, 24, new=True, flat_bottom=71)
    fillet("Tower round", TW, [[24, 24, 90]], 2.5)
    box("Tower cavity", TW, [0, -0.5, mid(74, "zS")], [42, 43, "zS - 74"], op="cut")
    cyl("Tower cavity top", TW, [0, -22, "zS"], 42, 43, axis="Y", op="cut")
    servo_seat("Shoulder", TW, "zS", -1)
    lid_bosses("Tower", TW, [(-16, "zS"), (16, "zS"), (-16, 80), (16, 80)])
    cyl("Tower cable hole", TW, [0, -15, 70], 10, 5, op="cut")
    lid("TowerLid", "TowerLid", None, "zS", ["zS"], [(-16, "zS"), (16, "zS"), (-16, 80), (16, 80)], flat_bottom=71)
    fillet("TowerLid round", "TowerLid", [[24, -24, 90]], 2.5)
elif stage == "3":
    U = "UpperArm"
    stadium("UpperArm cheek A", U, "zS", "zE", 28, 33, 24, new=True)
    stadium("UpperArm cheek B", U, "zS", "zE", -33, -28, 24)
    box("UpperArm spine", U, [0, 0, mid("zS", "zE")], [48, 56, "L1 - 54"])
    m = (V["zS"] + V["zE"]) / 2
    fillet("UpperArm round A", U, [[24, 33, m]], 2)
    fillet("UpperArm round B", U, [[24, -33, m]], 2)
    box("UpperArm window", U, [0, 0, mid("zS", "zE")], [60, 46, "L1 - 64"], op="cut")
    horn_holes("Shoulder", U, "zS"); horn_holes("Elbow", U, "zE")
    cheek_b_pivot("Shoulder", U, "zS"); cheek_b_pivot("Elbow", U, "zE")
elif stage == "4":
    F = "Forearm"
    stadium("Forearm", F, "zE", "zW", -21, 24, 24, new=True)
    m = (V["zE"] + V["zW"]) / 2
    fillet("Forearm round", F, [[24, 24, m]], 2.5)
    box("Forearm cavity", F, [0, -0.5, mid("zE", "zW")], [42, 43, "L2"], op="cut")
    cyl("Forearm cavity end 1", F, [0, -22, "zE"], 42, 43, axis="Y", op="cut")
    cyl("Forearm cavity end 2", F, [0, -22, "zW"], 42, 43, axis="Y", op="cut")
    servo_seat("Elbow", F, "zE", 1)
    servo_seat("Wrist", F, "zW", -1)
    screws = [(-16, "zE"), (16, "zE"), (-16, mid("zE", "zW")), (16, mid("zE", "zW")), (-16, "zW"), (16, "zW")]
    lid_bosses("Forearm", F, screws)
    lid("ForearmLid", "ForearmLid", "zE", "zW", ["zE", "zW"], screws, cable=mid("zE", "zW"))
    fillet("ForearmLid round", "ForearmLid", [[24, -24, m]], 2.5)
elif stage == "5":
    W = "WristFork"
    for side, y0 in (("A", 28), ("B", -33)):
        cyl(f"Wrist cheek {side} end", W, [0, y0, "zW"], 48, 5, axis="Y", new=(side == "A"))
        box(f"Wrist cheek {side}", W, [0, y0 + 2.5, e("zW", 16)], [48, 5, 32])
    box("Wrist bridge", W, [0, 0, e("zW", 29.5)], [48, 66, 5])
    fillet("Wrist round A", W, [[24, 33, V["zW"] + 10]], 2)
    fillet("Wrist round B", W, [[24, -33, V["zW"] + 10]], 2)
    horn_holes("Wrist", W, "zW"); cheek_b_pivot("Wrist", W, "zW")
    box("Roll cradle", W, [5.2, 0, e("zW", 32 + 7.85)], [37.6, 18, 15.7])
    zc = V["zW"] + 40
    fillet("Roll cradle round", W, [[24, 9, zc], [24, -9, zc], [-13.6, 9, zc], [-13.6, -9, zc]], 5)
    box("Roll pocket", W, [5.4, 0, e("zW", 39.95)], [23.6, 13, 15.8], op="cut")
    for i, x in enumerate([-8.5, 19.3]):
        cyl(f"Roll tab hole {i+1}", W, [x, 0, e("zW", 39.7)], 1.8, 9, op="cut")
    box("Roll cable notch", W, [20, 0, e("zW", 35.55)], [8, 7, 7], op="cut")
elif stage == "6":
    G = "GripperFrame"
    box("Palm", G, [0, -2, e(P, 2)], [60, 40, 4], new=True)
    pz = V["zW"] + 64
    fillet("Palm round", G, [[30, 18, pz], [-30, 18, pz], [30, -22, pz], [-30, -22, pz]], 6)
    cyl("Palm horn hole", G, [0, 0, e(P, -1)], 2.5, 6, op="cut")
    for i, x in enumerate([-7, 7]):
        cyl(f"Palm horn screw {i+1}", G, [x, 0, e(P, -1)], 1.6, 6, op="cut")
    box("Gripper plate", G, [0, 1.5, e(P, 22.5)], [56, 3, 37])
    for sx in (-26.5, 26.5):
        box(f"Gripper side {'L' if sx < 0 else 'R'}", G, [sx, -10, e(P, 22.5)], [3, 20, 37])
    box("Grip servo window", G, [GX, 1.5, e(GZ, -5.4)], [12.8, 5, 23.6], op="cut")
    for i, dz in enumerate([-19.3, 8.5]):
        cyl(f"Grip tab hole {i+1}", G, [GX, -1, e(GZ, dz)], 1.8, 5, axis="Y", op="cut")
    cyl("Idler boss", G, [-GX, 3, GZ], 7, 8.5, axis="Y")
    cyl("Idler axle hole", G, [-GX, -1, GZ], 3.3, 14, axis="Y", op="cut")
elif stage == "7":
    jaw("R"); jaw("L")
elif stage == "8":
    mg995_base("MG995 Base")
    mg995_pitch("MG995 Shoulder", "zS", -1)
    mg995_pitch("MG995 Elbow", "zE", 1)
    mg995_pitch("MG995 Wrist", "zW", -1)
    sg90_roll("SG90 Roll", "zW + 32")
    sg90_grip("SG90 Grip", GX, GZ)
print(json.dumps(pre + [{"tool": "batch", "args": {"commands": S, "verbose": False}},
                        {"tool": "measure", "args": {"summary": True}}]))
