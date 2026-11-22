"""Dispara la rampa de rampa_motores.lua y muestra el PWM de S7..S10 en vivo.
Uso: python rampa.py COM4 [adelante|atras]
"""
import sys, time
from pymavlink import mavutil

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
direction = -1.0 if (len(sys.argv) > 2 and sys.argv[2].startswith("atr")) else 1.0
PERIOD_US = 1e6 / 490

m = mavutil.mavlink_connection(port, baud=115200)
m.wait_heartbeat(timeout=10)
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                        0, mavutil.mavlink.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW, 100000, 0, 0, 0, 0, 0)
m.mav.param_set_send(m.target_system, m.target_component, b"SCR_USER1", direction,
                     mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
print("SCR_USER1 =", direction)

end = time.time() + 15
last = 0
done = False
while time.time() < end and not done:
    msg = m.recv_match(type=["SERVO_OUTPUT_RAW", "STATUSTEXT"], blocking=True, timeout=1)
    if not msg:
        continue
    if msg.get_type() == "STATUSTEXT":
        if not msg.text.startswith("PreArm"):
            print("FC:", msg.text, flush=True)
        if msg.text.startswith("Rampa: fin"):
            done = True
    elif msg.port == 0 and time.time() - last > 0.5:
        last = time.time()
        vals = [msg.servo7_raw, msg.servo8_raw, msg.servo9_raw, msg.servo10_raw]
        print("   S7 %4d (%3.0f%%)  S8 %4d  S9 %4d (%3.0f%%)  S10 %4d" % (
            vals[0], 100 * vals[0] / PERIOD_US, vals[1], vals[2], 100 * vals[2] / PERIOD_US, vals[3]), flush=True)
if not done:
    print("No llego el mensaje de fin. Revisa que el script este cargado (SD en la placa, SCR_ENABLE=1).")
