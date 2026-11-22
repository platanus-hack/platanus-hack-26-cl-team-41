"""Mueve una articulacion del brazo (brazo_estable.lua, sin puente) poniendo SCR_USER2..6 en grados.
Uso: python mover.py COM4 hombro 10      (base, hombro, codo, muneca, giro)
     python mover.py COM4 centro         (todas a 0)
El script limita la velocidad a MAX_RATE_DPS, asi que el servo llega despacio.
"""
import sys, time
from pymavlink import mavutil

IDX = {"base": 2, "hombro": 3, "codo": 4, "muneca": 5, "giro": 6}
port, joint = sys.argv[1], sys.argv[2]
m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)


def setp(name, val):
    for _ in range(3):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(val),
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
        if p and p.param_id == name and abs(p.param_value - val) < 1e-3:
            return True
    return False


if joint == "centro":
    ok = all(setp("SCR_USER%d" % i, 0) for i in IDX.values())
    print("todas a 0:", "OK" if ok else "FALLO")
else:
    val = float(sys.argv[3])
    print("%s -> %.1f grados: %s" % (joint, val, "OK" if setp("SCR_USER%d" % IDX[joint], val) else "FALLO"))
