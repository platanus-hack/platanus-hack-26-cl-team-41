"""Muestra roll/pitch y pulsos S1..S6 + mensajes del script. Uso: python watch_brazo.py COM4 [segundos]"""
import sys, time, math
from pymavlink import mavutil
port=sys.argv[1]; dur=float(sys.argv[2]) if len(sys.argv)>2 else 15
for _ in range(30):
    try:
        m=mavutil.mavlink_connection(port,baud=115200); m.wait_heartbeat(timeout=5); break
    except Exception: time.sleep(1)
m.mav.request_data_stream_send(m.target_system,m.target_component,mavutil.mavlink.MAV_DATA_STREAM_ALL,5,1)
t0=time.time(); att=None; last=0
while time.time()-t0<dur:
    msg=m.recv_match(type=["ATTITUDE","SERVO_OUTPUT_RAW","STATUSTEXT"],blocking=True,timeout=1)
    if not msg: continue
    t=msg.get_type()
    if t=="ATTITUDE": att=msg
    elif t=="STATUSTEXT" and "PreArm" not in msg.text: print("  >", msg.text)
    elif t=="SERVO_OUTPUT_RAW" and att and time.time()-last>1:
        last=time.time()
        print(f"roll {math.degrees(att.roll):6.1f}  pitch {math.degrees(att.pitch):6.1f} | S1 pinza {msg.servo1_raw} S2 base {msg.servo2_raw} S3 hom {msg.servo3_raw} S4 codo {msg.servo4_raw} S5 mun {msg.servo5_raw} S6 giro {msg.servo6_raw}")
