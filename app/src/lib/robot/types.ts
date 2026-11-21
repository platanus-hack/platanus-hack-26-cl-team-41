// Shared types and the WebSocket protocol between the console and the robot.
// Units: metres and radians in the world, degrees for joints, gripper 0 (closed) .. 1 (open).

export type Mode = "idle" | "manual" | "ordenar" | "asistente" | "saludo";

export type Vec2 = { x: number; y: number };

export type Pose = Vec2 & { th: number };

/** Joint order: base yaw, shoulder, elbow, wrist pitch, wrist roll (degrees). */
export type Joints = [number, number, number, number, number];

export type Zone = { x0: number; y0: number; x1: number; y1: number };

export type WorldObject = {
  id: string;
  cls: string;
  pos: Vec2;
  state: "free" | "carried" | "stored";
};

export type Person = {
  id: string;
  name: string;
  pos: Vec2;
  heading: number;
  lastGreeted?: number;
  isUser?: boolean;
};

export type World = {
  size: { w: number; h: number };
  objects: WorldObject[];
  people: Person[];
  toolStation: Vec2;
  materialBin: Vec2;
};

export type Telemetry = {
  t: number;
  mode: Mode;
  phase: string;
  task: string;
  pose: Pose;
  speed: { v: number; w: number };
  joints: Joints;
  gripper: number;
  battery: number;
  carrying: string | null;
  estop: boolean;
  /** Base tilt from the flight controller's IMU (degrees). */
  attitude?: { roll: number; pitch: number } | null;
  /** Battery voltage reported by the flight controller. */
  voltage?: number | null;
  /** Health of the robot's links: flight controller (MAVLink) and PC vision. */
  links?: { fc: boolean; vision: boolean };
};

export type Detection = {
  id: string;
  cls: string;
  confidence: number;
  /** Position in the world when the robot localises it (metres). */
  pos?: Vec2;
  /** Bounding box in the camera image, normalised 0..1. */
  bbox?: [number, number, number, number];
};

export type MissionConfig = {
  ordenar: { zone: Zone; drop: Vec2; classes: string[] };
  asistente: { followDistance: number };
  saludo: { greeting: string; cooldownS: number; range: number };
};

export type AssistantRequest = { action: "entregar" | "recibir"; item: string };

export type EventLevel = "info" | "ok" | "warn" | "error";

export type RobotEvent = { t: number; level: EventLevel; text: string; /** sentence the console reads aloud */ speak?: string };

export type Stats = { collected: number; delivered: number; received: number; greeted: number };

/* ---------------- protocol ---------------- */

export type ClientMessage =
  | { type: "hello"; client: string; version: number }
  | { type: "set_mode"; mode: Mode; config: MissionConfig }
  | { type: "stop" }
  | { type: "estop"; engaged: boolean }
  | { type: "drive"; v: number; w: number }
  | { type: "joints"; joints: Joints }
  | { type: "gripper"; open: number }
  | { type: "pose_preset"; name: PosePreset }
  | { type: "assistant_request"; request: AssistantRequest }
  | { type: "assistant_confirm" }
  | { type: "person_seen"; source: "browser_camera"; confidence: number }
  | { type: "config"; config: MissionConfig };

export type RobotMessage =
  | { type: "telemetry"; telemetry: Telemetry }
  | { type: "world"; world: World }
  | { type: "detections"; detections: Detection[] }
  | { type: "event"; event: RobotEvent }
  | { type: "stats"; stats: Stats };

export type PosePreset = "home" | "recoger" | "transportar" | "entregar" | "saludar" | "plegado";

export const POSE_PRESETS: Record<PosePreset, Joints> = {
  home: [0, 0, 0, 0, 0],
  recoger: [0, 62, 78, 40, 0],
  transportar: [0, -10, 110, 60, 0],
  entregar: [0, 48, 30, 12, 0],
  saludar: [0, 10, 60, -20, 0],
  plegado: [0, -20, 120, 75, 0],
};

export const JOINT_INFO: { name: string; servo: string; min: number; max: number }[] = [
  { name: "Base", servo: "MG995", min: -90, max: 90 },
  { name: "Hombro", servo: "MG995", min: -90, max: 90 },
  { name: "Codo", servo: "MG995", min: -90, max: 120 },
  { name: "Muñeca", servo: "MG995", min: -90, max: 90 },
  { name: "Giro muñeca", servo: "SG90", min: -90, max: 90 },
];

export const MODE_LABEL: Record<Mode, string> = {
  idle: "En espera",
  manual: "Control manual",
  ordenar: "Ordenar zona",
  asistente: "Asistente",
  saludo: "Saludo",
};

/** Arm geometry from the CAD (mm), used for the side view. */
export const ARM = { shoulderZ: 159.5, l1: 90, l2: 85, tool: 144 };

export const DEFAULT_CONFIG: MissionConfig = {
  ordenar: {
    zone: { x0: 0.5, y0: 0.4, x1: 2.6, y1: 2.0 },
    drop: { x: 3.4, y: 2.5 },
    classes: ["botella", "taza", "lata", "juguete"],
  },
  asistente: { followDistance: 0.7 },
  saludo: { greeting: "¡Hola! Soy Nexa, encantado de conocerte.", cooldownS: 30, range: 1.6 },
};

export const OBJECT_CLASSES = ["botella", "taza", "lata", "juguete", "tornillo", "libro"];

export const TOOLS = ["Destornillador", "Alicate", "Llave inglesa", "Martillo", "Cinta aislante", "Multímetro"];
