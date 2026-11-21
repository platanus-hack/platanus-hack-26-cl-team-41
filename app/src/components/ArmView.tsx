"use client";

import { useRobot } from "@/lib/robot/store";
import { ARM, JOINT_INFO } from "@/lib/robot/types";

const rad = (d: number) => (d * Math.PI) / 180;

/** Side view of the arm (mm) computed from the joint angles, plus a top dial for the base yaw. */
export function ArmView() {
  const tel = useRobot((s) => s.telemetry);
  const j = tel?.joints ?? [0, 0, 0, 0, 0];
  const grip = tel?.gripper ?? 0.4;

  const S = { x: 0, z: ARM.shoulderZ };
  const a1 = rad(j[1]);
  const a2 = a1 + rad(j[2]);
  const a3 = a2 + rad(j[3]);
  const E = { x: S.x + ARM.l1 * Math.sin(a1), z: S.z + ARM.l1 * Math.cos(a1) };
  const Wr = { x: E.x + ARM.l2 * Math.sin(a2), z: E.z + ARM.l2 * Math.cos(a2) };
  const palm = { x: Wr.x + 70 * Math.sin(a3), z: Wr.z + 70 * Math.cos(a3) };
  const T = { x: Wr.x + ARM.tool * Math.sin(a3), z: Wr.z + ARM.tool * Math.cos(a3) };
  const nx = Math.cos(a3);
  const nz = -Math.sin(a3);
  const spread = 6 + grip * 22;

  // viewBox in mm, z up -> flip
  const vb = { x: -230, y: -480, w: 460, h: 500 };
  const P = (p: { x: number; z: number }) => `${p.x},${-p.z}`;

  return (
    <div className="grid grid-cols-[1fr_auto] gap-3 items-stretch">
      <svg viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} className="w-full h-[260px]" role="img" aria-label="Vista lateral del brazo">
        <defs>
          <linearGradient id="link" x1="0" x2="1">
            <stop offset="0" stopColor="#e5e7eb" />
            <stop offset="1" stopColor="#9ca3af" />
          </linearGradient>
        </defs>
        <line x1={-230} y1={0} x2={230} y2={0} stroke="rgba(148,163,184,0.35)" strokeWidth={1.5} />
        {/* base: wheels, plate, cone, turntable, tower */}
        <circle cx={0} cy={-32.5} r={32.5} fill="#111827" stroke="#334155" strokeWidth={2} />
        <rect x={-89} y={-47.5} width={178} height={3} fill="#cbd5e1" />
        <path d="M -80 -47.5 L -80 -51.5 L -52 -102.5 L 52 -102.5 L 80 -51.5 L 80 -47.5 Z" fill="#cbd5e1" opacity={0.9} />
        <rect x={-52} y={-118.5} width={104} height={15} rx={4} fill="#94a3b8" />
        <rect x={-24} y={-S.z - 4} width={48} height={S.z - 118.5 + 4} rx={6} fill="#cbd5e1" />
        {/* links */}
        <line x1={S.x} y1={-S.z} x2={E.x} y2={-E.z} stroke="url(#link)" strokeWidth={44} strokeLinecap="round" opacity={0.95} />
        <line x1={E.x} y1={-E.z} x2={Wr.x} y2={-Wr.z} stroke="#e5e7eb" strokeWidth={40} strokeLinecap="round" />
        <line x1={Wr.x} y1={-Wr.z} x2={palm.x} y2={-palm.z} stroke="#cbd5e1" strokeWidth={26} strokeLinecap="round" />
        {/* fingers */}
        {[1, -1].map((s) => (
          <line
            key={s}
            x1={palm.x + s * nx * spread * 0.6}
            y1={-(palm.z + s * nz * spread * 0.6)}
            x2={T.x + s * nx * spread}
            y2={-(T.z + s * nz * spread)}
            stroke="#ef4444"
            strokeWidth={8}
            strokeLinecap="round"
          />
        ))}
        {[S, E, Wr].map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={-p.z} r={11} fill="#0b1018" stroke="#22d3ee" strokeWidth={3} />
          </g>
        ))}
        <polyline points={[S, E, Wr, T].map(P).join(" ")} fill="none" stroke="rgba(34,211,238,0.45)" strokeWidth={1.5} strokeDasharray="5 5" />
        <text x={-220} y={-455} fontSize={16} fill="#64748b">
          Vista lateral · alcance {Math.round(Math.hypot(T.x, T.z - 47.5))} mm
        </text>
      </svg>
      <div className="flex flex-col justify-between gap-2 min-w-[150px]">
        <div className="flex items-center justify-center gap-2">
          <BaseDial yaw={j[0]} />
          <TiltIndicator roll={tel?.attitude?.roll ?? 0} pitch={tel?.attitude?.pitch ?? 0} live={Boolean(tel?.attitude)} />
        </div>
        <div className="space-y-1">
          {JOINT_INFO.map((ji, i) => (
            <div key={ji.name} className="flex items-center justify-between text-xs">
              <span className="text-muted">{ji.name}</span>
              <span className="num text-text">{j[i].toFixed(0)}°</span>
            </div>
          ))}
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted">Pinza</span>
            <span className="num text-text">{Math.round(grip * 100)} %</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Artificial horizon of the base from the IMU (roll rotates it, pitch shifts it). */
function TiltIndicator({ roll, pitch, live }: { roll: number; pitch: number; live: boolean }) {
  const shift = Math.max(-30, Math.min(30, pitch * 3));
  return (
    <svg viewBox="-50 -50 100 100" className="w-24 h-24" role="img" aria-label={`Inclinación: roll ${roll.toFixed(1)}°, pitch ${pitch.toFixed(1)}°`}>
      <defs>
        <clipPath id="tiltClip">
          <circle r={44} />
        </clipPath>
      </defs>
      <g clipPath="url(#tiltClip)">
        <rect x={-60} y={-60} width={120} height={120} fill="rgba(34,211,238,0.08)" />
        <g transform={`rotate(${-roll}) translate(0 ${shift})`}>
          <rect x={-80} y={0} width={160} height={80} fill="rgba(167,139,250,0.22)" />
          <line x1={-80} y1={0} x2={80} y2={0} stroke="#a78bfa" strokeWidth={2} />
        </g>
      </g>
      <circle r={44} fill="none" stroke="rgba(148,163,184,0.25)" />
      <line x1={-18} y1={0} x2={-6} y2={0} stroke="#22d3ee" strokeWidth={3} strokeLinecap="round" />
      <line x1={6} y1={0} x2={18} y2={0} stroke="#22d3ee" strokeWidth={3} strokeLinecap="round" />
      <text y={30} fontSize={10} fill="#8b98ab" textAnchor="middle">
        {live ? `${roll.toFixed(1)}° / ${pitch.toFixed(1)}°` : "sin IMU"}
      </text>
    </svg>
  );
}

function BaseDial({ yaw }: { yaw: number }) {
  const a = rad(yaw);
  return (
    <svg viewBox="-50 -50 100 100" className="w-24 h-24 self-center" role="img" aria-label="Giro de la base">
      <circle r={44} fill="rgba(255,255,255,0.02)" stroke="rgba(148,163,184,0.25)" />
      <path d="M -44 0 A 44 44 0 0 1 44 0" fill="none" stroke="rgba(34,211,238,0.25)" strokeWidth={4} />
      <line x1={0} y1={0} x2={38 * Math.sin(a)} y2={-38 * Math.cos(a)} stroke="#22d3ee" strokeWidth={5} strokeLinecap="round" />
      <circle r={6} fill="#22d3ee" />
      <text y={30} fontSize={11} fill="#8b98ab" textAnchor="middle">
        base
      </text>
    </svg>
  );
}
