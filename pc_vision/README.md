# Visión en el PC

Corre el modelo YOLO en la GPU del PC (RTX 3070) sobre el video del robot y envía las detecciones al
puente de la Radxa. El robot las usa para acercarse a los objetos y a las personas, y la consola las
dibuja sobre el video.

```
Radxa: ustreamer :8080/stream ──video──▶ PC: vision_client.py (YOLO, CUDA)
Radxa: nexa_bridge :8765      ◀──{"type":"vision_detections", ...}──┘
```

## Instalación (Windows o Linux)

```bash
python -m venv .venv
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cu124   # torch con CUDA
.venv/Scripts/pip install -r requirements.txt
mkdir models && copy ruta\a\best.pt models\best.pt
```

En `config.toml`:
- **Direcciones de la Radxa:** `video_url` y `bridge_url`.
- **Modelo:** la ruta del modelo.
- **Clases:** la tabla `class_map`, del nombre de cada clase de su modelo al nombre que usa la consola (`persona`, `botella`, `taza`, `lata`, `juguete`, `tornillo`, `libro`). Las personas tienen que llegar como `persona`.

## Uso

```bash
.venv/Scripts/python vision_client.py --show     # con ventana de vista previa (q para salir)
```

- **Reconexión:** el cliente se reconecta solo si se cae el video o el puente.
- **Ritmo:** envía hasta `rate_hz` detecciones por segundo, una por cada cuadro nuevo.
- **Formato:** cada detección lleva `cls`, `confidence` y `bbox = [x, y, ancho, alto]`, normalizado de 0 a 1.

**Cámara monocromática:**
- La DECXIN entrega imágenes en blanco y negro, así que elijan clases que se distingan por la forma y no por el color.
- Un modelo entrenado con imágenes a color pierde algo de precisión. Si pueden, conviene entrenar o afinar con imágenes de esta cámara, o al menos convertir el set de entrenamiento a escala de grises.

**Si se cae el WiFi,** el robot deja de recibir detecciones y la consola muestra «Visión» en rojo. La estabilización y la parada por falta de mando siguen funcionando en la H743.
