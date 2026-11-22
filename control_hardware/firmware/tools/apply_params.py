"""Respalda todos los parametros y aplica un archivo .param (formato NOMBRE,VALOR).
Uso: python apply_params.py COM4 ../estabilizador_S2_S3.param [--reboot]
"""
import sys, time, datetime, os
from pymavlink import mavutil

port, pfile = sys.argv[1], sys.argv[2]
reboot = "--reboot" in sys.argv
m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)

# --- respaldo ---
m.mav.param_request_list_send(m.target_system, m.target_component)
params, total = {}, None
last = time.time()
while time.time() - last < 3:
    p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
    if p:
        params[p.param_id] = p.param_value
        total = p.param_count
        last = time.time()
os.makedirs("../backups", exist_ok=True)
bk = "../backups/params_%s.param" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
with open(bk, "w") as f:
    for k in sorted(params):
        f.write("%s,%s\n" % (k, repr(params[k])))
print("respaldo: %d/%s parametros -> %s" % (len(params), total, bk))

# --- aplicar ---
missing = []
for line in open(pfile, encoding="utf-8"):
    line = line.split("#")[0].strip()
    if not line:
        continue
    name, val = [x.strip() for x in line.split(",")]
    val = float(val)
    ok = False
    for _ in range(3):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), val,
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        end = time.time() + 1.5
        while time.time() < end:
            p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
            if p and p.param_id == name:
                ok = abs(p.param_value - val) < 1e-3
                break
        if ok:
            break
    print("%-18s %-8s %s" % (name, val, "OK" if ok else "FALTA/NO EXISTE"))
    if not ok:
        missing.append(name)

if reboot:
    time.sleep(3)  # dar tiempo a que se guarden en flash
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0, 1, 0, 0, 0, 0, 0, 0)
    print("reboot enviado")
print("pendientes:", missing)
