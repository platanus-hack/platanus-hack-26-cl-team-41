"""Muestra firmware, version y parametros clave de la placa ArduPilot."""
import sys, time
from pymavlink import mavutil

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
m = mavutil.mavlink_connection(port, baud=115200)
hb = m.wait_heartbeat(timeout=10)
if not hb:
    sys.exit("Sin heartbeat")
types = {1: "Plane", 2: "Copter(quad)", 10: "Rover(ground)", 11: "Boat", 26: "Gimbal"}
print("vehicle type:", hb.type, types.get(hb.type, "?"), "autopilot:", hb.autopilot)
m.mav.command_long_send(m.target_system, m.target_component,
                        mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
                        mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION, 0, 0, 0, 0, 0, 0)
end = time.time() + 5
while time.time() < end:
    msg = m.recv_match(type=["AUTOPILOT_VERSION", "STATUSTEXT"], blocking=True, timeout=1)
    if not msg:
        continue
    if msg.get_type() == "AUTOPILOT_VERSION":
        v = msg.flight_sw_version
        print("fw version: %d.%d.%d" % (v >> 24 & 0xFF, v >> 16 & 0xFF, v >> 8 & 0xFF), "board id:", msg.board_version >> 16)
        break
    else:
        print("STATUSTEXT:", msg.text)

for name in ["MNT1_TYPE", "SERVO2_FUNCTION", "SERVO3_FUNCTION", "MNT1_DEFLT_MODE", "BRD_SAFETY_DEFLT",
             "SCR_ENABLE", "INS_ACC_ID", "AHRS_ORIENTATION"]:
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=2)
    print(name, "=", p.param_value if p else "(no existe)")
