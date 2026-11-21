"use client";

import { ArrowRight, Battery, Gauge, Hand, Handshake, Map as MapIcon, Package, PersonStanding } from "lucide-react";
import { useRobot } from "@/lib/robot/store";
import { MODE_LABEL } from "@/lib/robot/types";
import { ArmView } from "../ArmView";
import { CameraPanel } from "../CameraPanel";
import { EventLog } from "../EventLog";
import type { View } from "../Shell";
import { Card, Stat } from "../ui";
import { WorldMap } from "../WorldMap";

export function PanelView({ onView }: { onView: (v: View) => void }) {
  const tel = useRobot((s) => s.telemetry);
  const stats = useRobot((s) => s.stats);
  const name = useRobot((s) => s.settings.robotName);
  const bat = tel?.battery ?? 0;

  const modes = [
    { id: "ordenar" as const, title: "Ordenar zona", text: "Recorre una zona, reconoce objetos y los lleva al punto de entrega.", icon: <Package size={20} /> },
    { id: "asistente" as const, title: "Asistente", text: "Te sigue, te alcanza herramientas y recibe materiales.", icon: <Handshake size={20} /> },
    { id: "saludo" as const, title: "Saludo", text: "Busca personas y las saluda. Ideal para demos.", icon: <Hand size={20} /> },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label">Panel general</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Hola, soy {name}</h1>
          <p className="text-sm text-muted">Robot móvil con brazo de 6 servos · 2 motores TT · visión con IA</p>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
        <Stat label="Modo" value={tel ? MODE_LABEL[tel.mode] : "—"} sub={tel?.phase} icon={<Gauge size={18} />} tone="accent" />
        <Stat label="Batería" value={tel ? `${bat.toFixed(0)} %` : "—"} sub={tel?.carrying ? `Lleva: ${tel.carrying}` : "Sin carga"} icon={<Battery size={18} />} tone={bat > 25 ? "ok" : "danger"} />
        <Stat label="Objetos ordenados" value={stats.collected} icon={<Package size={18} />} />
        <Stat label="Entregas / recepciones" value={`${stats.delivered} / ${stats.received}`} icon={<Handshake size={18} />} />
        <Stat label="Personas saludadas" value={stats.greeted} icon={<PersonStanding size={18} />} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {modes.map((m) => (
          <button key={m.id} onClick={() => onView(m.id)} className="panel group p-4 text-left transition hover:border-accent/40 hover:-translate-y-0.5">
            <div className="flex items-center justify-between">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent/10 text-accent border border-accent/25">{m.icon}</div>
              <ArrowRight size={16} className="text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
            </div>
            <div className="mt-3 font-semibold">{m.title}</div>
            <div className="mt-1 text-sm text-muted">{m.text}</div>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-4">
        <Card title="Mapa en vivo" icon={<MapIcon size={16} />}>
          <WorldMap show={{ zone: true, stations: true }} className="aspect-[4/3]" />
        </Card>
        <div className="space-y-4">
          <Card title="Brazo" icon={<Gauge size={16} />}>
            <ArmView />
          </Card>
          <CameraPanel compact />
        </div>
      </div>
      <EventLog />
    </div>
  );
}
