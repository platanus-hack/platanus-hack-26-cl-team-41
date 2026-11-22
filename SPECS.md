# Especificaciones técnicas

## 1. Mecánica (diseño paramétrico en SolidCraft)

### Brazo (versión compacta)

- **Grados de libertad:** 5 más la pinza, en este orden:
  1. Giro de la base (MG995).
  2. Hombro (MG995).
  3. Codo (MG995).
  4. Inclinación de la muñeca (MG995).
  5. Giro de la muñeca (SG90).
  6. Pinza de mandíbulas con engranajes de 14 dientes (SG90).
- **Eslabones:** 90 mm de hombro a codo y 85 mm de codo a muñeca, con unos 144 mm más hasta la punta de la pinza. Alcance horizontal de unos 31,9 cm.
- **Construcción:**
  - **Eslabones cerrados:** carcasas de 48 mm de ancho con tapas atornilladas y los servos adentro.
  - **Articulaciones de inclinación:** cada una agarra su servo por los dos lados, en el horn y en un eje M5 del lado opuesto, así el servo no carga solo con el peso.
- **Rango de las articulaciones de inclinación:** ±96,7° antes de chocar con el propio brazo, revisado con el análisis de colisiones de SolidCraft. Lo que limita es el servo, que da ±90°.
- **Apertura de la pinza:** unos 60 mm.
- **Carga útil:**
  - **Brazo estirado:** el hombro necesita unos 7 kg·cm, frente a los 9–11 kg·cm de bloqueo del MG995 a 6 V. Ese es el máximo instantáneo, no un valor de trabajo continuo.
  - **Carga de trabajo declarada:** unos 50 g (pelota de ping-pong, cubo de espuma, lata vacía), agarrando a 15–20 cm del eje del brazo y no con el brazo estirado del todo.
- **Exportado:** STL por pieza, STEP del conjunto y URDF con las 6 articulaciones.

### Base móvil (versión actual, TT)

- **Una sola pieza** de 178 × 170 mm y 132 cm³ de modelo sólido, que se imprime boca abajo sin soportes.
- **Tracción diferencial:** 2 motores TT de 1:48 con ruedas de Ø65 mm, más 2 ruedas locas de bola de 16 mm (el diámetro de la bola es un parámetro).
- **Bolas impresas** (`bola_rueda_loca/`): si no hay canicas, se imprimen bolas de Ø15,8 mm (0,3 mm de holgura en el alojamiento de 16,4). Cada bola son dos mitades con la cara plana sobre la cama, sin soportes, unidas con dos trozos de filamento de 1,75 mm como pasadores y gotita; lijar la junta.
- **Ruedas impresas** (`rueda_tt/`, generador `scripts/rueda_tt.py`), en reemplazo de las amarillas del TT:
  - **Medidas:** Ø65 mm exterior (misma altura del eje: 32,5 mm) y 34 mm de ancho total, contra 26 mm de la de fábrica. El robot queda en 242 mm de ancho.
  - **Llanta de PLA** (`Llanta_TT_PLA.stl`, 17,3 cm³): asiento de Ø55, dos rebordes de Ø57,4 × 1,6 mm que encierran el neumático, alma con 6 ventanas y cubo con agujero en doble D para el eje del TT (Ø5,6 con caras planas a 3,9 mm, 9,6 mm de profundidad) y agujero de Ø2,3 para el tornillo del motor.
  - **Impresión de la llanta:** de pie, con la cara del motor sobre la cama. Sin soportes: el reborde superior lleva un chaflán de 45° y las ventanas son pasantes verticales.
  - **Neumático de TPU** (`Neumatico_TT_TPU.stl`, 30,1 cm³): Ø65 × Ø54,4, ancho 30,6 mm. Queda con 0,3 mm de apriete por lado sobre el asiento y tiene un chaflán interior que calza con el reborde. Para montarlo se estira un 5,5 % sobre el reborde, lo que va bien con TPU 95A.
- **Soportes de motor:** según el plano del TT, con 2 tornillos M3 y la oreja, una ventana para el tetón de ubicación, 2 atiesadores por lado y empalmes en las uniones.
- **Distribución:**
  - **Debajo de la placa:** el L298N y la LiPo 3S, esta última lo más atrás posible para que sirva de contrapeso del brazo.
  - **Arriba:** el brazo, con 4 tornillos M4 a Ø150.
  - **Bandeja de electrónica** (`base_tt/Bandeja_electronica.stl`, 43,5 cm³): disco de Ø160 × 2,4 mm apretado entre la placa y la brida de la base del brazo con los mismos 4 M4, así la placa sigue saliendo en una sola impresión. Se imprime plana, con los separadores hacia arriba, y todo queda dentro de la base hueca del brazo. El brazo sube 2,4 mm.
  - **Matek H743:** montada rígida en la bandeja, a 38 mm del eje de la base del brazo, porque su IMU mide la inclinación que se compensa. Separadores de 5 mm para M3 a 30,5 × 30,5 mm (supuesto: medir la placa y cambiar `FC_DX`/`FC_DY` en `scripts/base_tt.py`). Queda 9,9 mm por debajo del servo de la base.
  - **Radxa Zero 3W:** en la bandeja, con separadores de 4 mm para M2,5 en el patrón de Pi Zero (58 × 23 mm), y la cámara conectada a su puerto USB 3.0.

### Mástil de la cámara

- **Varilla:** fibra de carbono de 12 × 500 mm, entera, vertical detrás de la base del brazo (eje en x = −99,5 mm, centrada).
- **Soporte de la varilla** (`base_tt/Soporte_varilla.stl`, 11,3 cm³): se pega al borde trasero de la placa con una pestaña arriba (8 × 60 mm), una pared contra el canto trasero y dos uñas por debajo que esquivan la rueda loca trasera. Encaje de 46 mm de profundidad con holgura de 0,3 mm para el adhesivo, y una cartela hasta la pestaña. La varilla apoya en el fondo del encaje, a ras de la cara inferior de la placa.
- **Cabezal** (`base_tt/Cabezal_camara.stl`, 7,5 cm³): casquillo que entra a tope en la punta de la varilla, con un brazo que sostiene el marco de 42 × 42 mm para la cámara de 38 × 38 (ventana de 30 × 30 y 4 agujeros guía M2 a 34 mm), inclinado **50° hacia abajo** y mirando hacia adelante.
- **Centro óptico:** a 525 mm del suelo y 58 mm detrás del eje del brazo.
- **Cobertura del suelo** (delante del eje del brazo, según el campo de visión vertical, que está por medir):

  | Campo vertical | Desde | Hasta |
  |---|---|---|
  | 37° (16:9 con 62° de horizontal) | 149 mm | 798 mm |
  | 48° (4:3 con 62° de horizontal) | 92 mm | 1018 mm |

  La inclinación es el parámetro `TILT` en `scripts/base_tt.py`: con 37° de campo vertical, 45° ve de 203 a 994 mm y 55° de 97 a 651 mm.
- **Línea de visión sobre el brazo:** hacia un punto de agarre a 150 mm, pasa por encima del eje del brazo a 378 mm de altura, más alta que el brazo plegado (~250 mm).
- **Límite para el brazo:** con la base del brazo mirando hacia adelante, el brazo recto no puede inclinarse hacia atrás más de ~12° sin tocar la varilla (lo primero que la toca es la punta de los dedos). El brazo no lleva cámara: la única cámara es la del mástil.

### Ensamble completo

- **Peso:** unos 980 g, de los que el brazo son unos 560 g.
- **Altura del centro de masa:** unos 13 cm con el brazo recto.
- **Estabilidad:**
  - Estable con el brazo recto, estirado hacia adelante sin carga y estirado hacia atrás (justo).
  - Se vuelca estirado hacia adelante con 100 g de carga.
  - Por eso las misiones acercan el rover al objeto antes de agarrarlo, en vez de estirar el brazo.
- **Ensamble articulado** (`robot_ensamble/robot_ensamble.sc`): la base móvil, con el mástil y la electrónica, queda fija, y el brazo conserva sus 7 articulaciones (base, hombro, codo, muñeca, giro de muñeca y las dos mandíbulas, unidas por engranaje). Exportado también a STEP y URDF.
- **Conjunto de contacto** "Brazo vs base y mastil": cualquier movimiento del brazo se detiene al tocar la base, la bandeja o la varilla.
- **Rango con el resto del brazo en 0°** (calculado en el CAD):

  | Articulación | Hacia atrás | Hacia adelante |
  |---|---|---|
  | Base (giro) | vuelta completa | vuelta completa |
  | Hombro | −13,7° (la pinza toca la varilla) | 96,7° (choca consigo mismo) |
  | Codo | −21,0° (pinza contra varilla) | 96,6° |
  | Muñeca | −45,7° (pinza contra varilla) | 96,4° |

  Los límites hacia atrás solo aplican con la base mirando hacia adelante. **El codo no pasa de ~96°**, así que el puente y la consola lo limitan a 95°.
- **Posturas predefinidas** (base, hombro, codo, muñeca), validadas sin choques contra la base, el mástil ni entre eslabones, con la base girando de −90° a +90°. La animación de esa validación está en `robot_ensamble/posturas.gif`:

  | Postura | Ángulos | Nota |
  |---|---|---|
  | Recoger | 0, 65,2, 61,3, 53,5 | Punta de los dedos a 5 mm del suelo y a 150 mm del eje del brazo, con la pinza vertical. Con las ruedas de 34 mm, a ras de suelo solo en el sector frontal (base entre −60° y +60°): girada entre ~65° y 80°, la pinza toca la rueda |
  | Transportar | 0, 0, 95, 60 | |
  | Entregar | 0, 48, 30, 12 | |
  | Saludar | 0, 10, 60, −20 | |
  | Plegado | 0, −10, 95, 80 | |

**Otra versión explorada:** una base de 4 ruedas con motores brushless de 1750 KV y una reducción de 80:1 en 3 etapas de engranajes de perfil involuta. Está diseñada y verificada, pero quedó descartada por la complejidad mecánica y el bajo torque de los ESC sin sensores a baja velocidad.

## 2. Electrónica

### Arquitectura en tres niveles

| Nivel | Equipo | Función |
|---|---|---|
| Tiempo real | Matek H743 (ArduPilot 4.5.7) | IMU, estabilización del brazo, PWM de los 6 servos y los 2 motores |
| A bordo | Radxa Zero 3W (RK3566, 4 GB, 32 GB eMMC) | Puente del robot, MAVLink hacia la H743, video MJPEG |
| Fuera del robot | PC con RTX 3070 | Detección con YOLO, consola web |

### Matek H743

- **Salidas:**
  - **S1–S6:** los 6 servos del brazo, en dos grupos de timer a 50 Hz.
  - **S7–S10:** IN1–IN4 del L298N, en su propio grupo de timer a 490 Hz. ENA y ENB quedan con jumper.
  - **S11–S12:** libres.
- **Motores:**
  - Script Lua en la SD de la placa. Para cada motor, un pin recibe PWM y el otro queda en 0. El ciclo de trabajo máximo es 0,55, unos 6 V promedio con la 3S.
  - Mientras la placa está desarmada, las salidas S7–S10 no emiten pulsos (`Q_M_SAFE_DISARM = 1`).
- **Estabilización:** la IMU estima la orientación de la base y el brazo compensa el roll y el pitch.
- **Enlace con la Radxa:** pads TX1/RX1 (SERIAL2) a `/dev/ttyS5` de la Radxa (pines 32 y 33), MAVLink 2 a 115200 baudios, con GND común.

### Alimentación (LiPo 3S)

| Destino | Fuente | Notas |
|---|---|---|
| H743 | Entrada de batería de la placa | Acepta de 9 a 36 V |
| Servos (4 MG995 y 2 SG90) | Vx de la Matek a 6 V (unos 8 A) | 6 V es el máximo para los SG90 |
| Radxa y cámara | Pad de 5 V de la Matek (2 A) o un power bank | Consumo estimado de 0,8–1,4 A |
| Motores TT | L298N directo de la 3S | El voltaje se limita por PWM |

### Cámara

- DECXIN USB, global shutter y monocromática.
- MJPEG nativo: 1280×720 hasta 120 fps y 640×480 hasta 210 fps.
- El campo de visión está por medir.

### Sensores

- IMU de la H743 (giroscopio y acelerómetro).
- Sin encoders en las ruedas ni en los servos.

### Red

WiFi de 5 GHz con WPA3. Medido en la red del evento:

- **Latencia de ida y vuelta:** unos 5 ms de mediana.
- **Radxa → PC:** unos 85 Mbit/s.
- **PC → Radxa:** unos 45 Mbit/s.

## 3. Software

### Consola web (Next.js 16 y TypeScript, servida en local desde el PC)

- **Ejecución:** se sirve por HTTP en la red local, no desde Vercel. Una página HTTPS no puede conectarse a `ws://` ni cargar video desde `http://`. La versión en Vercel queda solo como demo del simulador.
- **Control:**
  - **Manual:** joystick o teclado, 5 articulaciones más la pinza, y 6 posturas predefinidas.
  - **Misiones:** inicio y parada de tres misiones autónomas, con su configuración (zona y punto de entrega en el mapa, clases de objeto, distancias, texto de saludo).
  - **Parada de emergencia:** botón o barra espaciadora.
- **Visualización:**
  - **Mapa:** visto desde arriba, con la posición, el recorrido, el campo de visión y las detecciones.
  - **Brazo:** vista lateral calculada a partir de los ángulos.
  - **Datos del robot:** telemetría (incluida la orientación de la IMU) y registro de eventos.
  - **Video en vivo** de la cámara del robot, con las detecciones de YOLO superpuestas.
- **Voz:** reconocimiento de órdenes y lectura en voz alta en español, con la API Web Speech.
- **Simulador integrado:** física de tracción diferencial, cinemática del brazo y máquinas de estado de las 3 misiones, con el mismo protocolo que el robot.

### Puente del robot (Python 3, asyncio, en la Radxa)

- **Comunicación:**
  - Servidor WebSocket en el puerto 8765 con un protocolo JSON de 11 mensajes hacia el robot y 5 de vuelta.
  - Telemetría a 15 Hz y detecciones a 5 Hz.
- **Hardware:** MAVLink 2 hacia la H743 con pymavlink. Recibe la orientación (`ATTITUDE`) y envía las órdenes de los servos y los motores.
- **Control:**
  - Lazo de 50 Hz con movimiento de articulaciones a velocidad limitada (90°/s) y límites por articulación.
  - Freno automático si deja de llegar el mando.
  - **Odometría:** el desplazamiento se estima a partir de la velocidad mandada y el rumbo se corrige con el giroscopio de la H743.
- **Primitivas de movimiento:** ir a un punto por odometría, girar hacia un punto, buscar girando y acercarse guiado por la cámara (centrar el recuadro y avanzar hasta que alcance un tamaño dado). Con ellas están hechas las 3 misiones.
- **Modo `--mock`:** hardware simulado y un mundo falso en lazo cerrado.

### Video (Radxa)

- ustreamer como servicio del sistema. Reenvía el MJPEG de la cámara sin recomprimirlo, a 1280×720 y 30 fps, unos 15 Mbit/s.
- Puerto 8080: `/stream` para el video y `/snapshot` para una foto.

### Visión (PC con RTX 3070)

- OpenCV más YOLO de Ultralytics con su modelo propio y una tabla de clases configurable.
- Lee el video desde `http://<radxa>:8080/stream` y envía las detecciones al puente.
- Las clases se eligen por forma, no por color, porque la cámara es monocromática.

## 4. Estado de las pruebas

### Verificado en hardware real

- **H743:** servos estabilizados por la IMU, con los dos ejes compensando correctamente.
- **Motores:** rampa de 0 a 55 % en 10 s, lineal y simétrica en las dos ruedas, sin pulsos en reposo.
- **Radxa ↔ H743:** MAVLink 2 en los dos sentidos.
- **Video:** 30 fps a 1280×720 recibidos en el PC por el WiFi del evento.
- **Red:** latencia y ancho de banda medidos, sin aislamiento entre dispositivos.

### Verificado en software

- CAD sin interferencias, volúmenes comparados con cálculos a mano y rangos de las articulaciones calculados.
- Consola: compila, y las 3 misiones funcionan con el simulador en el navegador.
- Puente: las 3 misiones funcionan en modo simulado, y la consola conectada al puente funciona de punta a punta, parada de emergencia incluida.

### Sin verificar

- Nada impreso.
- Medidas nominales de los servos, los motores y los horns.
- Puente conectado a la H743 real, en vez del modo simulado.
- Estabilización del brazo completo montado sobre el rover.
- YOLO en el PC con la cámara del robot, el modelo propio y la calibración de la cámara.

## 5. Límites técnicos

- **Posición aproximada:** sin encoders, la posición se desvía con el tiempo. El giroscopio corrige el rumbo, pero no la distancia recorrida. No hay mapeo ni localización.
- **Estabilización:** compensa las rotaciones de la base (roll y pitch). No compensa desplazamientos, porque una IMU sola no mide la posición de forma confiable.
- **Servos de lazo abierto:** el MG995 no informa su posición real, tiene holgura y vibra.
- **Carga y estabilidad:** el brazo levanta poco y la base es chica para su peso cuando está estirado. Se mitiga acercando el rover y poniendo la batería atrás como contrapeso.
- **Guiado solo por imagen:** sin profundidad, la distancia se estima por el tamaño del recuadro.
- **Cámara monocromática:** no distingue colores, y los modelos entrenados con imágenes a color pierden algo de precisión.
- **Dependencia del WiFi:** la detección corre en el PC, así que si se cae la red el robot pierde la visión. La estabilización y la parada por falta de mando siguen funcionando, porque no dependen del WiFi.
- **Pinza:** los dientes de los engranajes son escalonados, no de perfil involuta.

## 6. Diferencias con el repositorio actual

El código está alineado con estos specs: el puente usa MAVLink hacia la H743 (`robot_bridge/`, `h743/nexa.lua`), el rumbo sale de la IMU, el video es ustreamer, YOLO corre en el PC (`pc_vision/`) y la consola muestra la orientación y el estado de los enlaces. Falta verificarlo en hardware:

- El puente conectado a la H743 real (solo probado con la H743 simulada).
- `nexa.lua` en la placa: si su script ya verificado usa otra forma de recibir las órdenes, hay que adoptar `nexa.lua` o adaptar la tabla de canales (`h743/README.md`).
- El cliente de visión con la cámara, el modelo propio y la GPU (solo probado el envío de detecciones con un cliente falso).

Nota de alimentación: 4 MG995 pueden pedir ~10 A de pico si se traban a la vez, por encima de los ~8 A del Vx. Conviene no mover los cuatro con carga al mismo tiempo, o medir la caída de tensión en una prueba.
