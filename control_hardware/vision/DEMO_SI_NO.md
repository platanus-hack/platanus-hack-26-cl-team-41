# Demo sí / no: Claude mira por la cámara y el brazo responde

El brazo se mueve suave mientras espera (idle). **Claude mira las fotos de la cámara** y decide:

| Lo que ve | Gesto | Después |
|---|---|---|
| Rollo de **cinta aislante** | **"no"**: sacude de lado a lado, se encoge y tiembla (~17 s), y **retrocede 1 s** | sigue mirando |
| **Plátano** | **"sí"**: asiente, se estira y celebra (~23 s), y **avanza 1 s** | **termina la búsqueda** |
| Nada, pies, sillas, otra cosa | ninguno, sigue en idle | sigue mirando |

Cualquier PC con el repositorio puede correrla: no usa GPU, YOLO, clave SSH ni USB. Solo hay que estar en la **misma red que la Raspberry** (WiFi `PlatanusHack`).

## Para las personas

1. Enciende el rover (batería de la H743 y Raspberry) y espera unos 40 s. Ponlo **en el suelo**, con **1 m libre adelante y atrás**: las ruedas se mueven (unos 10 cm por segundo al 45 %).
   Si está sobre una mesa, pídele a Claude que lo corra **sin ruedas**.
2. Conéctate al WiFi `PlatanusHack`.
3. Abre Claude Code en la carpeta del repositorio y escribe **`/demo-si-no`** (o "haz la demo de DEMO_SI_NO.md").
4. Deja unos **60 cm libres** alrededor del brazo (la base gira hasta 40° a cada lado), con el rover a nivel, con manos y pies lejos de la garra.
5. Muestra **un objeto a la vez**, quieto y entero, a 20–40 cm de la cámara. La cinta, con el aro hacia la cámara y sobre fondo claro. Retíralo cuando empiece el gesto.

Teclas en la ventana "robot vivo": **q** = reposo y salir, **espacio** = pausa, **s** = forzar "sí", **n** = forzar "no".
Si algo se ve mal: **q**, o desconecta la batería sosteniendo el brazo.

Solo **un PC a la vez** puede mandar el brazo. Cierra antes otras demos o apps que lo muevan.

## Instalación (una vez por PC)

Desde esta carpeta (`control_hardware/vision` en el repositorio). En Windows:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-demo.txt
```

En Mac o Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
```

Abajo, `PY` es `.venv\Scripts\python` (Windows) o `.venv/bin/python` (Mac o Linux).

---

## Instrucciones para Claude

Sigue estos pasos en orden, desde esta carpeta.

### 1. Revisar (no mueve nada)

`PY claude_demo.py revisar` → tiene que salir todo en `OK`.
- Si falta un paquete o el entorno, instálalo como se indica arriba.
- Si falla la cámara o la H743, pide que revisen el WiFi y la alimentación de la Raspberry. No pruebes otras IP de la red: hay Raspberry de otros equipos. Si la IP de la nuestra cambió, la persona debe decírtela y se usa con `ROVER_IP`.

### 2. Pedir permiso una sola vez

El brazo va a moverse en la realidad. Pregunta: **"¿El rover está en el suelo con 1 m libre adelante y atrás, 60 cm a los lados, manos fuera y nadie más moviéndolo?"** Con un sí claro, sigue, y **no vuelvas a preguntar** durante la demo.

### 3. Arrancar el idle en segundo plano

- Rover **en el suelo**, confirmado por la persona: `PY robot_vivo.py --claude --ruedas`
- Sobre una mesa, o si no lo confirmó: `PY robot_vivo.py --claude` (solo el brazo)

Corre en segundo plano y queda andando. Espera a que `PY claude_demo.py estado` diga `idle`.
- Las ruedas no parten si el rover está inclinado más de 10°, si la placa está armada o si no responde el script de ruedas (`PickerDrive`); en ese caso hace solo el gesto del brazo y lo escribe en la salida del programa (`ruedas quietas: …`).
- No cambies la potencia ni el tiempo de las ruedas.
- Las ruedas con los gestos están simuladas pero **aún no probadas en el robot**: la primera vez, con alguien al lado.
- `otro programa esta moviendo el brazo`: avisa y espera a que lo cierren. No insistas.

### 4. Mirar sin parar hasta ver el plátano

Repite este ciclo:

1. `PY claude_demo.py foto`
2. Lee `demo_tmp/foto.jpg` con la herramienta de lectura de archivos **en el mismo mensaje**, después del comando, para ahorrar tiempo.
3. Decide **mirando tú la imagen**:
   - **Cinta aislante** → `PY claude_demo.py gesto no` y **vuelve al punto 1**.
   - **Plátano** → `PY claude_demo.py gesto si`, y la búsqueda **termina** (paso 5).
   - **Nada o dudas** → vuelve al punto 1 de inmediato. Si dudas entre dos cosas, toma otra foto; no adivines.

Reglas del ciclo:
- **No termines el turno ni preguntes si seguir mientras no hayas visto el plátano.** Que una foto salga vacía no es motivo para parar. Solo paras si: viste el plátano, la persona te lo pide, o hay un error que no se arregla reintentando.
- **No uses vigilantes de movimiento ni detectores**: el brazo y la sombra del sol los activan. Mira tú cada foto.
- **No escribas texto largo entre fotos**, y no agregues esperas: cada segundo cuenta. Una frase corta solo cuando reconoces algo ("¡Cinta! → no").
- `gesto` espera a que el gesto termine, así que la foto siguiente ya es de después.
- **No reacciones dos veces al mismo objeto**: después de un "no", espera a ver una foto sin la cinta antes de volver a reaccionar a ella. Si en su lugar aparece el plátano, responde de inmediato.
- Un objeto guardado en un borde, en el piso o en una mesa, que nadie está mostrando, no cuenta.
- Si hay una mano o un pie **tocando la garra, o pegado al rover por delante o por detrás**, pide que lo alejen antes de mandar el gesto.

### 5. Terminar

Cuenta en una o dos líneas qué viste. El robot queda en idle, por si quieren repetir. Para apagar: `PY claude_demo.py salir` (vuelve al reposo).

### Cómo se ven las cosas en esta cámara

- Blanco y negro, desde arriba. **El brazo entra por arriba a la izquierda**, y el frente del rover es hacia **abajo** en la imagen.
- **Cinta aislante:** aro negro, con el centro claro o transparente; a veces se ve de lado, como un cilindro oscuro corto. No confundir con las **ruedas de las sillas** (discos claros con borde oscuro, en la punta de una pata) ni con los círculos de la pinza.
- **Plátano:** impreso en 3D, claro, curvo, con **caras planas** y dos bloques oscuros en el lado de adentro. Suele ir en una mano.
- **Pieza blanca con malla:** una pieza clara con una zona de **rejilla calada** en la superficie también es el **plátano** (así salió la impresión). Si la ves, responde **"sí"** igual que con el plátano, sin esperar a otra foto.
- El piso tiene una franja muy clara de sol y la sombra del brazo se mueve: no son objetos.
- Si la imagen sale muy quemada o muy oscura, dilo; la exposición se ajusta en la Pi (solo quien tiene la clave SSH): `v4l2-ctl -d /dev/video0 --set-ctrl=auto_exposure=1` y después `--set-ctrl=exposure_time_absolute=60,gain=30`. Se pierde al reiniciar la Pi.

### Errores

| Mensaje | Qué hacer |
|---|---|
| `sin camara` | Reintenta la foto 5 veces. Si sigue, la Raspberry se cayó (ya pasó por bajo voltaje): avisa. |
| `robot_vivo.py se detuvo` o `no esta corriendo` | Lanza de nuevo el paso 3, una vez. Si falla, avisa con el mensaje. |
| `corriente alta` / `voltaje bajo` | **No lo relances**: avisa y que revisen el brazo y la batería. |

**Seguridad:** no cambies parámetros de la placa ni subas scripts para esta demo. Para mover el brazo de otra forma, antes hay que leer `../firmware/BRAZO_CONTROL.md`.
