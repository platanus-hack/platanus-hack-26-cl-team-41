"use client";

import { Bot, Cable, Cpu, Eye, FileCode2, MonitorPlay, Plug, Unplug, Video } from "lucide-react";
import { useState } from "react";
import { useRobot } from "@/lib/robot/store";
import { Badge, Button, Card, Field, Slider, Toggle, inputCls } from "../ui";

const PROTOCOL = `// Consola -> robot (JSON por WebSocket)
{ "type": "set_mode", "mode": "ordenar" | "asistente" | "saludo" | "manual" | "idle", "config": {...} }
{ "type": "stop" }                      { "type": "estop", "engaged": true }
{ "type": "drive", "v": 0.2, "w": 0.5 } // m/s, rad/s (repetir cada 100 ms; si deja de llegar, frenar)
{ "type": "joints", "joints": [base, hombro, codo, muñeca, giro] }   // grados
{ "type": "gripper", "open": 0.0 .. 1.0 }
{ "type": "pose_preset", "name": "home" | "recoger" | "transportar" | "entregar" | "saludar" | "plegado" }
{ "type": "assistant_request", "request": { "action": "entregar" | "recibir", "item": "Alicate" } }
{ "type": "assistant_confirm" }
{ "type": "person_seen", "source": "browser_camera", "confidence": 0.93 }

// Robot -> consola
{ "type": "telemetry", "telemetry": { mode, phase, task, pose:{x,y,th}, speed:{v,w}, joints:[5], gripper, battery, carrying, estop } }
{ "type": "detections", "detections": [ { id, cls, confidence, pos?:{x,y}, bbox?:[x,y,w,h] (0..1) } ] }
{ "type": "event", "event": { t, level: "info"|"ok"|"warn"|"error", text, speak? } }
{ "type": "world", "world": {...} }     { "type": "stats", "stats": { collected, delivered, received, greeted } }`;

export function AjustesView() {
  const settings = useRobot((s) => s.settings);
  const setSettings = useRobot((s) => s.setSettings);
  const connKind = useRobot((s) => s.connKind);
  const status = useRobot((s) => s.status);
  const detail = useRobot((s) => s.statusDetail);
  const connectSim = useRobot((s) => s.connectSim);
  const connectWs = useRobot((s) => s.connectWs);
  const disconnect = useRobot((s) => s.disconnect);
  const [url, setUrl] = useState(settings.wsUrl);
  const secure = typeof window !== "undefined" && window.location.protocol === "https:";
  const insecureWs = secure && url.startsWith("ws://") && !/^ws:\/\/(localhost|127\.0\.0\.1)/.test(url);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <Card title="Conexión" icon={<Cable size={16} />} actions={<Badge tone={status === "open" ? "ok" : status === "connecting" ? "warn" : "muted"}>{status === "open" ? (connKind === "sim" ? "Simulador activo" : "Conectado") : status === "connecting" ? "Conectando" : "Desconectado"}</Badge>}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="rounded-xl border border-line p-4">
            <div className="flex items-center gap-2 font-medium">
              <MonitorPlay size={16} className="text-accent" /> Simulador
            </div>
            <p className="mt-1 text-xs text-muted">Robot virtual en el navegador. Ideal para la demo o para probar los modos sin hardware.</p>
            <Button className="mt-3 w-full" variant={connKind === "sim" ? "ghost" : "primary"} onClick={connectSim}>
              {connKind === "sim" ? "Reiniciar simulador" : "Usar simulador"}
            </Button>
          </div>
          <div className="rounded-xl border border-line p-4">
            <div className="flex items-center gap-2 font-medium">
              <Cpu size={16} className="text-accent" /> Robot real
            </div>
            <p className="mt-1 text-xs text-muted">El robot expone un WebSocket con el protocolo de abajo (Raspberry Pi, Jetson o PC).</p>
            <input className={`${inputCls} mt-3`} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="wss://robot.ejemplo.com" />
            <div className="mt-2 flex gap-2">
              <Button className="flex-1" variant="primary" onClick={() => connectWs(url)}>
                <Plug size={14} /> Conectar
              </Button>
              {connKind && (
                <Button variant="ghost" onClick={disconnect}>
                  <Unplug size={14} />
                </Button>
              )}
            </div>
          </div>
        </div>
        {detail && <p className="mt-3 text-xs text-muted">Estado: {detail}</p>}
        {insecureWs && (
          <p className="mt-3 rounded-xl border border-warn/30 bg-warn/10 p-3 text-xs text-warn">
            Esta página se abrió con HTTPS (por ejemplo en Vercel), y el navegador bloquea <b>ws://</b> hacia otra máquina. Usa <b>wss://</b> (por ejemplo con un túnel
            de Cloudflare o ngrok hacia el robot) o abre la consola en local.
          </p>
        )}
      </Card>

      <Card title="Robot" icon={<Bot size={16} />}>
        <Field label="Nombre">
          <input className={inputCls} value={settings.robotName} onChange={(e) => setSettings({ robotName: e.target.value })} />
        </Field>
        <Toggle checked={settings.voice} onChange={(v) => setSettings({ voice: v })} label="Leer en voz alta los mensajes del robot" />
        <Slider label="Velocidad máxima en manual" value={settings.maxSpeed} min={0.1} max={0.35} step={0.01} unit=" m/s" onChange={(v) => setSettings({ maxSpeed: v })} />
      </Card>

      <Card title="Visión" icon={<Eye size={16} />}>
        <Field label="Video del robot (MJPEG)" hint="Ej: http://raspberrypi.local:8080/stream.mjpg. Se muestra en «Cámara del robot».">
          <div className="relative">
            <Video size={14} className="absolute left-3 top-3 text-muted" />
            <input className={`${inputCls} pl-9`} value={settings.cameraUrl} onChange={(e) => setSettings({ cameraUrl: e.target.value })} placeholder="http://…/stream.mjpg" />
          </div>
        </Field>
        <Slider label="Confianza mínima (cámara local)" value={settings.minConfidence} min={0.3} max={0.95} step={0.05} onChange={(v) => setSettings({ minConfidence: v })} />
        <Toggle checked={settings.cameraTrigger} onChange={(v) => setSettings({ cameraTrigger: v })} label="La cámara local dispara saludos en modo saludo" />
        <p className="mt-2 text-xs text-muted leading-relaxed">
          La cámara local usa COCO-SSD en el navegador. El modelo que están entrenando corre en el robot y envía sus detecciones con el mensaje
          <code className="mx-1 rounded bg-white/5 px-1">detections</code>: la consola las muestra en el mapa y sobre el video.
        </p>
      </Card>

      <Card title="Protocolo del robot" icon={<FileCode2 size={16} />}>
        <pre className="max-h-[360px] overflow-auto rounded-xl border border-line bg-black/40 p-3 text-[11.5px] leading-relaxed text-text/85 num whitespace-pre">{PROTOCOL}</pre>
      </Card>
    </div>
  );
}
