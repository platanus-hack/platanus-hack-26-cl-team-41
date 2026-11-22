"""Robot "vivo": el brazo se mueve suave mientras espera y reacciona a lo que ve la camara.
   platano -> gesto "si" (asiente y se estira)      cinta -> gesto "no" (sacude y se encoge)

Uso (desde la carpeta vision, con el Python de .venv):
  .venv\\Scripts\\python robot_vivo.py                  # ventana; q = reposo y salir, espacio = pausa, s/n = forzar gesto
  .venv\\Scripts\\python robot_vivo.py --grabar CARPETA --seg 40 --sin-reaccion     # solo idle y guarda cuadros
  .venv\\Scripts\\python robot_vivo.py --dry            # solo deteccion, no mueve el brazo
  python robot_vivo.py --claude         # idle; el que mira y decide es Claude (ver DEMO_SI_NO.md). Sin YOLO ni GPU
"""
import argparse, math, os, random, threading, time
os.environ["MAVLINK20"] = "1"
import cv2
import numpy as np
import gestos
from gestos import DT, REPOSO, LO, HI, suave

ap = argparse.ArgumentParser()
ap.add_argument("--source")
ap.add_argument("--port")
ap.add_argument("--modelo", default="weights/gestos.pt")
ap.add_argument("--conf", type=float, default=0.60)
ap.add_argument("--grabar")
ap.add_argument("--seg", type=float, default=0)
ap.add_argument("--sin-reaccion", action="store_true")
ap.add_argument("--dry", action="store_true")
ap.add_argument("--ordenes", help="archivo de ordenes: si, no, atento, idle, salir (para que decida otro programa)")
ap.add_argument("--sin-ventana", action="store_true")
ap.add_argument("--claude", action="store_true", help="idle + ordenes de claude_demo.py, sin deteccion local")
A = ap.parse_args()
AQUI = os.path.dirname(os.path.abspath(__file__))
IP = os.environ.get("ROVER_IP", "172.16.0.127")
if A.claude:
    os.makedirs(os.path.join(AQUI, "demo_tmp"), exist_ok=True)
    A.sin_reaccion, A.ordenes = True, os.path.join(AQUI, "demo_tmp", "orden.txt")
    if os.path.exists(A.ordenes):
        os.remove(A.ordenes)                   # una orden vieja no debe ejecutarse al partir
ESTADO = os.path.join(AQUI, "demo_tmp", "estado.txt")
A.source = A.source or "http://%s:8080/stream" % IP
A.port = A.port or "udpout:%s:14550" % IP
GESTO = {"platano": "si", "cinta": "no"}
VIDLE = 32.0                                   # grados/s maximos en idle


class Idle:
    """Respira con todos los ejes y cada tanto mira a un lado, como esperando."""
    C = [0.0, -22.0, 54.0, 42.0, 0.0, 0.40]

    def __init__(self):
        self.t = 0.0
        self.prox = 5.0
        self.mirada = None

    def paso(self, dt):
        self.t += dt
        t = self.t

        def w(T, f=0.0):
            return math.sin(2 * math.pi * t / T + f)

        x = [5 * w(7.3) + 2 * w(3.1, 1), 3.0 * w(4.2), 2.5 * w(4.2, 1.3), 5 * w(5.1, .7), 8 * w(6.3, 2), .06 * w(3.7)]
        x = [c + d for c, d in zip(self.C, x)]
        if self.mirada is None and t > self.prox:
            lado = random.choice((-1, 1))
            d = [lado * random.uniform(12, 22), random.uniform(0, 6), random.uniform(-4, 3),
                 random.uniform(-16, -6), -lado * random.uniform(8, 18), random.uniform(.05, .3)]
            self.mirada = (t, random.uniform(2.6, 3.8), d)
        if self.mirada:
            t0, dur, d = self.mirada
            u = (t - t0) / dur
            if u >= 1:
                self.mirada = None
                self.prox = t + random.uniform(3.0, 7.0)
            else:
                k = suave(u / .35) * suave((1 - u) / .35)
                x = [a + k * b for a, b in zip(x, d)]
        x = [min(h, max(l, v)) for v, l, h in zip(x, LO, HI)]
        x[2] = max(x[2], 47.0)                 # en idle el codo no baja de 47: el hombro puede estar atras
        return x


class Brazo(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.x = None
        self.pedido = None
        self.estado = "conectando"
        self.pausa = False
        self.fin = False
        self.a = self.v = self.pico = 0.0
        self.error = None

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.error = str(e)
            self.estado = "ERROR"

    def _run(self):
        from pymavlink import mavutil
        m = mavutil.mavlink_connection(A.port, baud=115200, source_system=255)
        S = dict(rc=None, ok=False, hi=None, ult=time.time())

        def lee(dt):
            fin = time.time() + dt
            while True:
                p = m.recv_match(blocking=True, timeout=max(0.001, fin - time.time()))
                if p and p.get_srcSystem() == 1:
                    S["ult"] = time.time()
                    k = p.get_type()
                    if k == "RC_CHANNELS":
                        S["rc"] = [getattr(p, "chan%d_raw" % i) for i in range(9, 15)]
                    elif k == "SYS_STATUS":
                        self.a, self.v = p.current_battery / 100, p.voltage_battery / 1000
                        self.pico = max(self.pico, self.a)
                        S["hi"] = (S["hi"] or time.time()) if self.a > 2.5 else None
                        if S["hi"] and time.time() - S["hi"] > .6:
                            raise RuntimeError("corriente alta %.2f A" % self.a)
                        if 5 < self.v < 10.2:
                            raise RuntimeError("voltaje bajo %.2f V" % self.v)
                    elif k == "STATUSTEXT" and p.text.startswith("Brazo"):
                        S["ok"] = True
                if time.time() >= fin:
                    return

        for i in range(48):
            m.mav.heartbeat_send(6, 8, 0, 0, 0)
            if i % 6 == 2:
                for mid, us in ((65, 200000), (1, 100000)):
                    m.mav.command_long_send(1, 1, 511, 0, mid, us, 0, 0, 0, 0, 0)
            lee(.25)
            if i > 8 and S["ok"] and S["rc"]:
                break
        if not S["ok"] or S["rc"] is None:
            raise RuntimeError("la H743 o el script del brazo no responden")
        # otro PC mandando el brazo a la vez = dos ordenes peleando: si la orden cambia sola, no partir
        vistas = set()
        for _ in range(8):
            m.mav.heartbeat_send(6, 8, 0, 0, 0)
            lee(.25)
            vistas.add(tuple(S["rc"]))
        if len(vistas) > 1:
            raise RuntimeError("otro programa esta moviendo el brazo; cierralo antes")
        rc = S["rc"]
        if min(rc) >= 900:
            self.x = [(v - 1500) / 5 for v in rc[:5]] + [(rc[5] - 1000) / 1000]
        else:
            self.x = [0, -30, 60, 50, 0, .4]
        idle = Idle()
        tr = None
        n, t0, vel = 0, time.time(), 0.0
        while True:
            if self.fin and self.estado != "saliendo":
                tr = gestos.trayectoria("reposo", self.x)
                self.estado = "saliendo"
            if self.pedido and (tr is None or self.estado == "atento") and not self.fin:
                g, self.pedido = self.pedido, None
                if g == "idle":
                    tr, vel, self.estado = None, 0.0, "idle"
                    continue
                tr = gestos.trayectoria(g, self.x)
                self.estado = g
            if tr is not None:
                sig = next(tr, None)
                if sig is None:
                    tr, vel = None, 0.0
                    if self.fin:
                        break
                    self.estado = "idle"
                    continue
                self.x = list(sig[1])
            elif not self.pausa:
                self.estado = "idle"
                obj = idle.paso(DT)
                vel = min(VIDLE, vel + 20 * DT)            # entra de a poco
                for i in range(6):
                    lim = vel * DT if i < 5 else .8 * DT
                    self.x[i] += max(-lim, min(lim, obj[i] - self.x[i]))
            else:
                self.estado = "pausa"
            ch = [int(round(1500 + v * 5)) for v in self.x[:5]] + [int(round(1000 + self.x[5] * 1000))]
            m.mav.rc_channels_override_send(1, 1, *([65535] * 8), *ch, *([0] * 4))
            if n % 10 == 0:
                m.mav.heartbeat_send(6, 8, 0, 0, 0)
            if n % 400 == 0:
                m.mav.command_long_send(1, 1, 511, 0, 1, 100000, 0, 0, 0, 0, 0)
            if time.time() - S["ult"] > 5:
                raise RuntimeError("se perdio el enlace con la H743")
            n += 1
            lee(max(0.0, t0 + n * DT - time.time()))
            if time.time() - (t0 + n * DT) > .3:
                t0 = time.time() - n * DT                  # no recuperar el tiempo perdido a saltos
        self.estado = "fuera"


class Video(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.f, self.n, self.vivo = None, 0, True

    def run(self):
        while self.vivo:
            cap = cv2.VideoCapture(A.source)
            while self.vivo:
                ok, f = cap.read()
                if not ok:
                    break
                self.f, self.n = f, self.n + 1
            cap.release()
            time.sleep(.5)


def main():
    vid = Video()
    vid.start()
    model = None
    if not A.sin_reaccion:
        from ultralytics import YOLO
        model = YOLO(A.modelo)
        model.predict(np.zeros((640, 640, 3), "uint8"), verbose=False)     # calienta
    brazo = Brazo()
    if not A.dry:
        brazo.start()
    if A.grabar:
        os.makedirs(A.grabar, exist_ok=True)
    hist, armado, sin_ver = [], True, 0
    t0, ult, kg, tg = time.time(), -1, 0, 0.0
    ver = not A.sin_ventana
    if ver:
        cv2.namedWindow("robot vivo", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("robot vivo", 960, 540)
    print("listo", flush=True)
    te = 0.0

    def anota(txt):
        if A.claude:
            try:
                open(ESTADO, "w", encoding="utf8").write(txt)
            except OSError:
                pass

    try:
        while not (A.seg and time.time() - t0 > A.seg):
            if time.time() - te > .2:
                te = time.time()
                anota("%s | %.2f A %.1f V" % (brazo.estado, brazo.a, brazo.v))
            if brazo.error:
                print("ERROR:", brazo.error, flush=True)
                break
            if A.ordenes and os.path.exists(A.ordenes):
                try:
                    o = open(A.ordenes).read().strip()
                    os.remove(A.ordenes)
                except OSError:
                    o = ""
                if o == "salir":
                    break
                if o in ("si", "no", "atento", "idle"):
                    print("%.1fs orden %s" % (time.time() - t0, o), flush=True)
                    brazo.pedido = o
            if vid.f is None or vid.n == ult:
                time.sleep(.004)
                continue
            ult, f = vid.n, vid.f
            if A.grabar and time.time() - tg > .25:
                tg = time.time()
                cv2.imwrite("%s/%04d.jpg" % (A.grabar, kg), f)
                kg += 1
            vista = f.copy() if ver else f
            if model is not None:
                mejor = None
                for b in model.predict(f, conf=.3, verbose=False)[0].boxes:
                    c, nom = float(b.conf), model.names[int(b.cls)]
                    if c >= A.conf and (mejor is None or c > mejor[0]):
                        mejor = (c, nom)
                    if ver:
                        x1, y1, x2, y2 = [int(v) for v in b.xyxy[0]]
                        col = (0, 255, 255) if nom == "platano" else (255, 160, 0)
                        cv2.rectangle(vista, (x1, y1), (x2, y2), col, 4 if c >= A.conf else 2)
                        cv2.putText(vista, "%s %.0f%%" % (nom, 100 * c), (x1, max(24, y1 - 8)), 0, .9, col, 2)
                hist = (hist + [mejor[1] if mejor else None])[-6:]
                sin_ver = 0 if mejor else sin_ver + 1
                libre = A.dry or brazo.estado == "idle"
                if sin_ver > 20 and libre:
                    armado = True                          # el objeto se fue: puede volver a reaccionar
                for nom, g in GESTO.items():
                    if armado and libre and hist.count(nom) >= 4:
                        print("%.1fs veo %s -> %s" % (time.time() - t0, nom, g), flush=True)
                        brazo.pedido, armado, hist = g, False, []
            if ver:
                txt = "%s  %.2fA %.1fV%s" % (brazo.estado, brazo.a, brazo.v, "" if armado else "  (quita el objeto para repetir)")
                cv2.putText(vista, txt, (12, vista.shape[0] - 20), 0, .9, (0, 255, 0), 2)
                cv2.imshow("robot vivo", vista)
                k = cv2.waitKey(1) & 255
                if k in (ord("q"), 27) or cv2.getWindowProperty("robot vivo", cv2.WND_PROP_VISIBLE) < 1:
                    break
                if k == ord(" "):
                    brazo.pausa = not brazo.pausa
                if k in (ord("s"), ord("n")):
                    brazo.pedido = "si" if k == ord("s") else "no"
    except KeyboardInterrupt:
        pass
    brazo.fin = True
    if not A.dry and brazo.is_alive():
        brazo.join(30)
    vid.vivo = False
    if ver:
        cv2.destroyAllWindows()
    anota("ERROR: " + brazo.error if brazo.error else "fuera")
    print("fin: estado %s, max %.2f A, %.1f V, cuadros %d" % (brazo.estado, brazo.pico, brazo.v, kg), flush=True)


if __name__ == "__main__":
    main()
