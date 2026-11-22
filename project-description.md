# Yunta — El ayudante de obra autónomo y anticipatorio

La construcción es el pilar físico de la civilización (13% del PIB mundial), pero en terreno lleva más de dos décadas estancada: el último gran cambio en las manos de un maestro fueron las herramientas inalámbricas de litio (~2005). En Chile, según la Comisión Nacional de Productividad (CNP) y la Cámara Chilena de la Construcción (CChC), la brecha de productividad frente a referentes de la OCDE alcanza los 52 puntos porcentuales: con los mismos recursos con que un país referente levanta un edificio de 19 pisos, en Chile levantamos 13.

## El problema que atacamos

### 1. Eficiencia en el cuello de botella olvidado: instalaciones y terminaciones
Cuando se piensa en modernizar la construcción se imaginan grúas y hormigón, pero la obra gruesa es apenas un tercio del proyecto. Más de la mitad del tiempo y el esfuerzo está adentro —electricidad, gasfitería, climatización, pintura y tabiquería— donde no entran máquinas gigantes y todo sigue siendo artesanal.

En obra, la jornada se divide en **Trabajo Productivo (TP)**, **Trabajo Contributorio (TC)** y **Trabajo No Contributorio (TNC)**. Tanto estudios internacionales (Construction Industry Institute) como mediciones en edificación en Chile muestran que **menos de la mitad del turno (frecuentemente entre 30% y 45%) es trabajo productivo directo**, mientras entre un **15% y un 25%** se va en traslados, buscar herramientas y acarrear materiales.

### 2. Envejecimiento y desgaste físico del trabajador
Según el estudio de **CIEDESS y el OTIC CChC (2024)**, el **34,6%** de los trabajadores de la construcción en Chile tiene más de 50 años y los jóvenes (15–29 años) cayeron al **15,4%**, poniendo en riesgo el modelo tradicional de maestro y aprendiz.

A esto se suma una carga física severa: trastornos musculoesqueléticos por sobreesfuerzo y posturas forzadas (vigilados bajo el Protocolo TMERT), y caídas desde altura, que según la Mutual de Seguridad CChC representan cerca del 27% de los accidentes graves y ~38% de las muertes por caídas. Lo más valioso en obra son las décadas de criterio en la cabeza del maestro, no su espalda agachándose cientos de veces al día ni bajando de una escalera cada vez que falta una herramienta.

## La solución: IA anticipatoria en obra

**Yunta** es un rover compacto con brazo robótico estabilizado e inteligencia artificial que acompaña al maestro como su compañero de faena.

En una obra con 90 dB de ruido y las manos ocupadas, un robot al que hay que darle comandos por voz o tablet estorba. Yunta funciona como una **instrumentista quirúrgica en pabellón**: su cámara observa continuamente lo que el trabajador hace, **entiende el proceso constructivo** y se adelanta al siguiente paso:

- **Electricidad:** te ve pelando cables → acerca la cinta aislante o conectores antes de que los pidas, y luego prepara el destornillador.
- **Gasfitería:** te ve cortando tubería PVC → acerca lija, adhesivo y fitting.
- **Pintura y tabiquería:** acerca insumos, mantiene tornillos o cinta a mano y recoge herramientas caídas del suelo para evitar agacharse o bajar de la escalera.

## Qué construimos en Platanus Hack 26 (Hardware)

- **Diseño mecánico e impresión 3D (`solidcraft_import/`, `toolhead_13mm/`, `print_jobs/`):** brazo robótico compacto de 5 DOF + pinza (4× MG995 + 2× SG90), base móvil y cabezal sujetador expandible de 13 mm con archivos STEP, STL, URDF y 3MF listos para manufactura.
- **Simulación física y control aprendido (`simulation/`):** simulador en **MuJoCo** + Gymnasium con auditoría física y currículum entrenado de alcance, ruteo y sujeción de herramientas.
- **Control embebido y estabilización activa para obra real:** controladora **Matek H743** con ArduPilot + script Lua que ejecuta **estabilización activa por IMU (Roll, Pitch y Yaw)** para mantener la pinza estable en pisos irregulares, cables y desniveles, con límites de velocidad seguros (`60°/s`).
- **Visión en tiempo real y puente inalámbrico:** **Raspberry Pi 5** con streaming de cámara y puente MAVLink UDP conectado a detección *open-vocabulary* (**YOLO-World**) + calibración por homografía pixel-a-metro para reconocer herramientas nuevas sin reentrenar desde cero.

## Impacto

- **Más obra efectiva:** convertir traslados, búsquedas y acarreos en tiempo productivo directo.
- **Cuidado y dignidad laboral:** reducir sobreesfuerzo físico y bajadas innecesarias de escaleras, extendiendo la vida laboral sana de los maestros y haciendo el oficio atractivo para nuevas generaciones.
- **Preservar el oficio:** un ayudante autónomo que aprende junto al maestro hoy y escala ese conocimiento en *Physical AI* para construir más rápido el futuro.

## Equipo (team-41)

- Claudio Me Ragni Urrutia ([@claudio-ragni](https://github.com/claudio-ragni))
- Vicente Alexis Diaz Madariaga ([@vicentealexisdiaz](https://github.com/vicentealexisdiaz))
- Mateo Eduardo Morales Farias ([@lilteo14](https://github.com/lilteo14))
