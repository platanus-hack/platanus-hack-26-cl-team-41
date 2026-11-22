# Nexa · Consola del robot

Panel web para el robot móvil con brazo (4 × MG995, 2 × SG90, 2 motores TT con L298N).
Hecho con Next.js 16, TypeScript y Tailwind. Con el robot se sirve **en local desde el PC** (HTTP en la red del robot); la versión en Vercel sirve solo como demo del simulador.

## Modos

| Modo | Qué hace |
|---|---|
| **Ordenar zona** | Dibujas la zona en el mapa y el punto de entrega, eliges qué clases recoger. El robot barre la zona, reconoce objetos, los toma y los lleva a la entrega. |
| **Asistente** | Te sigue a la distancia que elijas. Le pides herramientas (botón o voz: «pásame el alicate») y te las trae; le das materiales («recibe estos tornillos») y los lleva al contenedor. |
| **Saludo** | Recorre el área buscando personas, se acerca y saluda con el brazo y la voz. Con la cámara local encendida, cada persona que vea tu cámara dispara un saludo real. |
| **Control manual** | Joystick (o W A S D) para las ruedas, un control por articulación, pinza y posturas. |

Barra espaciadora o el botón rojo: **parada de emergencia**.

## Simulador

Sin robot conectado la consola arranca un simulador en el navegador que habla el mismo protocolo,
así que todos los modos funcionan para la demo. En el mapa puedes arrastrar personas, agregar gente y
esparcir objetos.

## Conectar el robot

El robot (Raspberry Pi, Jetson o PC junto al robot) expone un **WebSocket** con mensajes JSON. El
protocolo completo está en `src/lib/robot/types.ts` (`ClientMessage` / `RobotMessage`) y en la vista
**Ajustes**. Lo mínimo:

- Recibir `set_mode`, `stop`, `estop`, `drive`, `joints`, `gripper`, `pose_preset`, `assistant_request`, `assistant_confirm`, `person_seen`.
- Enviar `telemetry` (unas 10–20 veces por segundo) y, si los hay, `detections`, `event`, `world` y `stats`.

Las detecciones del modelo que están entrenando se envían con `detections` (`cls`, `confidence`, y `pos`
en metros o `bbox` normalizado sobre el video). El video del robot se muestra si das una URL MJPEG en Ajustes.

**Ojo con HTTPS:** una página en Vercel (https) no puede abrir `ws://` hacia otra máquina. Usa `wss://`
(por ejemplo un túnel de Cloudflare o ngrok hacia el robot) o abre la consola en local (`npm run dev`).

## Desarrollo

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # lo mismo que hace Vercel
```

## Deploy en Vercel (solo demo del simulador)

Una página HTTPS no puede conectarse a `ws://` ni cargar video desde `http://`, así que para manejar el robot usa `npm run dev` o `npm run build && npm start` en el PC.


1. Sube el repositorio a GitHub.
2. En Vercel: **Add New → Project**, importa el repositorio.
3. En **Root Directory** elige `app` (el resto lo detecta solo: Next.js, `npm run build`).
4. Deploy. No necesita variables de entorno.

O desde la terminal, dentro de `app/`: `npx vercel` y luego `npx vercel --prod`.
