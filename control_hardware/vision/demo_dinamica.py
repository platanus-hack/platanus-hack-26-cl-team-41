"""Demo dinamica del brazo: todos los ejes a la vez, con movimientos continuos (sinusoides con entrada y salida suaves).

Ningun eje pasa de ~55 grados/s (la placa limita a 60). Parte y termina en reposo.
Uso: python demo_dinamica.py [--port COM4] [--espera 8]
Se detiene (el brazo se queda quieto) con Ctrl+C, corriente alta sostenida o voltaje bajo.
"""
import math

from demo_brazo import REST, GRIP0, correr

DT = 0.025
CENTRO = [0.0, 5.0, 60.0, 10.0, 0.0, 0.45]     # base, hombro, codo, muneca, giro, pinza
INICIO = list(REST) + [GRIP0]


def s(t, T, fase=0.0):
    return math.sin(2 * math.pi * t / T + fase)


# cada figura: (nombre, duracion, funcion(t) -> desplazamiento respecto de CENTRO)
FIGURAS = [
    ("ola", 10.0, lambda t: [28 * s(t, 5.0), 13 * s(t, 5.0, 1.6), 14 * s(t, 5.0, 3.1), 24 * s(t, 3.33),
                             28 * s(t, 5.0), 0.0]),
    ("ocho con la punta", 12.0, lambda t: [35 * s(t, 6.0), 10 * s(t, 3.0), -12 * s(t, 3.0), 12 * s(t, 3.0, 1.6),
                                           -35 * s(t, 6.0), 0.0]),
    ("baile con la pinza", 10.0, lambda t: [16 * s(t, 5.0), 9 * s(t, 2.5), -14 * s(t, 2.5), 15 * s(t, 2.5, 1.6),
                                            28 * s(t, 5.0, 1.6) + 20, 0.32 * s(t, 3.33)]),
    ("barrido en circulo", 12.0, lambda t: [45 * s(t, 6.0), 14 * s(t, 6.0, 1.6), 10 * s(t, 6.0, 1.6), 22 * s(t, 4.0),
                                            24 * s(t, 4.0, 1.6), 0.25 * s(t, 4.0)]),
]


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


def trayectoria():
    def ir(tag, a, b, T):
        n = int(T / DT)
        for i in range(1, n + 1):
            k = suave(i / n)
            x = [p + (q - p) * k for p, q in zip(a, b)]
            yield tag, x[:5], x[5]

    yield from ir("se levanta", INICIO, CENTRO, 3.0)
    for nombre, T, f in FIGURAS:
        for i in range(int(T / DT)):
            t = i * DT
            env = suave(t / 1.8) * suave((T - t) / 1.8)
            x = [c + env * d for c, d in zip(CENTRO, f(t))]
            yield nombre, x[:5], x[5]
    reverencia = [0.0, 25.0, 60.0, 35.0, 0.0, 0.75]
    yield from ir("reverencia", CENTRO, reverencia, 2.0)
    yield from ir("reverencia", reverencia, reverencia, 0.8)
    yield from ir("vuelve al reposo", reverencia, CENTRO, 2.0)
    yield from ir("vuelve al reposo", CENTRO, INICIO, 3.0)


if __name__ == "__main__":
    correr(trayectoria, dt=DT, max_a=3.0)
