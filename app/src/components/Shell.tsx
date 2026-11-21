"use client";

import { BatteryFull, BatteryLow, BatteryMedium, Bot, Hand, Handshake, LayoutDashboard, LifeBuoy, OctagonX, Package, Plug, Settings, Gamepad2, Wifi, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { useRobot } from "@/lib/robot/store";
import { MODE_LABEL } from "@/lib/robot/types";
import { Badge, Button, cx } from "./ui";

export type View = "panel" | "ordenar" | "asistente" | "saludo" | "manual" | "ajustes";

export const NAV: { id: View; label: string; icon: ReactNode; hint: string }[] = [
  { id: "panel", label: "Panel", icon: <LayoutDashboard size={18} />, hint: "Estado general" },
  { id: "ordenar", label: "Ordenar zona", icon: <Package size={18} />, hint: "Recoger y llevar objetos" },
  { id: "asistente", label: "Asistente", icon: <Handshake size={18} />, hint: "Entrega y recibe cosas" },
  { id: "saludo", label: "Saludo", icon: <Hand size={18} />, hint: "Demo: saluda a la gente" },
  { id: "manual", label: "Control manual", icon: <Gamepad2 size={18} />, hint: "Ruedas y articulaciones" },
  { id: "ajustes", label: "Ajustes", icon: <Settings size={18} />, hint: "Conexión, visión y voz" },
];

export function Sidebar({ view, onView }: { view: View; onView: (v: View) => void }) {
  const name = useRobot((s) => s.settings.robotName);
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col gap-6 border-r border-line bg-black/20 px-4 py-5">
      <div className="flex items-center gap-3 px-2">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-accent to-accent-2 text-[#04141a] shadow-[0_0_30px_-8px_var(--accent)]">
          <Bot size={22} />
        </div>
        <div>
          <div className="font-semibold tracking-tight">{name}</div>
          <div className="text-xs text-muted">Consola del robot</div>
        </div>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => onView(n.id)}
            className={cx(
              "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition",
              view === n.id ? "bg-white/[0.07] text-text shadow-[inset_0_0_0_1px_var(--line-strong)]" : "text-muted hover:bg-white/[0.04] hover:text-text",
            )}
          >
            <span className={cx(view === n.id ? "text-accent" : "text-muted group-hover:text-text")}>{n.icon}</span>
            <span className="min-w-0">
              <span className="block text-sm font-medium">{n.label}</span>
              <span className="block text-[11px] text-muted truncate">{n.hint}</span>
            </span>
          </button>
        ))}
      </nav>
      <div className="mt-auto panel p-3 text-xs text-muted">
        <div className="flex items-center gap-2 text-text/90 font-medium">
          <LifeBuoy size={14} className="text-accent" /> Seguridad
        </div>
        <p className="mt-1.5 leading-relaxed">
          Barra espaciadora o el botón rojo: parada de emergencia. El robot se detiene y mantiene la postura.
        </p>
      </div>
    </aside>
  );
}

export function MobileNav({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <nav className="lg:hidden flex gap-1 overflow-x-auto border-b border-line px-3 py-2">
      {NAV.map((n) => (
        <button
          key={n.id}
          onClick={() => onView(n.id)}
          className={cx("flex shrink-0 items-center gap-1.5 rounded-lg px-3 h-9 text-sm", view === n.id ? "bg-white/10 text-text" : "text-muted")}
        >
          {n.icon}
          {n.label}
        </button>
      ))}
    </nav>
  );
}

export function TopBar({ onView }: { onView: (v: View) => void }) {
  const tel = useRobot((s) => s.telemetry);
  const status = useRobot((s) => s.status);
  const kind = useRobot((s) => s.connKind);
  const setEstop = useRobot((s) => s.setEstop);
  const connectSim = useRobot((s) => s.connectSim);

  const online = status === "open";
  const bat = tel?.battery ?? 0;
  const BatIcon = bat > 60 ? BatteryFull : bat > 25 ? BatteryMedium : BatteryLow;
  const estop = tel?.estop ?? false;

  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-line px-4 lg:px-6 py-3 bg-black/10 backdrop-blur">
      <div className="flex items-center gap-2">
        {online ? (
          <Badge tone={kind === "sim" ? "accent" : "ok"}>
            <Wifi size={12} /> {kind === "sim" ? "Simulador" : "Robot conectado"}
          </Badge>
        ) : (
          <Badge tone={status === "connecting" ? "warn" : "danger"}>
            <WifiOff size={12} /> {status === "connecting" ? "Conectando…" : "Sin conexión"}
          </Badge>
        )}
        {!online && status !== "connecting" && (
          <Button size="sm" variant="ghost" onClick={() => (kind === "ws" ? onView("ajustes") : connectSim())}>
            <Plug size={14} /> {kind === "ws" ? "Revisar conexión" : "Iniciar simulador"}
          </Button>
        )}
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="h-8 w-px bg-line hidden sm:block" />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{tel ? MODE_LABEL[tel.mode] : "—"}</span>
            {tel && (
              <Badge tone={estop ? "danger" : tel.mode === "idle" ? "muted" : "accent"}>
                {tel.mode !== "idle" && !estop && <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />}
                {tel.phase}
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted truncate">{tel?.task ?? "Conéctate a un robot o inicia el simulador"}</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-2 text-sm">
          <BatIcon size={18} className={bat > 25 ? "text-ok" : "text-danger"} />
          <span className="num">{tel ? `${bat.toFixed(0)} %` : "—"}</span>
        </div>
        <div className="hidden md:block num text-sm text-muted">{tel ? `${Math.abs(tel.speed.v).toFixed(2)} m/s` : ""}</div>
        <Button variant={estop ? "ok" : "danger"} onClick={() => setEstop(!estop)} disabled={!online} className="font-semibold">
          <OctagonX size={16} /> {estop ? "Liberar" : "PARADA"}
        </Button>
      </div>
    </header>
  );
}
