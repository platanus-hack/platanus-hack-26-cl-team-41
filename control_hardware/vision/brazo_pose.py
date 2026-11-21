"""Manda una postura al brazo por WiFi (puente MAVLink de la Pi) y saca una foto de la camara.
Uso: .venv\\Scripts\\python brazo_pose.py BASE HOMBRO CODO MUNECA [GIRO] [--foto archivo.jpg] [--espera 3]
La H743 (brazo_estable.lua) limita la velocidad a 60 grados/s y mantiene la postura cuando el programa termina.
"""
import argparse, time, urllib.request
from pymavlink import mavutil

PI = "172.16.0.127"


def conectar():
    m = mavutil.mavlink_connection("udpout:%s:14550" % PI, source_system=255)
    for _ in range(3):
        m.mav.heartbeat_send(6, 8, 0, 0, 0); time.sleep(0.2)
    if not m.wait_heartbeat(timeout=8):
        raise SystemExit("La H743 no responde por WiFi")
    return m


def enviar(m, pose, grip=0.4, segundos=2.0):
    ch = [int(round(1500 + max(-100, min(100, p)) * 5)) for p in pose] + [int(round(1000 + grip * 1000))]
    t = time.time()
    while time.time() - t < segundos:
        m.mav.rc_channels_override_send(m.target_system, m.target_component, *([65535] * 8), *ch)
        m.mav.heartbeat_send(6, 8, 0, 0, 0)
        time.sleep(0.05)


def foto(path):
    urllib.request.urlretrieve("http://%s:8080/snapshot" % PI, path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pose", type=float, nargs="+")
    ap.add_argument("--foto")
    ap.add_argument("--espera", type=float, default=3.0)
    a = ap.parse_args()
    pose = (a.pose + [0.0])[:5]
    m = conectar()
    enviar(m, pose, segundos=a.espera)
    print("postura enviada:", pose)
    if a.foto:
        foto(a.foto); print("foto:", a.foto)
