"""Mobile base: 4 drive pods (brushless 2207 1750KV -> 80:1 three-stage spur reduction) in an enclosed chassis.
usage: python gen3.py <stage>
World: X forward, Y left, Z up, floor at z=0. Front-right pod built first (right side = -Y), then mirrored.
Gear train per wheel (axes along Y):  motor M --P1 12T m1 / G1 60T m1--> A --P2 12T m1.25 / G2 48T m1.25--> B
--P3 12T m1.25 / G3 48T m1.25--> wheel W.  Ratio 5 * 4 * 4 = 80.
"""
import json, math, sys

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

def poly_extrude(name, body, pts_xz, y0, h, op="new"):
    """Closed polygon given in world (x, z) on a plane at Y=y0, extruded +Y by h."""
    cmd("sketch.create", plane="XZ", offset=y0, name=name + " sk")
    cmd("sketch.line", points=[[round(x, 4), round(-z, 4)] for x, z in pts_xz], closed=True)
    cmd("sketch.finish")
    p = {"sketch": name + " sk", "distance": h, "name": name}
    if op == "new": p["body_name"] = body
    else: p.update(operation=op, targets=[body])
    S.append({"command": "solid.extrude", "params": p})

# ---------- involute gear outline ----------
def inv(a): return math.tan(a) - a

def gear_pts(cx, cz, z, m, phase, pa=math.radians(25), backlash=0.15, n_flank=6):
    r = m * z / 2; rb = r * math.cos(pa); ra = r + m; rf = r - 1.25 * m
    s = math.pi * m / 2 - backlash / 2
    psi = s / (2 * r)
    def half(rho):
        a = math.acos(min(1.0, rb / rho))
        return psi + inv(pa) - inv(a)
    r0 = max(rb, rf)
    radii = [r0 + (ra - r0) * (i / (n_flank - 1)) ** 1.3 for i in range(n_flank)]
    pts = []
    pitch = 2 * math.pi / z
    for k in range(z):
        c = phase + k * pitch
        flank = []
        if rf < rb:
            flank.append((rf, half(rb)))
        flank += [(rho, half(rho)) for rho in radii]
        # right flank (clockwise side) root -> tip
        for rho, h in flank:
            pts.append((rho, c - h))
        # tip land midpoint
        pts.append((ra, c))
        for rho, h in reversed(flank):
            pts.append((rho, c + h))
        # root land midpoint to next tooth
        pts.append((rf, c + pitch / 2))
    return [(cx + rho * math.cos(t), cz + rho * math.sin(t)) for rho, t in pts]

def hexagon(cx, cz, af, rot=0):
    rc = af / math.sqrt(3)
    return [(cx + rc * math.cos(rot + i * math.pi / 3), cz + rc * math.sin(rot + i * math.pi / 3)) for i in range(6)]

# ---------- convex hull of circles (pod outline) ----------
def hull(circles, step=6):
    P = []
    for (cx, cz), r in circles:
        for i in range(0, 360, step):
            t = math.radians(i); P.append((cx + r * math.cos(t), cz + r * math.sin(t)))
    P = sorted(set((round(x, 4), round(z, 4)) for x, z in P))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

# ---------- layout (front-right corner) ----------
AX = 80.0; AZ = 50.0                     # wheel axle (wheel diameter 100)
W = (AX, AZ)
B = (AX - 37.5, AZ)                      # stage 3 CD 37.5 (toward chassis centre)
A = (AX - 21.65, AZ + 33.99)             # stage 2 CD 37.5 from B
M = (A[0] + 36.0, A[1])                  # stage 1 CD 36 from A (m1 12/60)
LUGS = [(104.1, 21.3), (13.8, 25.9), (80.0, 116.0)]
def ang(p, q): return math.atan2(q[1] - p[1], q[0] - p[0])

# world Y of each layer (right side; wall outer face Y=-110, inner face -107)
Y = dict(G1=(-92, -86), P1=(-92, -86), P2=(-99.5, -92), G2=(-99, -93), P3=(-106, -99), G3=(-106, -100),
         plate=(-65.5, -62.5), motor=(-85.5, -65.5), wheel=(-146.5, -118.5))

def gears():
    # phases: driver tooth points at the driven gear; driven gear shows a gap back (half pitch).
    t = ang(M, A); poly_extrude("Pinion", "Pinion", gear_pts(*M, 12, 1.0, t), Y["P1"][0], 6)
    cyl("Pinion bore", "Pinion", [M[0], Y["P1"][0] - 1, M[1]], 5.2, 8, axis="Y", op="cut")
    t = ang(A, M) + math.pi / 60; poly_extrude("Gear A", "ClusterA", gear_pts(*A, 60, 1.0, t), Y["G1"][0], 6)
    t = ang(A, B); poly_extrude("Pinion A", "ClusterA", gear_pts(*A, 12, 1.25, t), Y["P2"][0], 7.5, op="join")
    for i in range(5):
        t = 2 * math.pi * i / 5
        cyl(f"Gear A window {i+1}", "ClusterA", [A[0] + 17 * math.cos(t), -93, A[1] + 17 * math.sin(t)], 13, 8, axis="Y", op="cut")
    cyl("ClusterA bore", "ClusterA", [A[0], -101, A[1]], 4.4, 17, axis="Y", op="cut")
    t = ang(B, A) + math.pi / 48; poly_extrude("Gear B", "ClusterB", gear_pts(*B, 48, 1.25, t), Y["G2"][0], 6)
    t = ang(B, W); poly_extrude("Pinion B", "ClusterB", gear_pts(*B, 12, 1.25, t), Y["P3"][0], 7, op="join")
    for i in range(5):
        t = 2 * math.pi * i / 5
        cyl(f"Gear B window {i+1}", "ClusterB", [B[0] + 17 * math.cos(t), -100, B[1] + 17 * math.sin(t)], 12, 8, axis="Y", op="cut")
    cyl("ClusterB bore", "ClusterB", [B[0], -108, B[1]], 4.4, 17, axis="Y", op="cut")
    t = ang(W, B) + math.pi / 48; poly_extrude("Output gear", "OutputGear", gear_pts(*W, 48, 1.25, t), Y["G3"][0], 6)
    for i in range(5):
        t = 2 * math.pi * i / 5
        cyl(f"Output window {i+1}", "OutputGear", [W[0] + 18 * math.cos(t), -107, W[1] + 18 * math.sin(t)], 12, 8, axis="Y", op="cut")
    poly_extrude("Output hex bore", "OutputGear", hexagon(*W, 10.3), -107, 8, op="cut")

def shaft_and_wheel():
    # hex shaft 10 AF from the pod plate to the wheel's outer face, collar outside the pod plate
    poly_extrude("Drive shaft", "Shaft", hexagon(*W, 10.0), Y["wheel"][0], Y["plate"][1] - Y["wheel"][0])
    cyl("Shaft collar", "Shaft", [W[0], Y["plate"][1], W[1]], 16, 2, axis="Y")
    cyl("Shaft end screw hole", "Shaft", [W[0], Y["wheel"][0] - 1, W[1]], 2.5, 11, axis="Y", op="cut")
    # wheel: rim 92/80, centre web, hub, hex bore; TPU tyre 100/92
    y0, y1 = Y["wheel"]; wd = y1 - y0
    cyl("Wheel rim", "Wheel", [W[0], y0, W[1]], 92, wd, axis="Y", new=True)
    cyl("Wheel rim hollow", "Wheel", [W[0], y0 - 1, W[1]], 85, wd + 2, axis="Y", op="cut")
    cyl("Wheel web", "Wheel", [W[0], (y0 + y1) / 2 - 1.5, W[1]], 86, 3, axis="Y")
    cyl("Wheel hub", "Wheel", [W[0], y0, W[1]], 24, wd, axis="Y")
    poly_extrude("Wheel hex bore", "Wheel", hexagon(*W, 10.3), y0 - 1, wd + 2, op="cut")
    for i in range(6):
        t = math.radians(30 + 60 * i)
        cyl(f"Wheel window {i+1}", "Wheel", [W[0] + 26 * math.cos(t), (y0 + y1) / 2 - 3, W[1] + 26 * math.sin(t)],
            18, 6, axis="Y", op="cut")
    cyl("Tyre", "Tyre", [W[0], y0, W[1]], 100, wd, axis="Y", new=True)
    cyl("Tyre bore", "Tyre", [W[0], y0 - 1, W[1]], 92, wd + 2, axis="Y", op="cut")

def pod():
    """Skeleton pod: 3 mm plate (motor mount + bolt and shaft supports) held off the chassis wall by 3 tubes."""
    co = [(W, 12), (B, 8), (A, 8), (M, 17)] + [(p, 6) for p in LUGS]
    poly_extrude("Pod plate", "Pod", hull(co), Y["plate"][0], 3)
    for i, (x, z) in enumerate(LUGS):
        cyl(f"Pod standoff {i+1}", "Pod", [x, -107, z], 10, Y["plate"][0] + 107, axis="Y")
        cyl(f"Pod standoff hole {i+1}", "Pod", [x, -108, z], 2.7, 13, axis="Y", op="cut")
    cyl("Pod spacer A", "Pod", [A[0], -85.8, A[1]], 9, Y["plate"][0] + 85.8, axis="Y")
    cyl("Pod spacer B", "Pod", [B[0], -92.6, B[1]], 9, Y["plate"][0] + 92.6, axis="Y")
    cyl("Pod shaft boss", "Pod", [W[0], -72, W[1]], 20, 72 + Y["plate"][0], axis="Y")
    for nm, p in (("A", A), ("B", B)):
        cyl(f"Pod bolt hole {nm}", "Pod", [p[0], -110, p[1]], 4.3, 50, axis="Y", op="cut")
    cyl("Pod shaft hole", "Pod", [W[0], -75, W[1]], 12, 15, axis="Y", op="cut")
    for i, (dx, dz) in enumerate([(8, 8), (-8, 8), (8, -8), (-8, -8)]):
        cyl(f"Motor screw {i+1}", "Pod", [M[0] + dx, -67, M[1] + dz], 3.2, 7, axis="Y", op="cut")
    cyl("Motor centre hole", "Pod", [M[0], -67, M[1]], 10, 7, axis="Y", op="cut")

def motor_dummy():
    cyl("Motor bell", "Motor", [M[0], Y["motor"][0], M[1]], 27.9, 20, axis="Y", new=True)
    cyl("Motor shaft", "Motor", [M[0], -97, M[1]], 5, 11.5, axis="Y")

HX, HY = 121.0, 110.0   # chassis half length / width (outer)


def chassis():
    C = "Chassis"
    box("Chassis block", C, [0, 0, 65.5], [2 * HX, 2 * HY, 113], new=True)
    fillet_pts = [[sx * HX, sy * HY, 65.5] for sx in (1, -1) for sy in (1, -1)]
    cmd("solid.fillet", edges=fillet_pts, radius=10, body=C, name="Chassis corner rounds")
    box("Chassis cavity", C, [0, 0, 68], [2 * HX - 6, 2 * HY - 6, 112], op="cut")
    in_pts = [[sx * (HX - 3), sy * (HY - 3), 70] for sx in (1, -1) for sy in (1, -1)]
    cmd("solid.fillet", edges=in_pts, radius=7, body=C, name="Chassis inner rounds")
    for sx in (1, -1):
        for sy in (1, -1):
            tag = f"{'F' if sx > 0 else 'R'}{'L' if sy > 0 else 'R'}"
            wx = sx * W[0]
            # shaft bearing: boss outside the wall + through hole
            yb = -HY - 8 if sy < 0 else HY
            cyl(f"{tag} axle boss", C, [wx, yb, AZ], 24, 8, axis="Y")
            cyl(f"{tag} axle hole", C, [wx, -HY - 10 if sy < 0 else HY - 4, AZ], 12, 14, axis="Y", op="cut")
            # blind sockets for the cluster bolts, wall bosses keeping cluster A in place
            for nm, p in (("A", A), ("B", B)):
                px = sx * p[0]
                ys = -109 if sy < 0 else 107
                cyl(f"{tag} bolt socket {nm}", C, [px, ys, p[1]], 4.2, 2, axis="Y", op="cut")
            yA = -107 if sy < 0 else 100
            cyl(f"{tag} spacer A", C, [sx * A[0], yA, A[1]], 9, 7, axis="Y")
            cyl(f"{tag} socket A", C, [sx * A[0], -109 if sy < 0 else 100, A[1]], 4.2, 9, axis="Y", op="cut")
            for i, (lx, lz) in enumerate(LUGS):
                cyl(f"{tag} lug screw {i+1}", C, [sx * lx, -HY - 1 if sy < 0 else HY - 4, lz], 3.2, 5, axis="Y", op="cut")
    # lid bosses (between the pods)
    for i, (x, y) in enumerate([(HX - 7, 0), (-(HX - 7), 0), (0, HY - 7), (0, -(HY - 7))]):
        cyl(f"Lid boss {i+1}", C, [x, y, 60], 10, 62)
        cyl(f"Lid boss hole {i+1}", C, [x, y, 110], 2.6, 13, op="cut")
    # rear panel: power switch, USB/charge slot; floor: battery strap slots, vents
    cyl("Power switch hole", C, [-HX - 1, 40, 45], 12.5, 5, axis="X", op="cut")
    box("USB slot", C, [-HX + 1.5, -35, 40], [6, 30, 12], op="cut")
    for i, x in enumerate([-45, 45]):
        for sy in (1, -1):
            box(f"Strap slot {i+1}{'L' if sy > 0 else 'R'}", C, [x, sy * 30, 10.5], [4, 22, 6], op="cut")
    for sx in (1, -1):
        box(f"{'Front' if sx > 0 else 'Rear'} window", C, [sx * (HX - 1.5), 0, 75], [6, 100, 50], op="cut")
    for i, x in enumerate([-30, -10, 10, 30]):
        box(f"Floor vent {i+1}", C, [x, 0, 10.5], [5, 40, 6], op="cut")

def deck():
    D = "Deck"
    box("Deck plate", D, [0, 0, 123.5], [2 * HX, 2 * HY, 3], new=True)
    cmd("solid.fillet", edges=[[sx * HX, sy * HY, 123.5] for sx in (1, -1) for sy in (1, -1)], radius=10, body=D,
        name="Deck corner rounds")
    for i, (x, y) in enumerate([(HX - 7, 0), (-(HX - 7), 0), (0, HY - 7), (0, -(HY - 7))]):
        cyl(f"Deck screw {i+1}", D, [x, y, 121], 3.2, 5, op="cut")
    for i, (x, y) in enumerate([(53.03, 53.03), (-53.03, 53.03), (-53.03, -53.03), (53.03, -53.03)]):
        cyl(f"Arm bolt {i+1}", D, [x, y, 121], 4.5, 5, op="cut")
    cyl("Arm cable pass", D, [0, 0, 121], 40, 5, op="cut")
    for i, y in enumerate([-80, -70, 70, 80]):
        box(f"Deck vent {i+1}", D, [-90, y, 123.5], [40, 4, 5], op="cut")

stage = sys.argv[1]
pre = []
if stage == "gears":
    pre = [{"tool": "new_design"}]
    gears()
elif stage == "pod":
    pod(); motor_dummy()
elif stage == "gp":
    pre = [{"tool": "new_design"}]
    gears(); pod(); motor_dummy()
elif stage == "wheel":
    shaft_and_wheel()
elif stage == "chassis":
    chassis()
elif stage == "deck":
    deck()
print(json.dumps(pre + [{"tool": "batch", "args": {"commands": S, "verbose": False}},
                        {"tool": "measure", "args": {"summary": True}}]))
