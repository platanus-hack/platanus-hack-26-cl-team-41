"""Ajuste fino del servo auxiliar del hombro (S1) para que no se pelee con el principal (S3).

Idea: si los dos servos quieren ir a angulos distintos se empujan entre si y la corriente sube.
El script mantiene el brazo quieto, prueba valores de BRH_TRIM alrededor del actual y deja el de MENOR corriente.

Corriente: la lee de la H743 (SYS_STATUS) si mide la corriente; si no, te pide que escribas lo que marca
la fuente en cada paso (--manual).

Antes de correrlo:
  1. Vx en 6 V. Brazo despejado. S1 y S3 conectados.
  2. BRH_DIR y BRH_TRIM ya puestos con el desfase del montaje (hombro auxiliar actual: DIR 1, TRIM -60;
     ver brazo_estable.lua). El script NO cambia BRH_DIR; solo mueve el trim +-8 grados alrededor del actual.
Uso (desde firmware/tools):
  python buscar_trim_hombro.py --port COM4
  python buscar_trim_hombro.py --port COM4 --manual
Seguridad: si la corriente supera --max-a se suelta el servo auxiliar (BRH_DIR = 0) y se detiene.
"""
import argparse, time
from pymavlink import mavutil

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="COM4", help="COM4 por USB o udpout:172.16.0.127:14550 por WiFi")
ap.add_argument("--manual", action="store_true", help="escribir a mano la corriente de la fuente")
ap.add_argument("--rango", type=float, default=6.0, help="busqueda gruesa de +-rango grados alrededor del trim actual")
ap.add_argument("--max-a", type=float, default=2.0, help="corriente maxima antes de abortar (A)")
ap.add_argument("--espera", type=float, default=1.5, help="segundos para que se asiente cada paso")
args = ap.parse_args()

# postura de prueba: hombro algo adelante (con carga, asi la pelea se nota), codo y muneca suaves
POSE = [0.0, 10.0, 60.0, 40.0, 0.0]
GRIP = 0.4
DELTA_MAX = 8.0

m = mavutil.mavlink_connection(args.port, baud=115200, source_system=255)
for _ in range(3):
    m.mav.heartbeat_send(6, 8, 0, 0, 0); time.sleep(0.2)
if not m.wait_heartbeat(timeout=10):
    raise SystemExit("La H743 no responde por %s" % args.port)


def mantener(segundos):
    """Sigue mandando la postura (RC override ch9..14) mientras espera."""
    ch = [int(round(1500 + p * 5)) for p in POSE] + [int(round(1000 + GRIP * 1000))]
    t = time.time()
    while True:
        m.mav.rc_channels_override_send(m.target_system, m.target_component, *([65535] * 8), *ch)
        m.mav.heartbeat_send(6, 8, 0, 0, 0)
        if time.time() - t >= segundos:
            break
        time.sleep(0.05)


def getp(name):
    for _ in range(5):
        m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1.5)
        if p and p.param_id == name:
            return p.param_value
    raise SystemExit("No se pudo leer %s" % name)


def setp(name, val):
    for _ in range(5):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(val),
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1.5)
        if p and p.param_id == name and abs(p.param_value - val) < 1e-3:
            return
    raise SystemExit("No se pudo fijar %s" % name)


def corriente():
    if args.manual:
        mantener(0.1)
        return float(input("   corriente de la fuente (A): ").replace(",", "."))
    vals, t = [], time.time()
    while time.time() - t < 1.0:
        mantener(0.05)
        s = m.recv_match(type="SYS_STATUS", blocking=False)
        if s and s.current_battery >= 0:
            vals.append(s.current_battery / 100.0)   # cA -> A
    if not vals:
        raise SystemExit("La H743 no informa corriente: correr con --manual y leer la fuente")
    vals.sort()
    return vals[len(vals) // 2]


dir_ = getp("BRH_DIR")
centro = getp("BRH_TRIM")
if dir_ not in (1.0, -1.0):
    raise SystemExit("BRH_DIR = %g: primero fijar el sentido y el desfase del montaje" % dir_)
print("BRH_DIR = %d, trim actual = %+.2f (busco entre %+.1f y %+.1f)" % (dir_, centro, centro - args.rango, centro + args.rango))


def probar(trim):
    trim = max(centro - DELTA_MAX, min(centro + DELTA_MAX, trim))
    setp("BRH_TRIM", trim)
    mantener(args.espera)
    a = corriente()
    print("   trim %+6.2f  ->  %.2f A" % (trim, a))
    if a > args.max_a:
        setp("BRH_DIR", 0)
        raise SystemExit("Corriente %.2f A > %.2f A: servo auxiliar suelto (BRH_DIR = 0). Revisar montaje/sentido."
                         % (a, args.max_a))
    return a


try:
    print("Llevando el brazo a la postura de prueba", POSE)
    mantener(4.0)                       # 60 grados/s: tiempo de sobra para llegar

    print("Busqueda gruesa (de a 1 grado):")
    n = int(args.rango)
    medidas = {centro + d: probar(centro + d) for d in range(-n, n + 1)}
    mejor = min(medidas, key=medidas.get)

    print("Refinando alrededor de %+.2f:" % mejor)
    for d in (-0.75, -0.5, -0.25, 0.25, 0.5, 0.75):
        if abs(mejor + d - centro) <= DELTA_MAX:
            medidas[mejor + d] = probar(mejor + d)
    mejor = min(medidas, key=medidas.get)

    setp("BRH_TRIM", mejor)
    mantener(1.0)
    print("\nListo: BRH_TRIM = %+.2f  (%.2f A; con el trim inicial eran %.2f A)" % (mejor, medidas[mejor], medidas[centro]))
    if abs(mejor - centro) >= args.rango - 0.01:
        print("OJO: el minimo quedo en el borde del rango: repetir (ahora busca alrededor del nuevo trim).")
except KeyboardInterrupt:
    setp("BRH_TRIM", centro)
    print("Interrumpido: trim de vuelta a %+.2f" % centro)
