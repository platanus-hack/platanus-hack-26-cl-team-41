"""Prueba MAVLink Radxa <-> H743 por UART.
1) H743 -> Radxa: espera HEARTBEAT.
2) Radxa -> H743: pide un parametro y espera la respuesta.
Uso: python3 test_mavlink_h743.py [/dev/ttyS5] [baud...]
"""
import os, sys, time
os.environ["MAVLINK20"] = "1"   # ArduPilot responde en MAVLink 2; con MAVLink 1 no contestaba
sys.path.insert(0, "/var/tmp/packages")
from pymavlink import mavutil

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyS5"
bauds = [int(b) for b in sys.argv[2:]] or [115200, 57600, 921600]

for baud in bauds:
    print("== %s @ %d ==" % (port, baud), flush=True)
    m = mavutil.mavlink_connection(port, baud=baud, source_system=254, source_component=191)
    t0 = time.time(); nbytes = 0; hb = None
    while time.time() - t0 < 4:
        msg = m.recv_match(blocking=True, timeout=0.5)
        if msg is None:
            continue
        if msg.get_type() == "HEARTBEAT" and msg.get_srcSystem() != 254:
            hb = msg
            break
    if not hb:
        print("  H743 -> Radxa: SIN heartbeat")
        m.close()
        continue
    print("  H743 -> Radxa: OK (sysid %d, tipo %d, autopilot %d)" % (hb.get_srcSystem(), hb.type, hb.autopilot))
    m.target_system, m.target_component = hb.get_srcSystem(), hb.get_srcComponent()
    ok = False
    for _ in range(3):
        m.mav.param_request_read_send(m.target_system, m.target_component, b"SERIAL2_BAUD", -1)
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1.5)
        if p:
            print("  Radxa -> H743: OK (SERIAL2_BAUD = %s)" % p.param_value)
            ok = True
            break
    if not ok:
        print("  Radxa -> H743: SIN respuesta (revisar cable Radxa TX -> H743 RX1)")
    m.close()
    break
