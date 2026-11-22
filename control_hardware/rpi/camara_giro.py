"""Gira 180 grados el video de la camara sin recomprimir (TurboJPEG, transformacion sin perdida).

ustreamer (servicio camara) publica el video original solo en 127.0.0.1:8081; este programa lo publica girado en
0.0.0.0:8080 con las mismas direcciones de siempre: /stream, /snapshot y /. Requiere el paquete libturbojpeg0.
Uso: python3 camara_giro.py [--grados 180|0]
"""
import argparse, ctypes, socket, threading, time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORIGEN = "http://127.0.0.1:8081/stream"
PUERTO = 8080
TJXOP_ROT180, TJXOPT_TRIM = 6, 2


class Transform(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("w", ctypes.c_int), ("h", ctypes.c_int),
                ("op", ctypes.c_int), ("options", ctypes.c_int), ("data", ctypes.c_void_p),
                ("customFilter", ctypes.c_void_p)]


tj = ctypes.CDLL("libturbojpeg.so.0")
tj.tjInitTransform.restype = ctypes.c_void_p
tj.tjTransform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_int,
                           ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(Transform), ctypes.c_int]
tj.tjFree.argtypes = [ctypes.c_void_p]
tj.tjGetErrorStr2.argtypes = [ctypes.c_void_p]
tj.tjGetErrorStr2.restype = ctypes.c_char_p


def girar(handle, jpeg):
    dst, size = ctypes.c_void_p(None), ctypes.c_ulong(0)
    tr = Transform(op=TJXOP_ROT180, options=TJXOPT_TRIM)
    rc = tj.tjTransform(handle, jpeg, len(jpeg), 1, ctypes.byref(dst), ctypes.byref(size), ctypes.byref(tr), 0)
    try:
        if rc != 0 or not dst.value:
            raise RuntimeError(tj.tjGetErrorStr2(handle).decode(errors="replace"))
        return ctypes.string_at(dst.value, size.value)
    finally:
        if dst.value:
            tj.tjFree(dst)


cond = threading.Condition()
cuadro, numero, hora = None, 0, 0.0      # ultimo cuadro ya girado


def leer_origen(grados):
    global cuadro, numero, hora
    handle = tj.tjInitTransform()
    while True:
        try:
            with urllib.request.urlopen(ORIGEN, timeout=5) as r:
                while True:
                    largo = None
                    while True:                              # cabeceras de cada cuadro
                        linea = r.readline()
                        if not linea:
                            raise EOFError("ustreamer cerro la conexion")
                        if linea.lower().startswith(b"content-length:"):
                            largo = int(linea.split(b":")[1])
                        if linea in (b"\r\n", b"\n") and largo is not None:
                            break
                    jpeg = r.read(largo)
                    if len(jpeg) < largo:
                        raise EOFError("cuadro incompleto")
                    try:
                        out = girar(handle, jpeg) if grados == 180 else jpeg
                    except RuntimeError as e:                # un cuadro danado no corta el video
                        print("cuadro descartado:", e, flush=True)
                        continue
                    with cond:
                        cuadro, numero, hora = out, numero + 1, time.monotonic()
                        cond.notify_all()
        except Exception as e:
            print("origen:", e, flush=True)
            time.sleep(1)


class Web(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def cabecera(self, tipo, largo=None):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        if largo is not None:
            self.send_header("Content-Length", str(largo))
        self.end_headers()
        self.close_connection = True

    def do_GET(self):
        ruta = self.path.split("?")[0].rstrip("/")
        try:
            if ruta == "/stream":
                self.stream()
            elif ruta == "/snapshot":
                with cond:
                    ok = cuadro is not None and time.monotonic() - hora < 3
                    img = cuadro
                if not ok:
                    self.send_error(503, "sin video")
                    return
                self.cabecera("image/jpeg", len(img))
                self.wfile.write(img)
            elif ruta == "":
                html = b"<!doctype html><title>Camara</title><body style='margin:0;background:#222'><img src='/stream'>"
                self.cabecera("text/html; charset=utf-8", len(html))
                self.wfile.write(html)
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self.close_connection = True

    def stream(self):
        self.connection.settimeout(5)                        # un cliente colgado no se queda para siempre
        self.cabecera("multipart/x-mixed-replace;boundary=cuadro")
        visto = 0
        while True:
            with cond:
                cond.wait_for(lambda: numero != visto, timeout=5)
                if numero == visto:
                    return                                   # sin video: que el cliente reconecte
                img, visto = cuadro, numero
            self.wfile.write(b"--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(img))
            self.wfile.write(img + b"\r\n")


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--grados", type=int, choices=[0, 180], default=180)
    a = ap.parse_args()
    threading.Thread(target=leer_origen, args=(a.grados,), daemon=True).start()
    print("video girado %d en el puerto %d" % (a.grados, PUERTO), flush=True)
    Servidor(("0.0.0.0", PUERTO), Web).serve_forever()
