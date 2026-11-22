"use client";

import { useRef, useState, type PointerEvent } from "react";
import { useRobot, type MapTool } from "@/lib/robot/store";
import type { Vec2, Zone } from "@/lib/robot/types";
import { cx } from "./ui";

const CLASS_COLOR: Record<string, string> = {
  botella: "#38bdf8",
  taza: "#f472b6",
  lata: "#fbbf24",
  juguete: "#a78bfa",
  tornillo: "#94a3b8",
  libro: "#34d399",
};

const FOV = (40 * Math.PI) / 180;

type Props = {
  show?: { zone?: boolean; stations?: boolean; fov?: boolean; range?: number };
  tools?: MapTool[];
  className?: string;
};

export function WorldMap({ show = {}, tools = [], className }: Props) {
  const world = useRobot((s) => s.world);
  const tel = useRobot((s) => s.telemetry);
  const trail = useRobot((s) => s.trail);
  const detections = useRobot((s) => s.detections);
  const config = useRobot((s) => s.config);
  const setConfig = useRobot((s) => s.setConfig);
  const tool = useRobot((s) => s.mapTool);
  const sim = useRobot((s) => s.sim);
  const svgRef = useRef<SVGSVGElement>(null);
  const [draft, setDraft] = useState<Zone | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);

  const W = world?.size.w ?? 4;
  const H = world?.size.h ?? 3;
  const pad = 0.15;
  const Y = (y: number) => H - y;

  const toWorld = (e: PointerEvent): Vec2 | null => {
    const svg = svgRef.current;
    const m = svg?.getScreenCTM();
    if (!svg || !m) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    return { x: Math.min(W, Math.max(0, p.x)), y: Math.min(H, Math.max(0, H - p.y)) };
  };

  const active = (t: MapTool) => tools.includes(t) && tool === t;

  const onDown = (e: PointerEvent) => {
    const p = toWorld(e);
    if (!p) return;
    if (active("zone")) {
      (e.target as Element).setPointerCapture?.(e.pointerId);
      setDraft({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
    } else if (active("drop")) {
      setConfig((c) => ({ ...c, ordenar: { ...c.ordenar, drop: p } }));
    } else if (active("user")) {
      sim()?.movePerson("user", p);
    } else if (active("person")) {
      sim()?.addPerson(p);
    }
  };
  const onMove = (e: PointerEvent) => {
    const p = toWorld(e);
    if (!p) return;
    if (draft) setDraft({ ...draft, x1: p.x, y1: p.y });
    if (dragId) sim()?.movePerson(dragId, p);
  };
  const onUp = () => {
    if (draft) {
      const z = { x0: Math.min(draft.x0, draft.x1), y0: Math.min(draft.y0, draft.y1), x1: Math.max(draft.x0, draft.x1), y1: Math.max(draft.y0, draft.y1) };
      if (z.x1 - z.x0 > 0.3 && z.y1 - z.y0 > 0.3) setConfig((c) => ({ ...c, ordenar: { ...c.ordenar, zone: z } }));
      setDraft(null);
    }
    setDragId(null);
  };

  const zone = draft
    ? { x0: Math.min(draft.x0, draft.x1), y0: Math.min(draft.y0, draft.y1), x1: Math.max(draft.x0, draft.x1), y1: Math.max(draft.y0, draft.y1) }
    : config.ordenar.zone;
  const drop = config.ordenar.drop;
  const detIds = new Set(detections.map((d) => d.id));
  const pose = tel?.pose;
  const range = show.range ?? 1.5;

  const grid: number[] = [];
  for (let g = 0.5; g < Math.max(W, H); g += 0.5) grid.push(g);

  return (
    <div className={cx("relative w-full overflow-hidden rounded-xl border border-line bg-black/30", className)}>
      <svg
        ref={svgRef}
        viewBox={`${-pad} ${-pad} ${W + 2 * pad} ${H + 2 * pad}`}
        className={cx("block w-full h-full touch-none", tool !== "none" && tools.includes(tool) && "cursor-crosshair")}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
        role="img"
        aria-label="Mapa del área de trabajo"
      >
        <defs>
          <radialGradient id="fovGrad" cx="0" cy="0.5" r="1">
            <stop offset="0" stopColor="#22d3ee" stopOpacity="0.28" />
            <stop offset="1" stopColor="#22d3ee" stopOpacity="0" />
          </radialGradient>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="0.025" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* floor + grid */}
        <rect x={0} y={0} width={W} height={H} rx={0.06} fill="#0b1018" stroke="rgba(148,163,184,0.35)" strokeWidth={0.012} />
        {grid.map((g) => (
          <g key={g} stroke="rgba(148,163,184,0.08)" strokeWidth={0.006}>
            {g < W && <line x1={g} y1={0} x2={g} y2={H} />}
            {g < H && <line x1={0} y1={g} x2={W} y2={g} />}
          </g>
        ))}
        {[1, 2, 3].map((m) => (
          <text key={m} x={m} y={H + 0.11} fontSize={0.07} fill="#64748b" textAnchor="middle" className="num">
            {m} m
          </text>
        ))}

        {/* cleaning zone */}
        {show.zone && (
          <g>
            <rect
              x={zone.x0}
              y={Y(zone.y1)}
              width={zone.x1 - zone.x0}
              height={zone.y1 - zone.y0}
              fill="rgba(34,211,238,0.06)"
              stroke="#22d3ee"
              strokeDasharray="0.05 0.035"
              strokeWidth={0.012}
              rx={0.03}
            />
            <text x={zone.x0 + 0.05} y={Y(zone.y1) + 0.11} fontSize={0.075} fill="#22d3ee" fontWeight={600}>
              Zona a ordenar
            </text>
            <g transform={`translate(${drop.x} ${Y(drop.y)})`}>
              <rect x={-0.17} y={-0.17} width={0.34} height={0.34} rx={0.04} fill="rgba(52,211,153,0.10)" stroke="#34d399" strokeWidth={0.012} />
              <text y={-0.21} fontSize={0.07} fill="#34d399" textAnchor="middle" fontWeight={600}>
                Entrega
              </text>
            </g>
          </g>
        )}

        {/* assistant stations */}
        {show.stations && world && (
          <g>
            <Station p={world.toolStation} H={H} color="#fbbf24" label="Herramientas" />
            <Station p={world.materialBin} H={H} color="#a78bfa" label="Contenedor" />
          </g>
        )}

        {/* trail */}
        {trail.length > 1 && (
          <polyline
            points={trail.map((p) => `${p.x},${Y(p.y)}`).join(" ")}
            fill="none"
            stroke="rgba(34,211,238,0.35)"
            strokeWidth={0.012}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* objects */}
        {world?.objects.map((o) => {
          if (o.state === "carried") return null;
          const c = CLASS_COLOR[o.cls] ?? "#e2e8f0";
          const seen = detIds.has(o.id);
          return (
            <g key={o.id} transform={`translate(${o.pos.x} ${Y(o.pos.y)})`} opacity={o.state === "stored" ? 0.45 : 1}>
              {seen && <circle r={0.1} fill="none" stroke={c} strokeWidth={0.01} className="pulse-ring" />}
              <circle r={0.045} fill={c} stroke="#0b1018" strokeWidth={0.01} />
              {o.state === "free" && (
                <text y={-0.07} fontSize={0.06} fill={c} textAnchor="middle">
                  {o.cls}
                </text>
              )}
            </g>
          );
        })}

        {/* people */}
        {world?.people.map((p) => (
          <g
            key={p.id}
            transform={`translate(${p.pos.x} ${Y(p.pos.y)})`}
            onPointerDown={(e) => {
              if (sim()) {
                e.stopPropagation();
                (e.target as Element).setPointerCapture?.(e.pointerId);
                setDragId(p.id);
              }
            }}
            className={sim() ? "cursor-grab" : undefined}
          >
            {detIds.has(p.id) && <circle r={0.2} fill="none" stroke="#f472b6" strokeWidth={0.01} className="pulse-ring" />}
            <circle r={0.12} fill={p.isUser ? "rgba(34,211,238,0.18)" : "rgba(244,114,182,0.16)"} stroke={p.isUser ? "#22d3ee" : "#f472b6"} strokeWidth={0.014} />
            <circle r={0.045} cy={-0.02} fill={p.isUser ? "#22d3ee" : "#f472b6"} />
            <path d="M -0.07 0.07 Q 0 0.0 0.07 0.07" fill="none" stroke={p.isUser ? "#22d3ee" : "#f472b6"} strokeWidth={0.02} strokeLinecap="round" />
            <text y={0.22} fontSize={0.07} fill="#e2e8f0" textAnchor="middle" fontWeight={600}>
              {p.name}
            </text>
          </g>
        ))}

        {/* robot */}
        {pose && (
          <g transform={`translate(${pose.x} ${Y(pose.y)}) rotate(${(-pose.th * 180) / Math.PI})`} filter="url(#glow)">
            {show.fov !== false && (
              <path
                d={`M 0 0 L ${range * Math.cos(FOV)} ${-range * Math.sin(FOV)} A ${range} ${range} 0 0 1 ${range * Math.cos(FOV)} ${range * Math.sin(FOV)} Z`}
                fill="url(#fovGrad)"
                stroke="rgba(34,211,238,0.25)"
                strokeWidth={0.006}
              />
            )}
            <rect x={-0.032} y={-0.113} width={0.065} height={0.026} rx={0.008} fill="#1f2937" />
            <rect x={-0.032} y={0.087} width={0.065} height={0.026} rx={0.008} fill="#1f2937" />
            <rect x={-0.089} y={-0.085} width={0.178} height={0.17} rx={0.03} fill="#d7dadf" stroke="#22d3ee" strokeWidth={0.01} />
            <circle r={0.05} fill="#9aa3ad" stroke="#0b1018" strokeWidth={0.008} />
            <path d="M 0.04 -0.03 L 0.085 0 L 0.04 0.03 Z" fill="#0b1018" />
            {tel?.carrying && <circle cx={0.15} r={0.035} fill="#fbbf24" stroke="#0b1018" strokeWidth={0.008} />}
          </g>
        )}
      </svg>

      {!world && (
        <div className="absolute inset-0 grid place-items-center text-sm text-muted">Sin datos del mundo: conecta el simulador o el robot.</div>
      )}
    </div>
  );
}

function Station({ p, H, color, label }: { p: Vec2; H: number; color: string; label: string }) {
  return (
    <g transform={`translate(${p.x} ${H - p.y})`}>
      <rect x={-0.16} y={-0.16} width={0.32} height={0.32} rx={0.05} fill={`${color}1a`} stroke={color} strokeWidth={0.012} />
      <text y={0.24} fontSize={0.07} fill={color} textAnchor="middle" fontWeight={600}>
        {label}
      </text>
    </g>
  );
}

export function MapToolbar({ tools }: { tools: { id: MapTool; label: string; icon: React.ReactNode }[] }) {
  const tool = useRobot((s) => s.mapTool);
  const setTool = useRobot((s) => s.setMapTool);
  return (
    <div className="flex flex-wrap gap-1.5">
      {tools.map((t) => (
        <button
          key={t.id}
          onClick={() => setTool(tool === t.id ? "none" : t.id)}
          className={cx(
            "inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium border transition",
            tool === t.id ? "bg-accent/15 border-accent/50 text-accent" : "bg-white/[0.03] border-line text-muted hover:text-text",
          )}
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </div>
  );
}
