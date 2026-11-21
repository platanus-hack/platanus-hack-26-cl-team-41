"""Muestra S7..S10 por N segundos. Opcional: 'stopscript' detiene scripting primero, 'restart' lo reinicia."""
import sys, time
from pymavlink import mavutil
m=mavutil.mavlink_connection(sys.argv[1],baud=115200); m.wait_heartbeat(timeout=10)
if "stopscript" in sys.argv:
    m.mav.command_long_send(m.target_system,m.target_component,42701,0,1,0,0,0,0,0,0)  # STOP
if "restart" in sys.argv:
    m.mav.command_long_send(m.target_system,m.target_component,42701,0,3,0,0,0,0,0,0)  # STOP_AND_RESTART
m.mav.command_long_send(m.target_system,m.target_component,mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,0,mavutil.mavlink.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW,200000,0,0,0,0,0)
end=time.time()+float(sys.argv[2]); last=0
while time.time()<end:
    x=m.recv_match(type=["SERVO_OUTPUT_RAW","STATUSTEXT"],blocking=True,timeout=1)
    if not x: continue
    if x.get_type()=="STATUSTEXT":
        if not x.text.startswith("PreArm"): print("FC:",x.text)
    elif x.port==0 and time.time()-last>1:
        last=time.time(); print("S7 %d S8 %d S9 %d S10 %d"%(x.servo7_raw,x.servo8_raw,x.servo9_raw,x.servo10_raw),flush=True)
