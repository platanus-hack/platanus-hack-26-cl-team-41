"""Generates SolidCraft batch stages for a 6-servo robot arm (4x MG995, 2x SG90).
usage: python gen.py <stage> > calls.json
World: Z up, arm in XZ plane at home pose (straight up), pitch axes along Y.
"""
import json, sys

def e(base, off):
    """expression base + off (base is a parameter expression or number)."""
    if isinstance(base, (int, float)):
        return round(base + off, 4)
    if off == 0:
        return base
    return f"{base} + {off}" if off > 0 else f"{base} - {abs(off)}"

S = []
def box(name, body, cx, cy, cz, lx, ly, lz, op="join", new=False):
    p = {"length": lx, "width": ly, "height": lz, "center": [cx, cy, cz], "name": name}
    if new:
        p["body_name"] = body; p["operation"] = "new"
    else:
        p["operation"] = op; p["targets"] = [body]
    S.append({"command": "solid.box", "params": p})

def cyl(name, body, base, d, h, axis="Z", op="join", new=False):
    p = {"diameter": d, "height": h, "base": base, "axis": axis, "name": name}
    if new:
        p["body_name"] = body; p["operation"] = "new"
    else:
        p["operation"] = op; p["targets"] = [body]
    S.append({"command": "solid.cylinder", "params": p})

def zspan(z0, z1):
    """centre and height of a span between two expressions/numbers sharing a base."""
    return z0, z1

# ---------- MG995 / SG90 nominal dimensions (mm) ----------
# MG995 (shaft along +h, shaft tip at h=0, shaft 10.2 from the +l body end)
MG = dict(L=40.7, W=19.7, case_bot=-42.9, case_top=-6.9, tab_bot=-16.9, tab_top=-14.4,
          tab_len=54.5, body_c=-10.15, hole_dl=24.75, hole_dw=5.0)

def holder(body, zc, tag):
    """Mount for a pitch MG995 whose shaft axis is along +Y at height zc (x=0).
    Servo case y[-18.5,17.5], tabs y[7.5,10] rest on cheek A outer face (y=7.5).
    Cheeks start at zc-38 (must sit on a face of `body`)."""
    # cheek A (tab side)
    box(f"{tag} cheek A", body, 0, 5.5, e(zc, -8.5), 34, 4, 59)
    box(f"{tag} servo window", body, 0, 5.5, e(zc, -10.15), 20.5, 6, 41.5, op="cut")
    for i, (dx, dz) in enumerate([(-5, -24.75), (5, -24.75), (-5, 24.75), (5, 24.75)]):
        cyl(f"{tag} tab hole {i+1}", body, [dx, 2, e(zc, -10.15 + dz)], 3.3, 8, axis="Y", op="cut")
    # cheek B (servo bottom side) with M5 axle hole
    box(f"{tag} cheek B", body, 0, -22.5, e(zc, -13), 34, 4, 50)
    cyl(f"{tag} axle hole", body, [0, -27, zc], 5.2, 8, axis="Y", op="cut")
    # side gussets tying the cheeks together
    for sx in (-15, 15):
        box(f"{tag} gusset {'L' if sx < 0 else 'R'}", body, sx, -8.5, e(zc, -29), 4, 24, 18)

def yoke(body, zc, ztop_off_from, tag, new=True):
    """U-yoke straddling the servo whose shaft is at height zc: plate A on the horn (y 25..29),
    plate B on the M5 axle (y -29..-25). Plates run from zc up to ztop (expression)."""
    ztop_base, ztop_off = ztop_off_from
    # plate A (horn side) = box from zc to top + round lobe at the shaft
    # box centre z = (zc + ztop)/2 ; written as an expression
    cz = f"({zc} + {e(ztop_base, ztop_off)}) / 2"
    hz = f"{e(ztop_base, ztop_off)} - ({zc})"
    cyl(f"{tag} lobe A", body, [0, 25, zc], 30, 4, axis="Y", new=new)
    box(f"{tag} plate A", body, 0, 27, cz, 30, 4, hz)
    cyl(f"{tag} lobe B", body, [0, -29, zc], 30, 4, axis="Y")
    box(f"{tag} plate B", body, 0, -27, cz, 30, 4, hz)
    # horn screw holes (centre M3 + 4 pilot holes on r=8: check against your horn)
    cyl(f"{tag} horn centre hole", body, [0, 24, zc], 3.5, 6, axis="Y", op="cut")
    for i, (dx, dz) in enumerate([(8, 0), (-8, 0), (0, 8), (0, -8)]):
        cyl(f"{tag} horn hole {i+1}", body, [dx, 24, e(zc, dz)], 2.2, 6, axis="Y", op="cut")
    cyl(f"{tag} axle hole B", body, [0, -30, zc], 5.2, 6, axis="Y", op="cut")

def bridge(body, zb, tag, x0=-15, x1=15):
    """Cross plate y[-29,29], z[zb, zb+6]."""
    box(f"{tag} bridge", body, (x0 + x1) / 2, 0, e(zb, 3), x1 - x0, 58, 6)

# ---------- servo dummies ----------
def mg995_pitch(name, zc):
    """MG995 with shaft along +Y at (0, *, zc), body extending down (-Z)."""
    # case: l along +Z from zc-30.5 to zc+10.2, w along X, h along Y: y[-18.5, 17.5]
    box(f"{name} case", name, 0, -0.5, e(zc, -10.15), 19.7, 36, 40.7, new=True)
    box(f"{name} tabs", name, 0, 8.75, e(zc, -10.15), 19.7, 2.5, 54.5)
    cyl(f"{name} shaft", name, [0, 17.5, zc], 6, 6.9, axis="Y")

def mg995_base(name):
    """Base MG995: shaft along +Z at the origin, tip at z=46.9, body along +X."""
    box(f"{name} case", name, 10.15, 0, 22, 40.7, 19.7, 36, new=True)
    box(f"{name} tabs", name, 10.15, 0, 31.25, 54.5, 19.7, 2.5)
    cyl(f"{name} shaft", name, [0, 0, 40], 6, 6.9)

def sg90_roll(name, zW):
    """SG90 standing on the wrist bridge: shaft along +Z at x=y=0, case bottom at zW+36."""
    box(f"{name} case", name, 5.4, 0, e(zW, 36 + 11.35), 22.8, 12.2, 22.7, new=True)
    box(f"{name} tabs", name, 5.4, 0, e(zW, 36 + 15.7 + 1.25), 32.2, 12.2, 2.5)
    cyl(f"{name} gear bump", name, [0, 0, e(zW, 36 + 22.7)], 11.8, 4)
    cyl(f"{name} shaft", name, [0, 0, e(zW, 36 + 26.7)], 4.8, 2.8)

def sg90_grip(name, gx, Gz):
    """SG90 behind the gripper plate: shaft along +Y at (gx, *, Gz), body hanging down (-Z).
    case y[-18.2, 4.5], tabs y[-2.5, 0]."""
    box(f"{name} case", name, gx, -6.85, e(Gz, -5.4), 12.2, 22.7, 22.8, new=True)
    box(f"{name} tabs", name, gx, -1.25, e(Gz, -5.4), 12.2, 2.5, 32.2)
    cyl(f"{name} gear bump", name, [gx, 4.5, Gz], 11.8, 4, axis="Y")
    cyl(f"{name} shaft", name, [gx, 8.5, Gz], 4.8, 2.8, axis="Y")

# ---------- stages ----------
GX = 10.6           # gear centre offset from the roll axis (centre distance 21.2)
P = "zW + 67.5"     # palm bottom
GZ = "zW + 94.5"    # gear axis height (P + 27)

def jaw(body, side):
    s = 1 if side == "R" else -1
    cx = s * GX
    cyl(f"Jaw{side} hub", body, [cx, 12, GZ], 17.4, 5, axis="Y", new=True)
    if side == "R":   # seed tooth pointing +Z
        box(f"Jaw{side} tooth root", body, cx, 14.5, e(GZ, 9.45), 2.3, 5, 2.1)
        box(f"Jaw{side} tooth tip", body, cx, 14.5, e(GZ, 11.25), 1.4, 5, 1.5)
    else:             # seed tooth pointing +X (half a pitch out of phase with JawR)
        box(f"Jaw{side} tooth root", body, cx + 9.45, 14.5, GZ, 2.1, 5, 2.3)
        box(f"Jaw{side} tooth tip", body, cx + 11.25, 14.5, GZ, 1.5, 5, 1.4)
    S.append({"command": "solid.pattern.circular", "params": {
        "features": [f"Jaw{side} tooth root", f"Jaw{side} tooth tip"],
        "axis": {"origin": [cx, 0, GZ], "dir": [0, 1, 0]}, "count": 14, "name": f"Jaw{side} teeth"}})

def jaw_finger(body, side):
    s = 1 if side == "R" else -1
    cx = s * GX
    box(f"Jaw{side} finger", body, cx, 14.5, e(GZ, 27.5), 8, 5, 55)
    box(f"Jaw{side} pad", body, cx - s * 5.8, 14.5, e(GZ, 46.5), 3.6, 5, 17)
    if side == "R":
        cyl("JawR horn screw hole", body, [cx, 11, GZ], 2.2, 7, axis="Y", op="cut")
        cyl("JawR horn hub recess", body, [cx, 11, GZ], 7.5, 3, axis="Y", op="cut")
    else:
        cyl("JawL axle hole", body, [cx, 11, GZ], 3.3, 7, axis="Y", op="cut")

stage = sys.argv[1]
if stage == "1":
    for n, ex in [("zS", "91 mm"), ("L1", "100 mm"), ("L2", "90 mm"), ("zE", "zS + L1"), ("zW", "zE + L2")]:
        S.append({"command": "parameters.add", "params": {"name": n, "expression": ex}})
    B = "Base"
    cyl("Base cup", B, [0, 0, 0], 120, 47, new=True)
    cyl("Base hollow", B, [0, 0, 3], 112, 50, op="cut")
    box("Base servo cradle", B, 10.15, 0, 16.5, 56.3, 28, 27)
    box("Base servo pocket", B, 10.15, 0, 17.5, 41.5, 20.5, 27, op="cut")
    for i, (x, y) in enumerate([(-14.6, -5), (-14.6, 5), (34.9, -5), (34.9, 5)]):
        cyl(f"Base tab hole {i+1}", B, [x, y, 18], 3.3, 13, op="cut")
    box("Base servo cable notch", B, 34.65, 0, 9, 9, 6, 10, op="cut")
    box("Base cable exit", B, 57, 0, 9, 12, 16, 12, op="cut")
    for i, (x, y) in enumerate([(35.36, 35.36), (-35.36, 35.36), (-35.36, -35.36), (35.36, -35.36)]):
        cyl(f"Base mount hole {i+1}", B, [x, y, -1], 4.5, 5, op="cut")
elif stage == "2":
    T = "Shoulder"
    cyl("Turntable", T, [0, 0, 48], 116, 5, new=True)
    cyl("Turntable centre hole", T, [0, 0, 47], 7, 7, op="cut")
    for i, (x, y) in enumerate([(8, 0), (-8, 0), (0, 8), (0, -8)]):
        cyl(f"Turntable horn hole {i+1}", T, [x, y, 47], 2.2, 7, op="cut")
    holder(T, "zS", "Shoulder")
elif stage == "3":
    U = "UpperArm"
    yoke(U, "zS", ("zE", -38), "UpperArm")
    bridge(U, "zE - 44", "UpperArm")
    holder(U, "zE", "Elbow")
elif stage == "4":
    F = "Forearm"
    yoke(F, "zE", ("zW", -38), "Forearm")
    bridge(F, "zW - 44", "Forearm")
    holder(F, "zW", "Wrist")
elif stage == "5":
    W = "Wrist"
    yoke(W, "zW", ("zW", 36), "Wrist")
    bridge(W, "zW + 30", "Wrist", x0=-15, x1=24)
    # SG90 roll servo cradle (shaft on the arm axis)
    box("Roll cradle", W, 5.4, 0, e("zW", 36 + 15.7 / 2), 33.8, 18, 15.7)
    box("Roll pocket", W, 5.4, 0, e("zW", 36 + 15.7 / 2), 23.6, 13, 15.8, op="cut")
    for i, x in enumerate([-8.5, 19.3]):
        cyl(f"Roll tab hole {i+1}", W, [x, 0, e("zW", 36 + 15.7 - 8)], 1.8, 9, op="cut")
    box("Roll cable notch", W, 20, 0, e("zW", 36 + 3.5), 8, 7, 7, op="cut")
elif stage == "6":
    G = "GripperFrame"
    box("Palm", G, 0, -2, e(P, 2), 60, 40, 4, new=True)
    cyl("Palm horn hole", G, [0, 0, e(P, -1)], 2.5, 6, op="cut")
    for i, x in enumerate([-7, 7]):
        cyl(f"Palm horn screw {i+1}", G, [x, 0, e(P, -1)], 1.6, 6, op="cut")
    box("Gripper plate", G, 0, 1.5, e(P, 22.5), 56, 3, 37)
    box("Grip servo window", G, GX, 1.5, e(GZ, -5.4), 12.8, 5, 23.6, op="cut")
    for i, dz in enumerate([-19.3, 8.5]):
        cyl(f"Grip tab hole {i+1}", G, [GX, -1, e(GZ, dz)], 1.8, 5, axis="Y", op="cut")
    cyl("Idler boss", G, [-GX, 3, GZ], 7, 8.5, axis="Y")
    cyl("Idler axle hole", G, [-GX, -1, GZ], 3.3, 14, axis="Y", op="cut")
    for sx in (-26, 26):
        box(f"Gripper gusset {'L' if sx < 0 else 'R'}", G, sx, -11, e(P, 12), 4, 22, 16)
elif stage == "7R":
    jaw("JawR", "R")
elif stage == "7L":
    jaw("JawL", "L")
elif stage == "7F":
    jaw_finger("JawR", "R"); jaw_finger("JawL", "L")
elif stage == "8":
    mg995_base("MG995 Base")
    mg995_pitch("MG995 Shoulder", "zS")
    mg995_pitch("MG995 Elbow", "zE")
    mg995_pitch("MG995 Wrist", "zW")
    sg90_roll("SG90 Roll", "zW")
    sg90_grip("SG90 Grip", GX, GZ)
print(json.dumps([{"tool": "batch", "args": {"commands": S, "verbose": False}},
                  {"tool": "measure", "args": {"summary": True}}]))
