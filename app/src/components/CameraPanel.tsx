"use client";

import { Camera, CameraOff, Loader2, ScanEye } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useRobot } from "@/lib/robot/store";
import { detect, type BrowserDetection } from "@/lib/vision";
import { Badge, Button, Card, cx } from "./ui";

type Source = "browser" | "robot";

/** Camera with object/person detection. Browser: webcam + COCO-SSD. Robot: MJPEG stream + the robot's own detections. */
export function CameraPanel({ title = "Visión", compact = false }: { title?: string; compact?: boolean }) {
  const [source, setSource] = useState<Source>("browser");
  return (
    <Card
      title={title}
      icon={<ScanEye size={16} />}
      actions={
        <div className="flex rounded-lg border border-line p-0.5 text-xs">
          {(["browser", "robot"] as Source[]).map((s) => (
            <button
              key={s}
              onClick={() => setSource(s)}
              className={cx("px-2.5 h-7 rounded-md transition whitespace-nowrap", source === s ? "bg-white/10 text-text" : "text-muted hover:text-text")}
            >
              {s === "browser" ? "Cámara local" : "Cámara del robot"}
            </button>
          ))}
        </div>
      }
    >
      {source === "browser" ? <BrowserCamera compact={compact} /> : <RobotCamera compact={compact} />}
    </Card>
  );
}

function BrowserCamera({ compact }: { compact: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [state, setState] = useState<"off" | "loading" | "on" | "error">("off");
  const [error, setError] = useState("");
  const [dets, setDets] = useState<BrowserDetection[]>([]);
  const [size, setSize] = useState({ w: 640, h: 480 });
  const minConfidence = useRobot((s) => s.settings.minConfidence);
  const cameraTrigger = useRobot((s) => s.settings.cameraTrigger);
  const mode = useRobot((s) => s.telemetry?.mode);
  const send = useRobot((s) => s.send);
  const log = useRobot((s) => s.log);
  const lastPersonSent = useRef(0);

  const stop = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setState("off");
    setDets([]);
  };

  const start = async () => {
    setState("loading");
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: 640, height: 480 }, audio: false });
      streamRef.current = stream;
      const v = videoRef.current;
      if (!v) return;
      v.srcObject = stream;
      await v.play();
      setSize({ w: v.videoWidth || 640, h: v.videoHeight || 480 });
      setState("on");
    } catch (e) {
      setState("error");
      setError(e instanceof Error ? e.message : "No se pudo abrir la cámara");
    }
  };

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  useEffect(() => {
    if (state !== "on") return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const loop = async () => {
      const v = videoRef.current;
      if (!alive || !v) return;
      try {
        const d = await detect(v, minConfidence);
        if (!alive) return;
        setDets(d);
        const person = d.find((x) => x.cls === "person");
        if (person && cameraTrigger && mode === "saludo" && Date.now() - lastPersonSent.current > 5000) {
          lastPersonSent.current = Date.now();
          send({ type: "person_seen", source: "browser_camera", confidence: person.score });
        }
      } catch {
        log("error", "Falló la detección en el navegador.");
      }
      timer = setTimeout(loop, 250);
    };
    loop();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [state, minConfidence, cameraTrigger, mode, send, log]);

  return (
    <div>
      <div className={cx("relative w-full overflow-hidden rounded-xl border border-line bg-black grid-bg", compact ? "aspect-video" : "aspect-[4/3]")}>
        <video ref={videoRef} muted playsInline className={cx("absolute inset-0 h-full w-full object-cover", state !== "on" && "opacity-0")} />
        {state === "on" && (
          <svg viewBox={`0 0 ${size.w} ${size.h}`} preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
            {dets.map((d, i) => {
              const [x, y, w, h] = d.bbox;
              const c = d.cls === "person" ? "#f472b6" : "#22d3ee";
              return (
                <g key={i}>
                  <rect x={x} y={y} width={w} height={h} fill="none" stroke={c} strokeWidth={3} rx={6} />
                  <rect x={x} y={Math.max(0, y - 26)} width={Math.max(90, d.label.length * 11 + 50)} height={24} fill={c} rx={5} />
                  <text x={x + 8} y={Math.max(17, y - 9)} fontSize={15} fill="#04141a" fontWeight={700}>
                    {d.label} {Math.round(d.score * 100)}%
                  </text>
                </g>
              );
            })}
          </svg>
        )}
        {state !== "on" && (
          <div className="absolute inset-0 grid place-items-center p-4 text-center">
            {state === "loading" ? (
              <div className="flex items-center gap-2 text-sm text-muted">
                <Loader2 className="animate-spin" size={16} /> Abriendo cámara y cargando el modelo…
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-muted max-w-xs">
                  {state === "error" ? `Error: ${error}` : "Detección de objetos y personas en este navegador (COCO-SSD)."}
                </p>
                <Button variant="primary" size="sm" onClick={start}>
                  <Camera size={14} /> Activar cámara
                </Button>
              </div>
            )}
          </div>
        )}
        {state === "on" && (
          <div className="absolute top-2 left-2 flex gap-1.5">
            <Badge tone="danger">● EN VIVO</Badge>
            <Badge tone="accent">{dets.length} detecciones</Badge>
          </div>
        )}
      </div>
      {state === "on" && (
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1.5 min-w-0">
            {summarize(dets).map(([label, n]) => (
              <Badge key={label} tone={label === "persona" ? "danger" : "accent"}>
                {label} ×{n}
              </Badge>
            ))}
            {dets.length === 0 && <span className="text-xs text-muted">Nada a la vista</span>}
          </div>
          <Button size="sm" variant="ghost" onClick={stop}>
            <CameraOff size={14} /> Apagar
          </Button>
        </div>
      )}
    </div>
  );
}

function summarize(d: BrowserDetection[]): [string, number][] {
  const m = new Map<string, number>();
  d.forEach((x) => m.set(x.label, (m.get(x.label) ?? 0) + 1));
  return [...m.entries()];
}

function RobotCamera({ compact }: { compact: boolean }) {
  const url = useRobot((s) => s.settings.cameraUrl);
  const detections = useRobot((s) => s.detections);
  const boxed = detections.filter((d) => d.bbox);
  return (
    <div>
      <div className={cx("relative w-full overflow-hidden rounded-xl border border-line bg-black grid-bg", compact ? "aspect-video" : "aspect-[4/3]")}>
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element -- MJPEG streams need a plain <img>
          <img src={url} alt="Cámara del robot" className="absolute inset-0 h-full w-full object-cover" />
        ) : (
          <div className="absolute inset-0 grid place-items-center p-4 text-center text-sm text-muted">
            Configura la URL del video del robot (MJPEG) en Ajustes. Las detecciones de tu modelo llegan por el canal del robot.
          </div>
        )}
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
          {boxed.map((d) => {
            const [x, y, w, h] = d.bbox!;
            return <rect key={d.id} x={x} y={y} width={w} height={h} fill="none" stroke="#22d3ee" strokeWidth={0.004} />;
          })}
        </svg>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {detections.length === 0 && <span className="text-xs text-muted">El robot no reporta detecciones.</span>}
        {detections.slice(0, 10).map((d) => (
          <Badge key={d.id} tone={d.cls.startsWith("persona") ? "danger" : "accent"}>
            {d.cls} · {Math.round(d.confidence * 100)}%
          </Badge>
        ))}
      </div>
    </div>
  );
}
