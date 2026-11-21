"""Prueba de motores via relays (S7..S10 -> IN1..IN4 del L298N).
Pulsos cortos a velocidad maxima (sin PWM). Al final deja todo en 0.
Uso: python test_motores.py COM4 [segundos_por_paso]
"""
import sys, time
from pymavlink import mavutil

port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
dt = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
m = None
for _ in range(20):
    try:
        m = mavutil.mavlink_connection(port, baud=115200)
        if m.wait_heartbeat(timeout=3):
            break
    except Exception:
        time.sleep(1)

def relay(i, on):
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_DO_SET_RELAY, 0, i, 1 if on else 0, 0, 0, 0, 0, 0)
    ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
    return ack.result if ack else None

def all_off():
    for i in range(4):
        relay(i, False)

# IN1=relay0, IN2=relay1 (motor izq) ; IN3=relay2, IN4=relay3 (motor der)
steps = [("Motor IZQUIERDO adelante (IN1)", 0),
         ("Motor IZQUIERDO atras    (IN2)", 1),
         ("Motor DERECHO adelante   (IN3)", 2),
         ("Motor DERECHO atras      (IN4)", 3)]
try:
    all_off()
    print("Inicio en 3 s...", flush=True); time.sleep(3)
    for name, r in steps:
        res = relay(r, True)
        print("%s  ack=%s" % (name, res), flush=True)
        time.sleep(dt)
        relay(r, False)
        time.sleep(0.7)
finally:
    all_off()
    print("Todo apagado.")
