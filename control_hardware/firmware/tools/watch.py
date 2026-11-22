"""Muestra roll/pitch de la placa y el PWM de S2/S3 en vivo.
Uso: python watch.py COM4 [segundos]
"""
import sys, time, math
from pymavlink import mavutil

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
dur = float(sys.argv[2]) if len(sys.argv) > 2 else 20
m = None
for _ in range(20):
    try:
        m = mavutil.mavlink_connection(port, baud=115200)
        if m.wait_heartbeat(timeout=3):
            break
    except Exception:
        time.sleep(1)
for sid in (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, mavutil.mavlink.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW,
            mavutil.mavlink.MAVLINK_MSG_ID_MOUNT_STATUS if hasattr(mavutil.mavlink, "MAVLINK_MSG_ID_MOUNT_STATUS") else 158):
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, sid, 100000, 0, 0, 0, 0, 0)
roll = pitch = 0.0
s2 = s3 = 0
end = time.time() + dur
last = 0
while time.time() < end:
    msg = m.recv_match(type=["ATTITUDE", "SERVO_OUTPUT_RAW", "STATUSTEXT"], blocking=True, timeout=1)
    if not msg:
        continue
    t = msg.get_type()
    if t == "ATTITUDE":
        roll, pitch = math.degrees(msg.roll), math.degrees(msg.pitch)
    elif t == "SERVO_OUTPUT_RAW" and msg.port == 0:
        s2, s3 = msg.servo2_raw, msg.servo3_raw
    elif t == "STATUSTEXT":
        print("MSG:", msg.text)
    if time.time() - last > 0.25:
        last = time.time()
        print("roll %+6.1f  pitch %+6.1f  |  S2 %4d  S3 %4d" % (roll, pitch, s2, s3), flush=True)
