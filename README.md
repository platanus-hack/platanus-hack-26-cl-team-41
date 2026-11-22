# Yunta

<img src="./project-logo.png" alt="Yunta Logo" width="200" />

**Track:** 🔧 Hardware — **Platanus Hack 26: Santiago ft. Buk** (`team-41`)

**Yunta** es un ayudante de obra robótico con ruedas, brazo estabilizado e IA anticipatoria. Observa continuamente al maestro con su cámara, entiende el proceso constructivo (electricidad, gasfitería, pintura, terminaciones) y se adelanta para acercar la siguiente herramienta o recoger objetos del suelo antes de que los pida.

## Equipo

- Claudio Me Ragni Urrutia ([@claudio-ragni](https://github.com/claudio-ragni))
- Vicente Alexis Diaz Madariaga ([@vicentealexisdiaz](https://github.com/vicentealexisdiaz))
- Mateo Eduardo Morales Farias ([@lilteo14](https://github.com/lilteo14))

## Arquitectura y componentes

- **Mecánica y CAD (`solidcraft_import/`, `toolhead_13mm/`, `design/`, `print_jobs/`):** brazo robótico compacto de 5 DOF + pinza (4× MG995 + 2× SG90), chasis móvil, cabezal sujetador de 13 mm y proyectos 3MF listos para impresión 3D.
- **Simulación y entrenamiento (`simulation/`):** entorno físico en MuJoCo + Gymnasium con modelos entrenados de alcance, ruteo y acople de herramienta. Ver [PROJECT_FILES.md](./PROJECT_FILES.md) para instrucciones de ejecución.
- **Control embebido y visión (hardware en terreno):** controladora Matek H743 (ArduPilot + Lua con estabilización activa IMU en Roll/Pitch/Yaw y límite seguro de 60°/s), puente MAVLink UDP y cámara en Raspberry Pi 5, y detección *open-vocabulary* (YOLO-World) con calibración por homografía.

Para ver la descripción completa del impacto, contexto y motivación del proyecto, revisa [project-description.md](./project-description.md).
