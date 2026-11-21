"""Prueba de red entre la Radxa (servidor) y el PC (cliente).
El PC inicia la conexion, asi el firewall de Windows no molesta (igual que al pedir el video).

Radxa:  python3 net_test.py server
PC:     python net_test.py client <IP_RADXA>

Mide: latencia (ida y vuelta), Radxa->PC (lo que usa el video) y PC->Radxa.
"""
import socket, sys, time, struct, statistics

PORT = 5201
SECS = 5
CHUNK = b"\x55" * 65536


def server():
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT)); s.listen(1)
    print("Esperando al PC en el puerto %d ..." % PORT, flush=True)
    while True:
        c, addr = s.accept()
        print("Conectado:", addr, flush=True)
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            while True:
                cmd = c.recv(1)
                if not cmd:
                    break
                if cmd == b"P":            # ping: devolver 8 bytes
                    c.sendall(recv_exact(c, 8))
                elif cmd == b"D":          # Radxa -> PC durante SECS
                    end = time.time() + SECS
                    while time.time() < end:
                        c.sendall(CHUNK)
                    c.sendall(b"")
                    c.shutdown(socket.SHUT_WR)
                    break
                elif cmd == b"U":          # PC -> Radxa: contar bytes y responder
                    n = 0; t0 = time.time()
                    total = struct.unpack("!Q", recv_exact(c, 8))[0]
                    while n < total:
                        d = c.recv(65536)
                        if not d:
                            break
                        n += len(d)
                    c.sendall(struct.pack("!d", time.time() - t0))
        except Exception as e:
            print("error:", e)
        c.close()


def recv_exact(c, n):
    b = b""
    while len(b) < n:
        d = c.recv(n - len(b))
        if not d:
            raise ConnectionError("cerrado")
        b += d
    return b


def client(ip):
    def conn():
        c = socket.create_connection((ip, PORT), timeout=10)
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return c

    print("Conectando a %s:%d ..." % (ip, PORT))
    c = conn()
    rtts = []
    for _ in range(50):
        t = time.perf_counter(); c.sendall(b"P" + b"12345678"); recv_exact(c, 8)
        rtts.append((time.perf_counter() - t) * 1000); time.sleep(0.02)
    rtts.sort()
    print("Latencia ida y vuelta: mediana %.1f ms | p95 %.1f ms | max %.1f ms"
          % (statistics.median(rtts), rtts[int(len(rtts) * 0.95) - 1], rtts[-1]))

    total = 0; t0 = time.time()
    c.sendall(b"D")
    while True:
        d = c.recv(262144)
        if not d:
            break
        total += len(d)
    dt = time.time() - t0
    print("Radxa -> PC (video): %.1f Mbit/s" % (total * 8 / dt / 1e6))
    c.close()

    c = conn()
    size = 30 * 1024 * 1024
    c.sendall(b"U" + struct.pack("!Q", size))
    sent = 0
    while sent < size:
        c.sendall(CHUNK); sent += len(CHUNK)
    dt = struct.unpack("!d", recv_exact(c, 8))[0]
    print("PC -> Radxa:         %.1f Mbit/s" % (sent * 8 / dt / 1e6))
    c.close()
    print("Referencia: video MJPEG 640x480 a 30 fps ~ 15-30 Mbit/s; 1280x720 ~ 30-60 Mbit/s.")


if __name__ == "__main__":
    if sys.argv[1] == "server":
        server()
    else:
        client(sys.argv[2])
