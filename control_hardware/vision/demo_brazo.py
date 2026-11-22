"""Demo del brazo: se levanta, saluda, mira a los lados, abre y cierra la pinza, se inclina y vuelve al reposo.

Movimientos suaves (maximo ~40 grados/s), de a una articulacion. Parte y termina en la postura de reposo.
Uso: python demo_brazo.py [--port COM4 | udpout:172.16.0.127:14550] [--espera 5]
Se detiene (el brazo se queda quieto donde esta) con Ctrl+C, con corriente alta sostenida o con voltaje bajo.
"""
import argparse, math, time

REST = [0.0, -30.0, 60.0, 50.0, 0.0]        # base, hombro, codo, muneca, giro
GRIP0 = 0.4
VMAX = 40.0                                  # grados/s en la mitad del movimiento
BASE, HOMBRO, CODO, MUNECA, GIRO, PINZA = range(6)

# (articulacion, destino) o ("pausa", segundos). Pinza: 0 cerrada .. 1 abierta (lejos de los topes)
DEMO = [
    ("# se levanta", 0), (HOMBRO, -5), (MUNECA, 10), (CODO, 50), (HOMBRO, 10), (MUNECA, -10), ("pausa", 0.4),
    ("# saluda", 0), (BASE, 25), (BASE, -25), (BASE, 25), (BASE, 0), ("pausa", 0.3),
    ("# abre y cierra la pinza", 0), (PINZA, 0.85), (PINZA, 0.2), (PINZA, 0.85), (PINZA, 0.2), (PINZA, 0.4),
    ("# gira la pinza", 0), (GIRO, 35), (GIRO, -35), (GIRO, 0), ("pausa", 0.3),
    ("# mira a los lados", 0), (BASE, 45), (MUNECA, 30), (MUNECA, -10), (BASE, -45), (MUNECA, 30), (MUNECA, -10), (BASE, 0),
    ("# reverencia", 0), (MUNECA, 40), (HOMBRO, 25), ("pausa", 0.8), (HOMBRO, 10), (MUNECA, -10), ("pausa", 0.4),
    ("# vuelve al reposo", 0), (MUNECA, 10), (HOMBRO, -5), (CODO, 60), (MUNECA, 50), (HOMBRO, -30),
]


def trayectoria(dt=0.05):
    """Genera (etiqueta, postura[5], pinza) cada dt segundos."""
    x = list(REST) + [GRIP0]
    tag = ""
    for j, v in DEMO:
        if isinstance(j, str):
            if j.startswith("#"):
                tag = j[2:]
            else:
                for _ in range(int(v / dt)):
                    yield tag, x[:5], x[5]
            continue
        a = x[j]
        escala = 0.6 if j == PINZA else 1.0      # pinza en 0..1: recorrido completo en ~1 s
        dist = abs(v - a) if j != PINZA else abs(v - a) * 40
        n = max(2, int(math.ceil(dist * math.pi / 2 / (VMAX * escala) / dt)))
        for i in range(1, n + 1):
            x[j] = a + (v - a) * (1 - math.cos(math.pi * i / n)) / 2
            yield tag, x[:5], x[5]
        for _ in range(3):
            yield tag, x[:5], x[5]


def correr(trayectoria, dt=0.05, max_a=2.5):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM4")
    ap.add_argument("--espera", type=float, default=5.0)
    ap.add_argument("--max-a", type=float, default=max_a)
    ap.add_argument("--min-v", type=float, default=10.8)
    a = ap.parse_args()
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(a.port, baud=115200, source_system=255)
    for _ in range(3):
        m.mav.heartbeat_send(6, 8, 0, 0, 0); time.sleep(0.2)
    if not m.wait_heartbeat(timeout=10):
        raise SystemExit("La H743 no responde por %s" % a.port)

    # partir solo si el brazo esta comandado al reposo (lo dice el estado que manda el script de la placa)
    t, ok = time.time(), False
    while time.time() - t < 6 and not ok:
        s = m.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
        ok = bool(s and s.text.startswith("Brazo b0.0 h-30.0 c60.0 m50.0 g0.0"))
    if not ok:
        raise SystemExit("El brazo no esta en la postura de reposo: llevarlo primero ahi")

    print("Empieza en %.0f s: despejar la zona" % a.espera, flush=True)
    time.sleep(a.espera)
    alto, imax, vmin, tag0 = None, 0.0, 99.0, ""
    prox = time.time()
    try:
        for tag, pose, grip in trayectoria():
            if tag != tag0:
                print(tag, flush=True); tag0 = tag
            ch = [int(round(1500 + p * 5)) for p in pose] + [int(round(1000 + grip * 1000))]
            m.mav.rc_channels_override_send(m.target_system, m.target_component, *([65535] * 8), *ch)
            m.mav.heartbeat_send(6, 8, 0, 0, 0)
            while True:
                s = m.recv_match(type="SYS_STATUS", blocking=False)
                if not s:
                    break
                i, v = s.current_battery / 100, s.voltage_battery / 1000
                imax, vmin = max(imax, i), min(vmin, v)
                alto = (alto or time.time()) if i > a.max_a else None
                if (alto and time.time() - alto > 0.4) or v < a.min_v:
                    print("DETENIDO: %.2f A, %.2f V. El brazo se queda quieto." % (i, v)); return
            prox += dt
            time.sleep(max(0.0, prox - time.time()))
            prox = max(prox, time.time() - dt)
    except KeyboardInterrupt:
        print("Detenido: el brazo se queda quieto"); return
    print("Fin. Corriente max %.2f A, voltaje min %.2f V" % (imax, vmin))


if __name__ == "__main__":
    correr(trayectoria)
