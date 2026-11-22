"""Second shoulder MG995 (side B, outboard of cheek B) + its bracket. python gen6.py > s1.json"""
import json, math
S = []
def box(name, body, c, s, op="join", new=False):
    p = {"length": s[0], "width": s[1], "height": s[2], "center": c, "name": name}
    p.update({"body_name": body, "operation": "new"} if new else {"operation": op, "targets": [body]})
    S.append({"command": "solid.box", "params": p})
def cyl(name, body, base, d, h, axis="Y", op="join", new=False):
    p = {"diameter": d, "height": h, "base": base, "axis": axis, "name": name}
    p.update({"body_name": body, "operation": "new"} if new else {"operation": op, "targets": [body]})
    S.append({"command": "solid.cylinder", "params": p})
zS = 112
B = "Soporte servo hombro B"
box("SB tab", B, [0, -25.5, 77.5], [42, 3, 13], new=True)          # against TowerLid, 2 lower lid screws
box("SB foot", B, [0, -40, 72.7], [40, 32, 3.4])                         # rests on the turntable cap (z 71)
box("SB plate", B, [0, -46, 103.5], [32, 3, 65])                     # MG995 tabs screw onto its -Y face
for sx in (1, -1):
    box(f"SB outer rib {sx:+d}", B, [sx * 13.5, -51.75, 84.7], [3, 8.5, 20.6])
    box(f"SB inner rib {sx:+d}", B, [sx * 13.5, -39.25, 79.2], [3, 10.5, 9.6])
box("SB servo window", B, [0, -46, zS - 10.15], [20.5, 5, 41.5], op="cut")
k = 1
for z in (zS - 34.9, zS + 14.6):
    for x in (-5, 5):
        cyl(f"SB tab hole {k}", B, [x, -49, z], 2.2, 6, op="cut"); k += 1
for i, x in enumerate((-16, 16)):
    cyl(f"SB lid screw {i+1}", B, [x, -28, 80], 3.0, 5, op="cut")
# servo dummy: shaft +Y, tip 0.5 mm off the cheek B outer face (y -33), body hanging down like servo A
D = "MG995 Shoulder B"
box("MG995 Shoulder B case", D, [0, -58.4, zS - 10.15], [19.7, 36, 40.7], new=True)
box("MG995 Shoulder B tabs", D, [0, -48.75, zS - 10.15], [19.7, 2.5, 54.5])
cyl("MG995 Shoulder B shaft", D, [0, -40.4, zS], 6, 6.9)
# horn holes on cheek B (centre hole already exists: 5.2 pivot hole)
for i, (dx, dz) in enumerate([(8, 0), (-8, 0), (0, 8), (0, -8)]):
    cyl(f"Shoulder B horn hole {i+1}", "UpperArm", [dx, -34, zS + dz], 2.2, 7, op="cut")
S.append({"command": "component.move_bodies", "params": {"bodies": [B, D], "component": "Shoulder part"}})
print(json.dumps([{"tool": "new_design"}, {"tool": "open", "args": {"path": "C:/Users/vicen/SOLIDCRAFT/brazo_compacto/brazo_compacto.sc"}},
  {"tool": "measure", "args": {"summary": True}},
  {"tool": "batch", "args": {"commands": S, "verbose": False}},
  {"tool": "measure", "args": {"summary": True}},
  {"tool": "execute", "args": {"command": "inspect.interference", "params": {}}}]))
