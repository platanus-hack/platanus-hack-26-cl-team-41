"""Fija un parametro en vivo. Uso: python setp.py COM4 BRZ_STAB 0.3"""
import sys
from pymavlink import mavutil
m = mavutil.mavlink_connection(sys.argv[1], baud=115200); m.wait_heartbeat(timeout=10)
name, val = sys.argv[2], float(sys.argv[3])
for _ in range(3):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), val, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
    if p and p.param_id == name:
        print(name, "=", p.param_value); break
else:
    print("FALLO", name)
