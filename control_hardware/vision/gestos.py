"""Gestos del brazo con todos los ejes: "no" (sacude y se encoge) y "si" (asiente y se estira).

Uso:  python gestos.py si|no|reposo [--port udpout:172.16.0.127:14550 | COM4]     (python del sistema)
Parte desde donde este el brazo y termina en reposo. Ningun eje pasa de ~52 grados/s (la placa limita a 60).
Corta (el brazo se queda quieto) con Ctrl+C, corriente alta sostenida o voltaje bajo.
"""
import argparse, math, os, sys, time
os.environ["MAVLINK20"] = "1"

DT = 0.025
REPOSO = [0.0, -30.0, 46.0, 50.0, 0.0, 0.40]       # base, hombro, codo, muneca, giro, pinza (0..1)
LO = [-50, -30, 30, -25, -50, 0.05]
HI = [50, 40, 83, 74, 50, 0.95]
VMAX = 52.0


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


def mezcla(a, b, k):
    return [p + (q - p) * k for p, q in zip(a, b)]


def s(t, T, f=0.0):
    return math.sin(2 * math.pi * t / T + f)


def gesto_no():
    """(duracion, centro_ini, centro_fin, funcion de oscilacion)"""
    alerta = [0, -8, 58, 22, 0, 0.75]
    encogido = [0, -30, 80, 70, 0, 0.10]
    escondido = [24, -30, 82, 72, -28, 0.08]
    return [
        ("mira", 1.3, None, alerta, None),
        ("no, no, no", 6.9, alerta, encogido,
         lambda t: [16.5 * s(t, 2.3), 3 * s(t, 1.15), -3 * s(t, 1.15, 1.2), 7 * s(t, 1.15), -17 * s(t, 2.3, 0.5), 0.0]),
        ("se esconde", 1.3, encogido, escondido, None),
        ("tiembla", 1.6, escondido, escondido, lambda t: [2.5 * s(t, 0.4), 0, 0, 2.2 * s(t, 0.4, 1), 3 * s(t, 0.4, 2), 0.0]),
        ("vuelve", 2.2, escondido, REPOSO, None),
    ]


def gesto_si():
    alerta = [0, -6, 60, 30, 0, 0.45]
    feliz = [0, 2, 52, 22, 0, 0.75]
    estirado = [0, 8, 31, -8, 0, 0.92]
    return [
        ("mira", 1.3, None, alerta, None),
        ("si, si, si", 6.0, alerta, feliz,
         lambda t: [9 * s(t, 4.0), 7 * s(t, 2.0), -5 * s(t, 2.0), 13 * s(t, 2.0), 13 * s(t, 3.0), 0.12 * s(t, 1.0)]),
        ("se estira", 2.0, feliz, estirado, None),
        ("celebra", 4.6, estirado, estirado,
         lambda t: [20 * s(t, 3.7), 3 * s(t, 1.6), 0.0, 9 * s(t, 1.6, 1.5), 22 * s(t, 3.7, 0.6), -0.28 + 0.28 * s(t, 1.2, 1.57)]),
        ("se recoge", 1.8, estirado, [0, -8, 50, 25, 0, 0.6], None),
        ("vuelve", 1.6, [0, -8, 50, 25, 0, 0.6], REPOSO, None),
    ]


def gesto_atento():
    """Algo aparecio: se inclina hacia adelante y lo mira con curiosidad (mientras se decide que es)."""
    a = [0, -12, 56, 24, 12, 0.65]
    return [
        ("atento", 0.9, None, a, None),
        ("curioso", 7.0, a, [0, -8, 58, 22, -10, 0.55],
         lambda t: [6 * s(t, 3.1), 2 * s(t, 2.3), 0.0, 6 * s(t, 2.0), 11 * s(t, 2.6), 0.1 * s(t, 0.9)]),
    ]


GESTOS = {"no": gesto_no, "si": gesto_si, "atento": gesto_atento, "reposo": lambda: [("reposo", 2.5, None, REPOSO, None)]}


def trayectoria(nombre, actual):
    for tag, T, a, b, osc in GESTOS[nombre]():
        a = list(actual) if a is None else a
        # tramo desde una postura cualquiera: se alarga si hiciera falta para no pasar VMAX
        T = max(T, 1.9 * max(abs(p - q) for p, q in zip(a[:5], b[:5])) / VMAX)
        n = int(T / DT)
        for i in range(1, n + 1):
            t = i * DT
            x = mezcla(a, b, suave(t / T))
            if osc:
                env = suave(t / 0.7) * suave((T - t) / 0.7)
                x = [c + env * d for c, d in zip(x, osc(t))]
            x = [min(h, max(l, v)) for v, l, h in zip(x, LO, HI)]
            if x[2] < 46.0:                      # con el codo estirado el hombro no puede ir atras (varilla de la camara)
                x[1] = max(x[1], -12.0)
            if x[1] < -12.5:
                x[2] = max(x[2], 46.0)
            yield tag, x
    return


def main():
    from pymavlink import mavutil
    ap = argparse.ArgumentParser()
    ap.add_argument("gesto", choices=sorted(GESTOS))
    ap.add_argument("--port", default="udpout:172.16.0.127:14550")
    ap.add_argument("--max-a", type=float, default=2.5)
    g = ap.parse_args()
    m = mavutil.mavlink_connection(g.port, baud=115200, source_system=255)
    S = dict(rc=None, a=0.0, v=0.0, ok=False); pico = 0.0; hi = None

    def lee(dt):
        nonlocal pico, hi
        fin = time.time() + dt
        while True:
            x = m.recv_match(blocking=True, timeout=max(0.001, fin - time.time()))
            if x and x.get_srcSystem() == 1:
                k = x.get_type()
                if k == "RC_CHANNELS":
                    S["rc"] = [getattr(x, "chan%d_raw" % i) for i in range(9, 15)]
                elif k == "SYS_STATUS":
                    S["a"], S["v"] = x.current_battery / 100, x.voltage_battery / 1000
                    pico = max(pico, S["a"])
                    hi = (hi or time.time()) if S["a"] > g.max_a else None
                    if hi and time.time() - hi > 0.6:
                        raise SystemExit("CORTE: corriente alta %.2f A" % S["a"])
                    if 5 < S["v"] < 10.2:
                        raise SystemExit("CORTE: voltaje bajo %.2f V" % S["v"])
                elif k == "STATUSTEXT" and x.text.startswith("Brazo"):
                    S["ok"] = True
            if time.time() >= fin:
                return

    for i in range(40):                                        # despierta el puente y pide datos
        if i > 10 and S["ok"] and S["rc"]:
            break
        m.mav.heartbeat_send(6, 8, 0, 0, 0)
        if i % 6 == 2:
            for mid, us in ((65, 200000), (1, 100000)):
                m.mav.command_long_send(1, 1, 511, 0, mid, us, 0, 0, 0, 0, 0)
        lee(0.25)
    if not S["ok"] or S["rc"] is None:
        raise SystemExit("La H743 o el script del brazo no responden")
    rc = S["rc"]
    actual = [(v - 1500) / 5 for v in rc[:5]] + [(rc[5] - 1000) / 1000] if min(rc) >= 900 else [0, -30, 60, 50, 0, 0.4]
    tag0, t0, n = "", time.time(), 0
    for tag, x in trayectoria(g.gesto, actual):
        if tag != tag0:
            print("%s | %.2f A %.2f V" % (tag, S["a"], S["v"]), flush=True); tag0 = tag
        ch = [int(round(1500 + v * 5)) for v in x[:5]] + [int(round(1000 + x[5] * 1000))]
        m.mav.rc_channels_override_send(1, 1, *([65535] * 8), *ch, *([0] * 4))
        if n % 10 == 0:
            m.mav.heartbeat_send(6, 8, 0, 0, 0)
        n += 1
        lee(max(0.0, t0 + n * DT - time.time()))
    for _ in range(12):
        m.mav.rc_channels_override_send(1, 1, *([65535] * 8), *ch, *([0] * 4)); lee(0.05)
    print("fin %s | max %.2f A, %.2f V" % (g.gesto, pico, S["v"]))


if __name__ == "__main__":
    main()
