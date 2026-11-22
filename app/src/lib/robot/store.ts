"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { WebSocketLink, type RobotLink, type SimControls } from "./link";
import { Simulator } from "./sim";
import {
  DEFAULT_CONFIG,
  type ClientMessage,
  type Detection,
  type MissionConfig,
  type Mode,
  type RobotEvent,
  type RobotMessage,
  type Stats,
  type Telemetry,
  type Vec2,
  type World,
} from "./types";

export type ConnStatus = "idle" | "connecting" | "open" | "closed" | "error";
export type MapTool = "none" | "zone" | "drop" | "user" | "person";

export type Settings = {
  robotName: string;
  wsUrl: string;
  cameraUrl: string;
  voice: boolean;
  cameraTrigger: boolean;
  minConfidence: number;
  maxSpeed: number;
};

type State = {
  link: RobotLink | null;
  connKind: "sim" | "ws" | null;
  status: ConnStatus;
  statusDetail: string;
  telemetry: Telemetry | null;
  world: World | null;
  detections: Detection[];
  events: RobotEvent[];
  stats: Stats;
  trail: Vec2[];
  config: MissionConfig;
  settings: Settings;
  mapTool: MapTool;

  connectSim: () => void;
  connectWs: (url?: string) => void;
  disconnect: () => void;
  send: (msg: ClientMessage) => void;
  startMode: (mode: Mode) => void;
  stop: () => void;
  setEstop: (on: boolean) => void;
  setConfig: (fn: (c: MissionConfig) => MissionConfig) => void;
  setSettings: (p: Partial<Settings>) => void;
  setMapTool: (t: MapTool) => void;
  sim: () => SimControls | null;
  log: (level: RobotEvent["level"], text: string) => void;
};

function speak(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "es-ES";
  const v = window.speechSynthesis.getVoices().find((x) => x.lang.toLowerCase().startsWith("es"));
  if (v) u.voice = v;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export const useRobot = create<State>()(
  persist(
    (set, get) => {
      const handlers = {
        onMessage: (msg: RobotMessage) => {
          switch (msg.type) {
            case "telemetry": {
              const p = msg.telemetry.pose;
              const trail = get().trail;
              const last = trail[trail.length - 1];
              const next = !last || Math.hypot(last.x - p.x, last.y - p.y) > 0.03 ? [...trail.slice(-220), { x: p.x, y: p.y }] : trail;
              set({ telemetry: msg.telemetry, trail: next });
              break;
            }
            case "world":
              set({ world: msg.world });
              break;
            case "detections":
              set({ detections: msg.detections });
              break;
            case "stats":
              set({ stats: msg.stats });
              break;
            case "event":
              set({ events: [msg.event, ...get().events].slice(0, 200) });
              if (msg.event.speak && get().settings.voice) speak(msg.event.speak);
              break;
          }
        },
        onStatus: (status: "connecting" | "open" | "closed" | "error", detail?: string) => {
          set({ status, statusDetail: detail ?? "" });
          if (status === "error" || status === "closed") {
            if (get().connKind === "ws") get().log(status === "error" ? "error" : "warn", detail ?? "Conexión cerrada");
          }
        },
      };

      return {
        link: null,
        connKind: null,
        status: "idle",
        statusDetail: "",
        telemetry: null,
        world: null,
        detections: [],
        events: [],
        stats: { collected: 0, delivered: 0, received: 0, greeted: 0 },
        trail: [],
        config: DEFAULT_CONFIG,
        settings: {
          robotName: "Nexa",
          wsUrl: "ws://localhost:8765",
          cameraUrl: "",
          voice: true,
          cameraTrigger: true,
          minConfidence: 0.6,
          maxSpeed: 0.35,
        },
        mapTool: "none",

        connectSim: () => {
          get().link?.close();
          set({ connKind: "sim", trail: [], telemetry: null, world: null, events: [] });
          const link = new Simulator(handlers);
          set({ link });
          link.send({ type: "config", config: get().config });
        },
        connectWs: (url) => {
          get().link?.close();
          const u = url ?? get().settings.wsUrl;
          set({ connKind: "ws", trail: [], telemetry: null, world: null, settings: { ...get().settings, wsUrl: u } });
          try {
            set({ link: new WebSocketLink(u, handlers) });
          } catch {
            set({ status: "error", statusDetail: "Dirección no válida" });
          }
        },
        disconnect: () => {
          get().link?.close();
          set({ link: null, connKind: null, status: "idle", telemetry: null, world: null });
        },
        send: (msg) => get().link?.send(msg),
        startMode: (mode) => {
          get().send({ type: "set_mode", mode, config: get().config });
          if (get().connKind === "ws") get().log("info", `Modo enviado al robot: ${mode}`);
        },
        stop: () => get().send({ type: "stop" }),
        setEstop: (on) => get().send({ type: "estop", engaged: on }),
        setConfig: (fn) => {
          const config = fn(get().config);
          set({ config });
          get().send({ type: "config", config });
        },
        setSettings: (p) => set({ settings: { ...get().settings, ...p } }),
        setMapTool: (mapTool) => set({ mapTool }),
        sim: () => {
          const l = get().link;
          return l && l.kind === "sim" ? (l as unknown as SimControls) : null;
        },
        log: (level, text) => set({ events: [{ t: Date.now(), level, text }, ...get().events].slice(0, 200) }),
      };
    },
    {
      name: "nexa-console",
      partialize: (s) => ({ config: s.config, settings: s.settings }),
    },
  ),
);
