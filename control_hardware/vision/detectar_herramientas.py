"""Demo: identifica herramientas en el video de la camara y muestra si se estan usando.

Dos etapas: YOLO-World propone recuadros (umbral bajo, con contraste realzado) y CLIP decide que es cada recorte.
YOLO-World solo no basta: con esta camara en blanco y negro encuentra un destornillador pero lo llama tijeras (6%).

El estado de uso esta FIJO por ahora (ver estado_uso): siempre dice "herramienta sin uso".
Uso (desde la carpeta vision):
  .venv\\Scripts\\python detectar_herramientas.py                 # ventana en vivo (q o Esc = salir)
  .venv\\Scripts\\python detectar_herramientas.py --prueba 5      # sin ventana: 5 s, imprime y guarda --salida
  .venv\\Scripts\\python detectar_herramientas.py --source 0      # webcam
"""
import argparse, threading, time
import cv2
import numpy as np

# texto que busca YOLO-World -> nombre que se muestra
HERRAMIENTAS = {
    "screwdriver": "destornillador", "pliers": "alicate", "wire cutters": "alicate de corte", "wrench": "llave",
    "hammer": "martillo", "scissors": "tijeras", "soldering iron": "cautin", "multimeter": "multimetro",
    "utility knife": "cuchillo cartonero", "tape measure": "huincha de medir", "electric drill": "taladro",
    "hex key": "llave allen", "tweezers": "pinzas", "roll of tape": "rollo de cinta", "hot glue gun": "pistola de silicona",
    "caliper": "pie de metro", "ruler": "regla", "hand saw": "serrucho", "file tool": "lima",
}
# cosas parecidas que NO son herramientas: se le dan al modelo para que no las confunda, y no se muestran
DISTRACTORES = ["person", "hand", "wristwatch", "cable", "chair", "robot arm", "paper", "keyboard", "phone", "laptop"]
# otras cosas de la mesa que CLIP debe poder elegir en vez de una herramienta
OTROS_CLIP = ["finger", "computer mouse", "ID badge", "lanyard", "power adapter", "wooden floor", "dark cloth", "table",
              "bottle", "can", "printed circuit board", "tangled wires", "electrical connectors", "battery pack",
              "a blurry dark object", "clothing", "trousers", "shoe"]


def estado_uso(herramienta, caja, cuadro):
    """PENDIENTE: decidir si se usa y para que tarea. Por ahora es un valor fijo, no una medicion."""
    return "herramienta sin uso"


class Video:
    """Lee en un hilo y entrega siempre el ultimo cuadro (sin atraso acumulado); reconecta si se corta."""
    def __init__(self, src):
        self.src, self.f, self.n, self.vivo = src, None, 0, True
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self):
        while self.vivo:
            cap = cv2.VideoCapture(self.src)
            while self.vivo:
                ok, f = cap.read()
                if not ok:
                    break
                self.f, self.n = f, self.n + 1
            cap.release()
            time.sleep(0.5)


def iou(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    i = w * h
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def dentro(a, b):
    """Fraccion del recuadro mas chico cubierta por el otro."""
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))


class Clasificador:
    """CLIP: probabilidad de cada nombre para cada recorte (promedio de recorte ajustado y con contexto)."""
    def __init__(self):
        import os, torch, clip
        self.torch, self.dev = torch, "cuda" if torch.cuda.is_available() else "cpu"
        raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights", "clip")
        self.m, _ = clip.load("ViT-B/32", device=self.dev, download_root=raiz)
        self.nombres = list(HERRAMIENTAS) + DISTRACTORES + OTROS_CLIP
        self.nh = len(HERRAMIENTAS)
        with torch.no_grad():
            t = sum(self.m.encode_text(clip.tokenize([f % n for n in self.nombres]).to(self.dev))
                    for f in ("a photo of a %s.", "a black and white photo of a %s."))
            self.t = (t / t.norm(dim=-1, keepdim=True)).T
        self.media = np.array([0.4815, 0.4578, 0.4082], np.float32)
        self.desv = np.array([0.2686, 0.2613, 0.2758], np.float32)

    @staticmethod
    def _recortes(f, caja):
        H, W = f.shape[:2]; x1, y1, x2, y2 = map(int, caja)
        c = f[max(0, y1 - 8):min(H, y2 + 8), max(0, x1 - 8):min(W, x2 + 8)]
        d, dv, dh = max(c.shape[:2]), max(c.shape[:2]) - c.shape[0], max(c.shape[:2]) - c.shape[1]
        aj = cv2.copyMakeBorder(c, dv // 2, dv - dv // 2, dh // 2, dh - dh // 2, cv2.BORDER_CONSTANT, value=(114,) * 3)
        s, cx, cy = max(16, int(d * 1.15)) // 2, (x1 + x2) // 2, (y1 + y2) // 2
        cu = f[max(0, cy - s):min(H, cy + s), max(0, cx - s):min(W, cx + s)]
        return [cv2.resize(q, (224, 224), interpolation=cv2.INTER_AREA if min(q.shape[:2]) > 224 else cv2.INTER_CUBIC)
                for q in (aj, cu)]

    def __call__(self, f, cajas):
        if not cajas:
            return []
        x = np.stack([q for c in cajas for q in self._recortes(f, c)])[..., ::-1].astype(np.float32) / 255
        x = self.torch.from_numpy(((x - self.media) / self.desv).transpose(0, 3, 1, 2).copy()).to(self.dev)
        with self.torch.no_grad():
            v = self.m.encode_image(x.type(self.m.dtype)); v = v / v.norm(dim=-1, keepdim=True)
            p = (100 * v @ self.t).softmax(-1).float().cpu().numpy()
        return list((p[0::2] + p[1::2]) / 2)


class Seguidor:
    """Promedia las probabilidades en el tiempo: muestra algo recien tras verlo varias veces y lo mantiene si parpadea."""
    def __init__(self, nh, minimo=5, dura=0.7, entra=0.55, sale=0.40, nombre_min=0.22):
        self.p, self.nh, self.minimo, self.dura, self.entra, self.sale = [], nh, minimo, dura, entra, sale
        self.nombre_min = nombre_min                         # certeza minima del nombre elegido

    def actualizar(self, cajas, probs):
        ahora, usados = time.time(), set()
        for caja, pr in zip(cajas, probs):
            libres = [t for t in self.p if id(t) not in usados]
            m = max(libres, key=lambda t: iou(t["caja"], caja), default=None)
            if m and iou(m["caja"], caja) > 0.3:
                m["caja"] = [0.5 * x + 0.5 * y for x, y in zip(m["caja"], caja)]
                m["pr"] = 0.85 * m["pr"] + 0.15 * pr; m["t"] = ahora; m["n"] += 1
            else:
                m = dict(caja=list(caja), pr=pr.copy(), t=ahora, n=1, ver=False); self.p.append(m)
            usados.add(id(m))
        self.p = [t for t in self.p if ahora - t["t"] < self.dura]
        out = []
        for t in self.p:
            total = float(t["pr"][:self.nh].sum()); k = int(t["pr"].argmax())
            minimo = self.nombre_min * (0.7 if t["ver"] else 1.0)
            t["ver"] = (t["n"] >= self.minimo and k < self.nh and t["pr"][k] > minimo
                        and total > (self.sale if t["ver"] else self.entra))
            if t["ver"]:
                out.append((t["caja"], k, float(t["pr"][k]), total))
        return out


def texto(img, s, x, y, color, fondo, esc=0.65):
    (w, h), b = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, esc, 2)
    x = int(max(0, min(x, img.shape[1] - w - 10))); y = int(max(h + 8, min(y, img.shape[0] - 6)))
    cv2.rectangle(img, (x, y - h - 7), (x + w + 10, y + b), fondo, -1)
    cv2.putText(img, s, (x + 5, y - 2), cv2.FONT_HERSHEY_SIMPLEX, esc, color, 2, cv2.LINE_AA)
    return h + b + 9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="http://172.16.0.127:8080/stream")
    ap.add_argument("--model", default="yolov8s-worldv2.pt")
    ap.add_argument("--conf", type=float, default=0.03, help="umbral de las propuestas (el filtro fino lo hace CLIP)")
    ap.add_argument("--certeza", type=float, default=0.55, help="certeza minima de que sea una herramienta (0..1)")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--prueba", type=float, default=0, help="segundos sin ventana")
    ap.add_argument("--salida", default="herramientas.jpg")
    a = ap.parse_args()

    from ultralytics import YOLOWorld
    clases = list(HERRAMIENTAS) + ["hand tool"] + DISTRACTORES
    model = YOLOWorld(a.model); model.set_classes(clases)
    clip_ = Clasificador(); nombres = list(HERRAMIENTAS)
    clahe = cv2.createCLAHE(2.5, (8, 8))
    video = Video(int(a.source) if a.source.isdigit() else a.source)
    seg = Seguidor(clip_.nh, entra=a.certeza, sale=a.certeza - 0.15)
    t0 = time.time()
    while video.f is None:
        if time.time() - t0 > 15:
            raise SystemExit("No llega video de %s" % a.source)
        time.sleep(0.05)

    win = "Herramientas (q = salir)"
    if not a.prueba:
        cv2.namedWindow(win, cv2.WINDOW_NORMAL); cv2.resizeWindow(win, 1280, 720)
        cv2.setWindowProperty(win, cv2.WND_PROP_TOPMOST, 1)
    print("demo abierta", flush=True)
    visto, fps, t_ant, t0, vistos = 0, 0.0, time.time(), time.time(), {}
    while True:
        if video.n == visto:
            time.sleep(0.003)
        else:
            visto, f = video.n, video.f.copy()
            limpio = f.copy()
            real = cv2.cvtColor(clahe.apply(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)), cv2.COLOR_GRAY2BGR)
            r = model.predict(real, conf=a.conf, imgsz=a.imgsz, agnostic_nms=True, iou=0.5, verbose=False)[0]
            cand, area = [], f.shape[0] * f.shape[1]
            for b in r.boxes:                                # propuestas: lo que YOLO cree herramienta, ni enorme ni minusculo
                x1, y1, x2, y2 = caja = b.xyxy[0].tolist()
                if clases[int(b.cls)] not in DISTRACTORES and 400 < (x2 - x1) * (y2 - y1) < 0.25 * area:
                    cand.append((float(b.conf), caja))
            cajas = []
            for _, c in sorted(cand, key=lambda t: -t[0]):       # sin recuadros dentro de otros
                if len(cajas) < 10 and all(dentro(c, o) < 0.7 for o in cajas):
                    cajas.append(c)
            probs = clip_(limpio, cajas)
            lista = seg.actualizar(cajas, probs)
            for caja, k, conf, total in lista:
                nombre = HERRAMIENTAS[nombres[k]]; vistos[nombre] = max(vistos.get(nombre, 0), conf)
                x1, y1, x2, y2 = map(int, caja)
                cv2.rectangle(f, (x1, y1), (x2, y2), (0, 200, 255), 2)
                alto = texto(f, "%s %d%%" % (nombre, conf * 100), x1, y1 - 30, (0, 0, 0), (0, 200, 255))
                texto(f, estado_uso(nombre, caja, f), x1, y1 - 30 + alto, (255, 255, 255), (60, 60, 60), 0.55)
            ahora = time.time(); fps = 0.9 * fps + 0.1 / max(1e-3, ahora - t_ant); t_ant = ahora
            texto(f, "herramientas: %d   %.0f fps" % (len(lista), fps), 8, 30, (255, 255, 255), (40, 40, 40))
            if a.prueba:
                cv2.imwrite(a.salida, f)
            else:
                cv2.imshow(win, f)
        if a.prueba:
            if time.time() - t0 > a.prueba:
                print("fps %.0f" % fps, {k: round(v, 2) for k, v in sorted(vistos.items(), key=lambda t: -t[1])})
                break
        else:
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27) or cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break
    video.vivo = False
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
