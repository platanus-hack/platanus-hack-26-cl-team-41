"use client";

import { Check, Play, Square } from "lucide-react";
import type { ReactNode } from "react";
import { useRobot } from "@/lib/robot/store";
import type { Mode } from "@/lib/robot/types";
import { Button, cx } from "./ui";

export function MissionControl({ mode, label, description, icon }: { mode: Mode; label: string; description: string; icon: ReactNode }) {
  const tel = useRobot((s) => s.telemetry);
  const online = useRobot((s) => s.status === "open");
  const startMode = useRobot((s) => s.startMode);
  const stop = useRobot((s) => s.stop);
  const running = tel?.mode === mode;
  return (
    <div className="panel relative overflow-hidden p-5">
      <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-accent/10 blur-2xl" />
      <div className="flex items-start gap-4">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-accent/10 text-accent border border-accent/30">{icon}</div>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-tight">{label}</h1>
          <p className="mt-1 text-sm text-muted leading-relaxed">{description}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {running ? (
          <Button variant="ghost" onClick={stop}>
            <Square size={14} /> Detener misión
          </Button>
        ) : (
          <Button variant="primary" onClick={() => startMode(mode)} disabled={!online}>
            <Play size={14} /> Iniciar
          </Button>
        )}
        {running && (
          <span className="inline-flex items-center gap-2 text-sm text-accent">
            <span className="h-2 w-2 rounded-full bg-accent animate-pulse" /> En curso · {tel?.phase}
          </span>
        )}
        {!online && <span className="text-xs text-muted">Conecta el simulador o el robot para iniciar.</span>}
      </div>
    </div>
  );
}

export function PhaseTimeline({ mode, steps }: { mode: Mode; steps: string[] }) {
  const tel = useRobot((s) => s.telemetry);
  const running = tel?.mode === mode;
  const idx = running ? steps.findIndex((s) => tel!.phase.toLowerCase().startsWith(s.toLowerCase())) : -1;
  return (
    <ol className="relative space-y-0.5">
      {steps.map((s, i) => {
        const state = idx === -1 ? "todo" : i < idx ? "done" : i === idx ? "now" : "todo";
        return (
          <li key={s} className="flex items-center gap-3 py-1.5">
            <span
              className={cx(
                "grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[11px] font-semibold",
                state === "now" && "border-accent bg-accent text-[#04141a] shadow-[0_0_16px_-2px_var(--accent)]",
                state === "done" && "border-ok/40 bg-ok/15 text-ok",
                state === "todo" && "border-line text-muted",
              )}
            >
              {state === "done" ? <Check size={12} /> : i + 1}
            </span>
            <span className={cx("text-sm", state === "now" ? "text-text font-medium" : "text-muted")}>{s}</span>
            {state === "now" && <span className="ml-auto text-xs text-accent truncate max-w-[50%]">{tel?.task}</span>}
          </li>
        );
      })}
    </ol>
  );
}
