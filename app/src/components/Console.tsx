"use client";

import { useEffect, useState } from "react";
import { useRobot } from "@/lib/robot/store";
import { MobileNav, NAV, Sidebar, TopBar, type View } from "./Shell";
import { AjustesView } from "./views/AjustesView";
import { AsistenteView } from "./views/AsistenteView";
import { ManualView } from "./views/ManualView";
import { OrdenarView } from "./views/OrdenarView";
import { PanelView } from "./views/PanelView";
import { SaludoView } from "./views/SaludoView";

const isView = (v: string): v is View => NAV.some((n) => n.id === v);

export default function Console() {
  const [view, setView] = useState<View>(() => {
    const h = typeof window !== "undefined" ? window.location.hash.slice(1) : "";
    return isView(h) ? h : "panel";
  });
  const connKind = useRobot((s) => s.connKind);
  const connectSim = useRobot((s) => s.connectSim);
  const setMapTool = useRobot((s) => s.setMapTool);

  // start the simulator on first load so the console is alive right away
  useEffect(() => {
    if (!useRobot.getState().connKind) connectSim();
  }, [connectSim]);

  useEffect(() => {
    const onHash = () => {
      const h = window.location.hash.slice(1);
      if (isView(h)) setView(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // space bar = emergency stop toggle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.code !== "Space" || tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;
      e.preventDefault();
      const s = useRobot.getState();
      if (s.status === "open") s.setEstop(!s.telemetry?.estop);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (v: View) => {
    setView(v);
    setMapTool("none");
    if (window.location.hash.slice(1) !== v) history.replaceState(null, "", `#${v}`);
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar view={view} onView={go} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onView={go} />
        <MobileNav view={view} onView={go} />
        <main className="flex-1 p-4 lg:p-6" data-conn={connKind ?? "none"}>
          {view === "panel" && <PanelView onView={go} />}
          {view === "ordenar" && <OrdenarView />}
          {view === "asistente" && <AsistenteView />}
          {view === "saludo" && <SaludoView />}
          {view === "manual" && <ManualView />}
          {view === "ajustes" && <AjustesView />}
        </main>
      </div>
    </div>
  );
}
