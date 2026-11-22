"use client";

import { Crosshair, ListChecks, Map as MapIcon, Package, RotateCcw, Shapes, SquareDashed, Sparkles } from "lucide-react";
import { useRobot } from "@/lib/robot/store";
import { OBJECT_CLASSES } from "@/lib/robot/types";
import { CameraPanel } from "../CameraPanel";
import { EventLog } from "../EventLog";
import { MissionControl, PhaseTimeline } from "../Mission";
import { Badge, Button, Card, cx } from "../ui";
import { MapToolbar, WorldMap } from "../WorldMap";

const STEPS = ["Patrullando", "Objeto detectado", "Aproximando", "Agarrando", "Transportando", "Depositando", "Completado"];

export function OrdenarView() {
  const config = useRobot((s) => s.config.ordenar);
  const setConfig = useRobot((s) => s.setConfig);
  const world = useRobot((s) => s.world);
  const stats = useRobot((s) => s.stats);
  const sim = useRobot((s) => s.sim);
  const isSim = useRobot((s) => s.connKind === "sim");
  const z = config.zone;

  const inZone = (p: { x: number; y: number }) => p.x >= z.x0 && p.x <= z.x1 && p.y >= z.y0 && p.y <= z.y1;
  const pending = world?.objects.filter((o) => o.state === "free" && config.classes.includes(o.cls) && inZone(o.pos)).length ?? 0;

  const toggle = (cls: string) =>
    setConfig((c) => {
      const has = c.ordenar.classes.includes(cls);
      return { ...c, ordenar: { ...c.ordenar, classes: has ? c.ordenar.classes.filter((x) => x !== cls) : [...c.ordenar.classes, cls] } };
    });

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_1fr] gap-4">
      <div className="space-y-4 min-w-0">
        <MissionControl
          mode="ordenar"
          icon={<Package size={22} />}
          label="Ordenar zona"
          description="El robot barre la zona delimitada, reconoce los objetos con la IA, los toma y los deja en el punto de entrega."
        />
        <Card
          title="Zona de trabajo"
          icon={<MapIcon size={16} />}
          actions={
            <MapToolbar
              tools={[
                { id: "zone", label: "Dibujar zona", icon: <SquareDashed size={14} /> },
                { id: "drop", label: "Punto de entrega", icon: <Crosshair size={14} /> },
              ]}
            />
          }
        >
          <WorldMap show={{ zone: true, range: 0.9 }} tools={["zone", "drop"]} className="aspect-[4/3]" />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span className="num">
              Zona {(z.x1 - z.x0).toFixed(2)} × {(z.y1 - z.y0).toFixed(2)} m · entrega en ({config.drop.x.toFixed(2)}, {config.drop.y.toFixed(2)}) m
            </span>
            {isSim && (
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => sim()?.scatterObjects(4)}>
                  <Sparkles size={14} /> Esparcir objetos
                </Button>
                <Button size="sm" variant="ghost" onClick={() => sim()?.resetWorld()}>
                  <RotateCcw size={14} /> Reiniciar
                </Button>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="space-y-4 min-w-0">
        <div className="grid grid-cols-2 gap-3">
          <div className="panel p-4">
            <div className="label">Guardados</div>
            <div className="mt-1 text-3xl font-semibold text-ok num">{stats.collected}</div>
          </div>
          <div className="panel p-4">
            <div className="label">Pendientes en zona</div>
            <div className="mt-1 text-3xl font-semibold text-accent num">{pending}</div>
          </div>
        </div>
        <Card title="Progreso" icon={<ListChecks size={16} />}>
          <PhaseTimeline mode="ordenar" steps={STEPS} />
        </Card>
        <Card title="Qué recoger" icon={<Shapes size={16} />} actions={<Badge tone="accent">{config.classes.length} clases</Badge>}>
          <div className="flex flex-wrap gap-2">
            {OBJECT_CLASSES.map((c) => {
              const on = config.classes.includes(c);
              return (
                <button
                  key={c}
                  onClick={() => toggle(c)}
                  className={cx(
                    "h-8 rounded-full border px-3 text-sm capitalize transition",
                    on ? "border-accent/50 bg-accent/15 text-accent" : "border-line text-muted hover:text-text",
                  )}
                >
                  {c}
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-muted">Las clases deben coincidir con las etiquetas de tu modelo de reconocimiento.</p>
        </Card>
        <CameraPanel compact title="Visión del robot" />
        <EventLog max={20} />
      </div>
    </div>
  );
}
