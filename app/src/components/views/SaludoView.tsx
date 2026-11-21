"use client";

import { Hand, Map as MapIcon, MessageSquareQuote, PersonStanding, UserPlus, Volume2 } from "lucide-react";
import { useRobot } from "@/lib/robot/store";
import { CameraPanel } from "../CameraPanel";
import { EventLog } from "../EventLog";
import { MissionControl, PhaseTimeline } from "../Mission";
import { Button, Card, Slider, Toggle, inputCls } from "../ui";
import { MapToolbar, WorldMap } from "../WorldMap";

const STEPS = ["Buscando personas", "Acercándome", "Saludando"];

export function SaludoView() {
  const cfg = useRobot((s) => s.config.saludo);
  const setConfig = useRobot((s) => s.setConfig);
  const settings = useRobot((s) => s.settings);
  const setSettings = useRobot((s) => s.setSettings);
  const stats = useRobot((s) => s.stats);

  const update = (p: Partial<typeof cfg>) => setConfig((c) => ({ ...c, saludo: { ...c.saludo, ...p } }));
  const sayIt = () => {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(cfg.greeting);
    u.lang = "es-ES";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_1fr] gap-4">
      <div className="space-y-4 min-w-0">
        <MissionControl
          mode="saludo"
          icon={<Hand size={22} />}
          label="Modo saludo"
          description="Recorre el área buscando personas. Cuando encuentra a alguien se acerca, lo saluda con el brazo y le habla."
        />
        <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
          <Card title="Área" icon={<MapIcon size={16} />} actions={<MapToolbar tools={[{ id: "person", label: "Agregar persona", icon: <UserPlus size={14} /> }]} />}>
            <WorldMap show={{ range: cfg.range }} tools={["person"]} className="aspect-[4/3]" />
          </Card>
          <CameraPanel title="Cámara · detector de personas" />
        </div>
        <p className="text-xs text-muted">
          Con la cámara local activa y el modo saludo en curso, cada persona que vea tu cámara dispara un saludo real del robot.
        </p>
      </div>

      <div className="space-y-4 min-w-0">
        <div className="panel relative overflow-hidden p-5">
          <div className="pointer-events-none absolute -right-8 -bottom-10 h-36 w-36 rounded-full bg-accent-2/20 blur-2xl" />
          <div className="label">Personas saludadas</div>
          <div className="mt-1 flex items-end gap-3">
            <span className="text-5xl font-semibold num bg-gradient-to-r from-accent to-accent-2 bg-clip-text text-transparent">{stats.greeted}</span>
            <PersonStanding className="mb-2 text-muted" />
          </div>
        </div>
        <Card title="Lo que dice" icon={<MessageSquareQuote size={16} />}>
          <textarea className={`${inputCls} h-20 py-2 resize-none`} value={cfg.greeting} onChange={(e) => update({ greeting: e.target.value })} />
          <div className="mt-2 flex items-center justify-between">
            <Toggle checked={settings.voice} onChange={(v) => setSettings({ voice: v })} label="Hablar en voz alta" />
            <Button size="sm" variant="ghost" onClick={sayIt}>
              <Volume2 size={14} /> Probar
            </Button>
          </div>
        </Card>
        <Card title="Comportamiento" icon={<Hand size={16} />}>
          <Slider label="Alcance de búsqueda" value={cfg.range} min={0.8} max={3} step={0.1} unit=" m" onChange={(v) => update({ range: v })} />
          <Slider label="No repetir saludo a la misma persona" value={cfg.cooldownS} min={5} max={120} step={5} unit=" s" onChange={(v) => update({ cooldownS: v })} />
          <Toggle checked={settings.cameraTrigger} onChange={(v) => setSettings({ cameraTrigger: v })} label="La cámara local dispara saludos" />
          <div className="mt-3">
            <PhaseTimeline mode="saludo" steps={STEPS} />
          </div>
        </Card>
        <EventLog max={20} />
      </div>
    </div>
  );
}
