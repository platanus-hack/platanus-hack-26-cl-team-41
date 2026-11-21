"""Lee parametros por nombre (acepta prefijos con *). Uso: python getp.py COM4 SERVO7_* Q_ENABLE"""
import sys, time, fnmatch
from pymavlink import mavutil

port, pats = sys.argv[1], sys.argv[2:]
m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)
m.mav.param_request_list_send(m.target_system, m.target_component)
params, last = {}, time.time()
while time.time() - last < 3:
    p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
    if p:
        params[p.param_id] = p.param_value
        last = time.time()
for k in sorted(params):
    if any(fnmatch.fnmatch(k, pat) for pat in pats):
        print(k, "=", params[k])
