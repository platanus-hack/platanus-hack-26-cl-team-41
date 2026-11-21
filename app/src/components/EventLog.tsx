"use client";

import { ScrollText } from "lucide-react";
import { useRobot } from "@/lib/robot/store";
import { Card, cx } from "./ui";

const DOT = { info: "bg-accent", ok: "bg-ok", warn: "bg-warn", error: "bg-danger" };

export function EventLog({ className, max = 60 }: { className?: string; max?: number }) {
  const events = useRobot((s) => s.events);
  return (
    <Card title="Registro" icon={<ScrollText size={16} />} className={className} bodyClassName="flex-1 min-h-0">
      <ol className="space-y-1.5 overflow-y-auto max-h-[280px] pr-1">
        {events.length === 0 && <li className="text-sm text-muted">Sin eventos todavía.</li>}
        {events.slice(0, max).map((e, i) => (
          <li key={`${e.t}-${i}`} className="flex items-start gap-2.5 text-sm">
            <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", DOT[e.level])} />
            <span className="num text-xs text-muted mt-0.5 shrink-0">{new Date(e.t).toLocaleTimeString("es-CL", { hour12: false })}</span>
            <span className="text-text/90">{e.text}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
