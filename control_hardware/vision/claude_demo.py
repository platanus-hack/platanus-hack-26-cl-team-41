"""Herramientas para que un Claude haga la demo si/no (ver DEMO_SI_NO.md). Solo necesita Python y opencv.

  python claude_demo.py revisar         revisa dependencias, camara y enlace; no mueve nada
  python claude_demo.py foto            saca una foto de la camara -> demo_tmp/foto.jpg (para mirarla)
  python claude_demo.py gesto si        manda el gesto y espera a que termine (si | no | atento)
  python claude_demo.py estado          que esta haciendo el robot
  python claude_demo.py salir           el brazo vuelve al reposo y termina robot_vivo.py
Antes tiene que estar corriendo:  python robot_vivo.py --claude
La direccion de la Pi se puede cambiar con la variable de entorno ROVER_IP.
"""
import os, sys, time, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(AQUI, "demo_tmp")
IP = os.environ.get("ROVER_IP", "172.16.0.127")
FOTO, ORDEN, ESTADO = (os.path.join(TMP, n) for n in ("foto.jpg", "orden.txt", "estado.txt"))


def estado():
    """(texto, segundos desde la ultima actualizacion) o (None, None) si robot_vivo.py no esta corriendo"""
    try:
        edad = time.time() - os.path.getmtime(ESTADO)
        return open(ESTADO, encoding="utf8").read().strip(), edad
    except OSError:
        return None, None


def corriendo():
    e, edad = estado()
    return e is not None and edad < 5 and not e.startswith(("fuera", "ERROR"))


def foto():
    datos = urllib.request.urlopen("http://%s:8080/snapshot" % IP, timeout=5).read()
    os.makedirs(TMP, exist_ok=True)
    open(FOTO, "wb").write(datos)
    return FOTO


def orden(o):
    open(ORDEN + ".tmp", "w").write(o)
    os.replace(ORDEN + ".tmp", ORDEN)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "revisar":
        mal = 0
        for mod, pip in (("cv2", "opencv-python"), ("numpy", "numpy"), ("pymavlink", "pymavlink")):
            try:
                __import__(mod)
                print("OK   ", mod)
            except ImportError:
                print("FALTA", mod, "-> pip install", pip)
                mal = 1
        try:
            print("OK    camara:", foto())
        except Exception as e:
            print("FALLA camara en http://%s:8080 (%s). Estas en la red PlatanusHack? Esta encendida la Pi?" % (IP, e))
            mal = 1
        if not mal:
            os.environ["MAVLINK20"] = "1"
            from pymavlink import mavutil
            m = mavutil.mavlink_connection("udpout:%s:14550" % IP, source_system=254)
            t, ok, brazo = time.time(), False, ""
            while time.time() - t < 8 and not (ok and brazo):
                m.mav.heartbeat_send(6, 8, 0, 0, 0)
                x = m.recv_match(type=["HEARTBEAT", "STATUSTEXT"], blocking=True, timeout=.5)
                if x and x.get_srcSystem() == 1:
                    ok = ok or x.get_type() == "HEARTBEAT"
                    if x.get_type() == "STATUSTEXT" and x.text.startswith("Brazo"):
                        brazo = x.text
            print("OK    H743" if ok else "FALLA H743: no responde por udp %s:14550" % IP)
            print("OK    script del brazo: " + brazo if brazo else "FALLA script del brazo: no reporta")
            mal = not (ok and brazo)
        e, edad = estado()
        print("robot_vivo.py:", "corriendo (%s)" % e if corriendo() else "no esta corriendo")
        sys.exit(1 if mal else 0)
    if cmd == "foto":
        try:
            print(foto(), "| robot:", estado()[0] if corriendo() else "robot_vivo.py NO esta corriendo")
        except Exception as e:
            sys.exit("sin camara: %s" % e)
    elif cmd == "estado":
        print(estado()[0] if corriendo() else "robot_vivo.py NO esta corriendo")
    elif cmd == "gesto" and len(sys.argv) > 2 and sys.argv[2] in ("si", "no", "atento"):
        if not corriendo():
            sys.exit("robot_vivo.py no esta corriendo: lanzalo con  python robot_vivo.py --claude")
        orden(sys.argv[2])
        t, empezo = time.time(), False
        while time.time() - t < 30:
            time.sleep(.2)
            if not corriendo():
                sys.exit("robot_vivo.py se detuvo: %s" % (estado()[0] or ""))
            e = estado()[0].split("|")[0].strip()
            empezo = empezo or e == sys.argv[2]
            if empezo and e == "idle":
                print("gesto %s terminado en %.1f s" % (sys.argv[2], time.time() - t))
                return
        sys.exit("el gesto no termino a tiempo: %s" % estado()[0])
    elif cmd == "salir":
        orden("salir")
        t = time.time()
        while corriendo() and time.time() - t < 20:
            time.sleep(.3)
        print("robot en reposo" if not corriendo() else "sigue corriendo: cierra la ventana con q")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
