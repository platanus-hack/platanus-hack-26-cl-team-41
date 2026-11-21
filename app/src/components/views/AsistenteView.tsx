"use client";

import { CheckCircle2, Handshake, Inbox, Map as MapIcon, Mic, MicOff, PersonStanding, Wrench } from "lucide-react";
import { useState } from "react";
import { useRobot } from "@/lib/robot/store";
import { TOOLS, type AssistantRequest } from "@/lib/robot/types";
import { listenOnce, parseCommand, speechSupported } from "@/lib/voice";
import { EventLog } from "../EventLog";
import { MissionControl, PhaseTimeline } from "../Mission";
import { Badge, Button, Card, inputCls, Slider } from "../ui";
import { MapToolbar, WorldMap } from "../WorldMap";

const STEPS = ["Acompañando", "Buscando herramienta", "Llevando", "Entregando", "Recibiendo", "Esperando material", "Guardando"];

export function AsistenteView() {
  const tel = useRobot((s) => s.telemetry);
  const online = useRobot((s) => s.status === "open");
  const send = useRobot((s) => s.send);
  const log = useRobot((s) => s.log);
  const follow = useRobot((s) => s.config.asistente.followDistance);
  const setConfig = useRobot((s) => s.setConfig);
  const stats = useRobot((s) => s.stats);
  const [material, setMaterial] = useState("");
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState("");

  const request = (r: AssistantRequest) => send({ type: "assistant_request", request: r });
  const waiting = tel?.mode === "asistente" && (tel.phase === "Entregando" || tel.phase === "Esperando material");

  const voice = async () => {
    setListening(true);
    setHeard("");
    try {
      const text = await listenOnce();
      setHeard(text);
      const cmd = parseCommand(text);
      if (cmd === "confirm") send({ type: "assistant_confirm" });
      else if (cmd) request(cmd);
      else log("warn", `No entendí «${text}». Prueba: «pásame el alicate» o «recibe estos tornillos».`);
    } catch (e) {
      log("error", e instanceof Error ? e.message : "Error de voz");
    } finally {
      setListening(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_1fr] gap-4">
      <div className="space-y-4 min-w-0">
        <MissionControl
          mode="asistente"
          icon={<Handshake size={22} />}
          label="Asistente de taller"
          description="Se mantiene cerca tuyo, te trae herramientas de la estación y se lleva los materiales que le entregues al contenedor."
        />

        {waiting && (
          <div className="panel border-accent/50 bg-accent/10 p-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-semibold text-accent">{tel?.phase === "Entregando" ? "Te está entregando algo" : "Esperando tu material"}</div>
              <div className="text-sm text-text/80">{tel?.task}</div>
            </div>
            <Button variant="primary" size="lg" onClick={() => send({ type: "assistant_confirm" })}>
              <CheckCircle2 size={18} /> {tel?.phase === "Entregando" ? "Ya lo tomé" : "Listo, guárdalo"}
            </Button>
          </div>
        )}

        <Card
          title="Taller"
          icon={<MapIcon size={16} />}
          actions={<MapToolbar tools={[{ id: "user", label: "Mover mi posición", icon: <PersonStanding size={14} /> }]} />}
        >
          <WorldMap show={{ stations: true, range: 1.2 }} tools={["user"]} className="aspect-[4/3]" />
          <p className="mt-2 text-xs text-muted">En el simulador puedes arrastrar tu marcador («Tú») y el robot te sigue.</p>
        </Card>
      </div>

      <div className="space-y-4 min-w-0">
        <Card title="Pedir herramienta" icon={<Wrench size={16} />} actions={<Badge tone="ok">{stats.delivered} entregadas</Badge>}>
          <div className="grid grid-cols-2 gap-2">
            {TOOLS.map((t) => (
              <Button key={t} onClick={() => request({ action: "entregar", item: t })} disabled={!online} className="justify-start">
                <Wrench size={14} className="text-accent" /> {t}
              </Button>
            ))}
          </div>
        </Card>

        <Card title="Entregarle material" icon={<Inbox size={16} />} actions={<Badge tone="ok">{stats.received} recibidos</Badge>}>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              request({ action: "recibir", item: material.trim() || "material" });
              setMaterial("");
            }}
          >
            <input className={inputCls} placeholder="Ej: tornillos sobrantes" value={material} onChange={(e) => setMaterial(e.target.value)} />
            <Button type="submit" variant="primary" disabled={!online}>
              Recibir
            </Button>
          </form>
        </Card>

        <Card title="Comando de voz" icon={<Mic size={16} />}>
          <div className="flex items-center gap-3">
            <Button variant={listening ? "danger" : "primary"} onClick={voice} disabled={listening || !speechSupported() || !online}>
              {listening ? <MicOff size={16} /> : <Mic size={16} />} {listening ? "Escuchando…" : "Hablar"}
            </Button>
            <div className="text-sm text-muted min-w-0">
              {heard ? <>Escuché: «<span className="text-text">{heard}</span>»</> : speechSupported() ? "«Pásame el destornillador», «recibe estos tornillos», «listo»" : "Tu navegador no reconoce voz (usa Chrome o Edge)."}
            </div>
          </div>
        </Card>

        <Card title="Comportamiento" icon={<PersonStanding size={16} />}>
          <Slider
            label="Distancia de seguimiento"
            value={follow}
            min={0.4}
            max={1.5}
            step={0.05}
            unit=" m"
            onChange={(v) => setConfig((c) => ({ ...c, asistente: { followDistance: v } }))}
          />
          <div className="mt-3">
            <PhaseTimeline mode="asistente" steps={STEPS} />
          </div>
        </Card>
        <EventLog max={20} />
      </div>
    </div>
  );
}
