"""Printed wheel for the yellow TT gear motor: PLA rim with two bead flanges + TPU tyre.
Built in print orientation: axis = Z, motor side on the bed (z = 0), outer side up.
usage: python gen5.py > calls.json
"""
import json, math

OD_TYRE = 65.0          # keeps the axle height (32.5 mm) of the base
W = 34.0                # total wheel width (stock TT wheel: 26 mm)
SEAT_R = 27.5           # tyre seat radius (OD 55)
RIM_T = 2.0             # rim wall
FL_R = 28.7             # bead flange radius (1.2 mm lip)
FL_T = 1.6              # flange thickness
HUB_R, HUB_H = 6.0, 11.0
WEB_T = 2.4
BORE_D, FLAT = 5.6, 1.95   # TT shaft: D 5.4 with two flats 3.7 mm apart (+0.1 clearance each)
BORE_DEPTH = 9.6
TYRE_ID_R = 27.2        # 0.3 mm radial interference on the seat
TYRE_GAP = 0.1

S = []
def cmd(c, **p): S.append({"command": c, "params": p})

rim_in = SEAT_R - RIM_T
prof = [(0, 0), (FL_R, 0), (FL_R, FL_T), (SEAT_R, FL_T),
        (SEAT_R, W - FL_T - (FL_R - SEAT_R)), (FL_R, W - FL_T), (FL_R, W - 0.6), (FL_R - 0.5, W),
        (rim_in, W), (rim_in, WEB_T + 2), (rim_in - 2, WEB_T), (HUB_R + 2, WEB_T), (HUB_R, WEB_T + 2),
        (HUB_R, HUB_H), (0, HUB_H)]
cmd("sketch.create", plane="XZ", name="Rim profile")
cmd("sketch.line", points=[[r, -z] for r, z in prof], closed=True)
cmd("sketch.finish")
S.append({"command": "solid.revolve", "params": {"sketch": "Rim profile", "axis": "Z", "name": "Rim", "body_name": "Llanta TT"}})

R = "Llanta TT"
def cyl(name, base, d, h, op="cut", body=R):
    S.append({"command": "solid.cylinder", "params": {"diameter": d, "height": h, "base": base, "axis": "Z", "name": name, "operation": op, "targets": [body]}})
def box(name, c, s, op="join", body=R):
    S.append({"command": "solid.box", "params": {"length": s[0], "width": s[1], "height": s[2], "center": c, "name": name, "operation": op, "targets": [body]}})

# double-D bore from the motor side, flats filled back in; screw hole through the cap
cyl("Shaft bore", [0, 0, -1], BORE_D, BORE_DEPTH + 1)
for sx in (1, -1):
    box(f"Bore flat {'+' if sx > 0 else '-'}", [sx * (FLAT + 0.6), 0, BORE_DEPTH / 2], [1.2, BORE_D + 0.4, BORE_DEPTH])
cyl("Screw hole", [0, 0, BORE_DEPTH - 0.5], 2.3, HUB_H - BORE_DEPTH + 1)
# lightening windows in the web (vertical through holes: no support)
for i in range(6):
    t = 2 * math.pi * i / 6
    cyl(f"Web window {i+1}", [15.8 * math.cos(t), 15.8 * math.sin(t), -1], 9.0, WEB_T + 2)

# TPU tyre between the flanges
z0, z1 = FL_T + TYRE_GAP, W - FL_T - TYRE_GAP
ro = OD_TYRE / 2
# inner top corner chamfered to sit against the 45 deg flange chamfer
tyre = [(TYRE_ID_R, z0), (ro - 0.8, z0), (ro, z0 + 0.8), (ro, z1 - 0.8), (ro - 0.8, z1), (TYRE_ID_R + 1.4, z1), (TYRE_ID_R, z1 - 1.4)]
cmd("sketch.create", plane="XZ", name="Tyre profile")
cmd("sketch.line", points=[[r, -z] for r, z in tyre], closed=True)
cmd("sketch.finish")
S.append({"command": "solid.revolve", "params": {"sketch": "Tyre profile", "axis": "Z", "name": "Tyre", "body_name": "Neumatico TT"}})

def pappus(pts):
    A = Cx = 0
    for i in range(len(pts)):
        x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % len(pts)]
        c = x0 * y1 - x1 * y0; A += c; Cx += (x0 + x1) * c
    A /= 2; Cx /= 6 * A
    return abs(2 * math.pi * Cx * A)

expect_rim = pappus(prof) - math.pi * (BORE_D / 2) ** 2 * BORE_DEPTH - 6 * math.pi * 4.5 ** 2 * WEB_T
import sys
print(f"expected rim ~{expect_rim:.0f} mm3 (+ flats, - screw hole), tyre {pappus(tyre):.0f} mm3", file=sys.stderr)
print(json.dumps([{"tool": "new_design"}, {"tool": "batch", "args": {"commands": S, "verbose": False}},
                  {"tool": "measure", "args": {"summary": True}}]))
