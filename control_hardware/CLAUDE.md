# Rover con brazo (PlatanusHack)

- Antes de mover el brazo, leer [firmware/BRAZO_CONTROL.md](firmware/BRAZO_CONTROL.md): sentidos verificados, límites, posturas y reglas de seguridad.
- Hardware: Matek H743 (ArduPlane 4.5.7, USB = COM4). La Radxa se dañó; ahora va una **Raspberry Pi 5** (`ssh rover-wifi`, 172.16.0.127 en PlatanusHack; `ssh rover` por Ethernet IPv6 link-local, solo con el ssh de Git). Usuario pi, sudo sin contraseña; credenciales en ~/.rover/.
- Pi 5: cámara en http://172.16.0.127:8080/stream (`camara` = ustreamer en 127.0.0.1:8081; `camara-giro` la publica girada 180° en 8080), H743 por UART pines 8/10 (/dev/ttyAMA0) y puente MAVLink UDP 14550 (servicio `mav-puente`, ver `rpi/`). Desde el PC: `udpout:172.16.0.127:14550`.
- Herramientas en `firmware/tools/`. Todo cambio de parámetros pasa por `apply_params.py`, que respalda antes en `firmware/backups/`.
- Nunca mover servos sin límite de velocidad ni hacia los extremos de su recorrido. Si algo se ve mal, la primera acción es `brazo_off.param` (`SCR_ENABLE = 0`).
