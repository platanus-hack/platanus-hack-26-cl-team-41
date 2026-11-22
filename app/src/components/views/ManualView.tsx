"use client";

import { Gamepad2, Grip, Keyboard, Move3d, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useRobot } from "@/lib/robot/store";
import { JOINT_INFO, POSE_PRESETS, type Joints, type PosePreset } from "@/lib/robot/types";
import { ArmView } from "../ArmView";
import { Button, Card, Slider } from "../ui";
import { WorldMap } from "../WorldMap";

const PRESET_LABEL: Record<PosePreset, string> = {
  home: "Recto",
  recoger: "Recoger del piso",
  transportar: "Transportar",
  entregar: "Entregar",
  saludar: "Saludar",
  plegado: "Plegado",
};

export function ManualView() {
  const send = useRobot((s) => s.send);
  const tel = useRobot((s) => s.telemetry);
  const maxSpeed = useRobot((s) => s.settings.maxSpeed);
  const setSettings = useRobot((s) => s.setSettings);
  const online = useRobot((s) => s.status === "open");
  const [joints, setJoints] = useState<Joints>(() => tel?.joints ?? [0, 0, 0, 0, 0]);
  const [grip, setGrip] = useState(tel?.gripper ?? 0.4);
  const latest = useRef<Joints>(joints);
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);

  // send at most every 60 ms, always ending with the latest slider values
  const sendJoints = (j: Joints) => {
    setJoints(j);
    latest.current = j;
    if (pending.current) return;
    pending.current = setTimeout(() => {
      pending.current = null;
      send({ type: "joints", joints: latest.current });
    }, 60);
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_1.2fr] gap-4">
      <div className="space-y-4 min-w-0">
        <Card title="Conducción" icon={<Gamepad2 size={16} />}>
          <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-5 items-center">
            <Joystick maxSpeed={maxSpeed} disabled={!online} />
            <div className="space-y-3">
              <Slider label="Velocidad máxima" value={maxSpeed} min={0.1} max={0.35} step={0.01} unit=" m/s" onChange={(v) => setSettings({ maxSpeed: v })} />
              <div className="flex items-start gap-2 text-xs text-muted">
                <Keyboard size={14} className="mt-0.5 shrink-0" /> También con W A S D o las flechas. Al soltar, el robot frena solo.
              </div>
              <div className="num text-sm text-muted">
                v = {(tel?.speed.v ?? 0).toFixed(2)} m/s · ω = {(tel?.speed.w ?? 0).toFixed(2)} rad/s
              </div>
            </div>
          </div>
        </Card>
        <Card title="Posición" icon={<Move3d size={16} />}>
          <WorldMap show={{ zone: false }} className="aspect-[4/3]" />
        </Card>
      </div>

      <div className="space-y-4 min-w-0">
        <Card title="Brazo" icon={<Move3d size={16} />}>
          <ArmView />
        </Card>
        <Card title="Articulaciones" icon={<Sparkles size={16} />}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
            {JOINT_INFO.map((ji, i) => (
              <Slider
                key={ji.name}
                label={
                  <span>
                    {ji.name} <span className="text-muted text-xs">· {ji.servo}</span>
                  </span>
                }
                value={joints[i]}
                min={ji.min}
                max={ji.max}
                unit="°"
                onChange={(v) => {
                  const j = [...joints] as Joints;
                  j[i] = v;
                  sendJoints(j);
                }}
              />
            ))}
            <Slider
              label={
                <span className="inline-flex items-center gap-1.5">
                  <Grip size={14} /> Pinza <span className="text-muted text-xs">· SG90</span>
                </span>
              }
              value={grip}
              min={0}
              max={1}
              step={0.01}
              onChange={(v) => {
                setGrip(v);
                send({ type: "gripper", open: v });
              }}
            />
          </div>
          <div className="mt-4 label">Posturas</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(Object.keys(POSE_PRESETS) as PosePreset[]).map((p) => (
              <Button
                key={p}
                size="sm"
                disabled={!online}
                onClick={() => {
                  setJoints([...POSE_PRESETS[p]] as Joints);
                  send({ type: "pose_preset", name: p });
                }}
              >
                {PRESET_LABEL[p]}
              </Button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Joystick({ maxSpeed, disabled }: { maxSpeed: number; disabled: boolean }) {
  const send = useRobot((s) => s.send);
  const ref = useRef<HTMLDivElement>(null);
  const [knob, setKnob] = useState({ x: 0, y: 0 });
  const vec = useRef({ x: 0, y: 0 });
  const keys = useRef(new Set<string>());

  useEffect(() => {
    if (disabled) return;
    const timer = setInterval(() => {
      let { x, y } = vec.current;
      const k = keys.current;
      if (k.size) {
        y = (k.has("w") || k.has("arrowup") ? 1 : 0) - (k.has("s") || k.has("arrowdown") ? 1 : 0);
        x = (k.has("d") || k.has("arrowright") ? 1 : 0) - (k.has("a") || k.has("arrowleft") ? 1 : 0);
      }
      if (x !== 0 || y !== 0) send({ type: "drive", v: y * maxSpeed, w: -x * 1.8 });
    }, 100);
    const down = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"].includes(k)) {
        if ((e.target as HTMLElement)?.tagName === "INPUT") return;
        keys.current.add(k);
        e.preventDefault();
      }
    };
    const up = (e: KeyboardEvent) => keys.current.delete(e.key.toLowerCase());
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      clearInterval(timer);
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [disabled, maxSpeed, send]);

  const R = 70;
  const move = (e: PointerEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    let dx = e.clientX - (r.left + r.width / 2);
    let dy = e.clientY - (r.top + r.height / 2);
    const d = Math.hypot(dx, dy);
    if (d > R) {
      dx = (dx / d) * R;
      dy = (dy / d) * R;
    }
    setKnob({ x: dx, y: dy });
    vec.current = { x: dx / R, y: -dy / R };
  };
  const release = () => {
    setKnob({ x: 0, y: 0 });
    vec.current = { x: 0, y: 0 };
    send({ type: "drive", v: 0, w: 0 });
  };

  return (
    <div
      ref={ref}
      className="relative mx-auto h-[180px] w-[180px] rounded-full border border-line bg-black/30 touch-none grid-bg"
      onPointerDown={(e) => {
        if (disabled) return;
        (e.target as Element).setPointerCapture(e.pointerId);
        move(e);
      }}
      onPointerMove={(e) => e.buttons && !disabled && move(e)}
      onPointerUp={release}
      onPointerCancel={release}
    >
      <div className="absolute inset-6 rounded-full border border-line/60" />
      <div
        className="absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-accent to-accent-2 shadow-[0_0_30px_-6px_var(--accent)]"
        style={{ transform: `translate(calc(-50% + ${knob.x}px), calc(-50% + ${knob.y}px))` }}
      />
    </div>
  );
}
