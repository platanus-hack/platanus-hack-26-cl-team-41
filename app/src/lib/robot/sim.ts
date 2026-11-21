// Browser simulator of the mobile arm: same protocol as the real robot, so every mode can be demoed offline.
import type { LinkHandlers, RobotLink, SimControls } from "./link";
import {
  DEFAULT_CONFIG,
  OBJECT_CLASSES,
  POSE_PRESETS,
  type AssistantRequest,
  type ClientMessage,
  type Detection,
  type EventLevel,
  type Joints,
  type MissionConfig,
  type Mode,
  type Person,
  type Pose,
  type Stats,
  type Telemetry,
  type Vec2,
  type World,
  type WorldObject,
} from "./types";

type Step = Generator<void, void, void>;

const DT = 1 / 30;
const MAX_V = 0.35; // m/s
const MAX_W = 2.2; // rad/s
const JOINT_SPEED = 120; // deg/s
const FOV = (40 * Math.PI) / 180; // half angle

const dist = (a: Vec2, b: Vec2) => Math.hypot(a.x - b.x, a.y - b.y);
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const NAMES = ["Camila", "Diego", "Valentina", "Matías", "Sofía", "Tomás", "Isidora", "Benjamín"];

export class Simulator implements RobotLink, SimControls {
  readonly kind = "sim" as const;
  private rand = rng(42);
  private timer: ReturnType<typeof setInterval> | null = null;
  private tick = 0;
  private t = 0;
  private idSeq = 0;

  private world!: World;
  private pose: Pose = { x: 0.4, y: 2.6, th: 0 };
  private cmd = { v: 0, w: 0 };
  private manualDrive = { v: 0, w: 0, until: 0 };
  private joints: Joints = [0, 0, 0, 0, 0];
  private jointTarget: Joints = [0, 0, 0, 0, 0];
  private gripper = 0.4;
  private gripperTarget = 0.4;
  private battery = 100;
  private carrying: WorldObject | null = null;
  private carryingLabel: string | null = null;

  private mode: Mode = "idle";
  private phase = "Listo";
  private task = "Esperando instrucciones";
  private estop = false;
  private config: MissionConfig = DEFAULT_CONFIG;
  private program: Step | null = null;
  private requests: AssistantRequest[] = [];
  private confirmed = false;
  private cameraPerson = 0;
  private stats: Stats = { collected: 0, delivered: 0, received: 0, greeted: 0 };

  constructor(private h: LinkHandlers) {
    this.resetWorld();
    h.onStatus("open", "Simulador");
    this.event("ok", "Simulador iniciado: robot en la base de carga.");
    this.timer = setInterval(() => this.step(), DT * 1000);
  }

  /* ---------------- RobotLink ---------------- */

  send(msg: ClientMessage) {
    switch (msg.type) {
      case "hello":
        break;
      case "set_mode":
        this.config = msg.config;
        this.setMode(msg.mode);
        break;
      case "config":
        this.config = msg.config;
        break;
      case "stop":
        this.setMode("idle");
        break;
      case "estop":
        this.estop = msg.engaged;
        if (msg.engaged) {
          this.cmd = { v: 0, w: 0 };
          this.jointTarget = [...this.joints] as Joints;
          this.event("error", "Parada de emergencia activada.");
        } else this.event("ok", "Parada de emergencia liberada.");
        break;
      case "drive":
        this.manualDrive = { v: clamp(msg.v, -MAX_V, MAX_V), w: clamp(msg.w, -MAX_W, MAX_W), until: this.t + 0.5 };
        if (this.mode !== "manual") this.setMode("manual");
        break;
      case "joints":
        this.jointTarget = [...msg.joints] as Joints;
        if (this.mode !== "manual") this.setMode("manual");
        break;
      case "gripper":
        this.gripperTarget = clamp(msg.open, 0, 1);
        break;
      case "pose_preset":
        this.jointTarget = [...POSE_PRESETS[msg.name]] as Joints;
        break;
      case "assistant_request":
        this.requests.push(msg.request);
        this.event("info", `Pedido en cola: ${msg.request.action} «${msg.request.item}».`);
        if (this.mode !== "asistente") this.setMode("asistente");
        break;
      case "assistant_confirm":
        this.confirmed = true;
        break;
      case "person_seen":
        if (this.mode === "saludo" && this.t > this.cameraPerson + 6) {
          this.cameraPerson = this.t;
          this.event("info", `La cámara vio a una persona (${Math.round(msg.confidence * 100)} %).`);
        }
        break;
    }
  }

  close() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.h.onStatus("closed");
  }

  /* ---------------- SimControls ---------------- */

  movePerson(id: string, pos: Vec2) {
    const p = this.world.people.find((q) => q.id === id);
    if (p) p.pos = this.inside(pos);
    this.emitWorld();
  }

  addPerson(pos: Vec2) {
    const name = NAMES[this.world.people.length % NAMES.length];
    this.world.people.push({ id: this.nid("p"), name, pos: this.inside(pos), heading: this.rand() * 6.28 });
    this.event("info", `${name} entró al área.`);
    this.emitWorld();
  }

  scatterObjects(n: number) {
    const z = this.config.ordenar.zone;
    for (let i = 0; i < n; i++) {
      this.world.objects.push({
        id: this.nid("o"),
        cls: OBJECT_CLASSES[Math.floor(this.rand() * OBJECT_CLASSES.length)],
        pos: { x: z.x0 + 0.15 + this.rand() * (z.x1 - z.x0 - 0.3), y: z.y0 + 0.15 + this.rand() * (z.y1 - z.y0 - 0.3) },
        state: "free",
      });
    }
    this.emitWorld();
  }

  resetWorld() {
    this.world = {
      size: { w: 4, h: 3 },
      objects: [],
      people: [
        { id: "user", name: "Tú", pos: { x: 1.2, y: 2.55 }, heading: 0, isUser: true },
        { id: this.nid("p"), name: "Camila", pos: { x: 3.2, y: 0.8 }, heading: 2 },
        { id: this.nid("p"), name: "Diego", pos: { x: 2.0, y: 1.5 }, heading: 4 },
      ],
      toolStation: { x: 0.35, y: 0.35 },
      materialBin: { x: 3.65, y: 0.35 },
    };
    this.scatterObjects(7);
    this.carrying = null;
    this.carryingLabel = null;
  }

  /* ---------------- core loop ---------------- */

  private step() {
    this.t += DT;
    this.tick++;
    if (!this.estop) {
      this.moveArm();
      if (this.mode === "manual") {
        this.cmd = this.t < this.manualDrive.until ? { v: this.manualDrive.v, w: this.manualDrive.w } : { v: 0, w: 0 };
      }
      if (this.program) {
        const r = this.program.next();
        if (r.done) this.program = null;
      }
      this.integrate();
      this.walkPeople();
    }
    this.battery = Math.max(5, this.battery - DT * (0.004 + Math.abs(this.cmd.v) * 0.05));
    if (this.carrying) {
      this.carrying.pos = { x: this.pose.x + 0.18 * Math.cos(this.pose.th), y: this.pose.y + 0.18 * Math.sin(this.pose.th) };
    }
    this.emitTelemetry();
    if (this.tick % 6 === 0) {
      this.emitWorld();
      this.emitDetections();
    }
  }

  private integrate() {
    const { v, w } = this.estop ? { v: 0, w: 0 } : this.cmd;
    this.pose.th = wrap(this.pose.th + w * DT);
    const p = this.inside({ x: this.pose.x + v * Math.cos(this.pose.th) * DT, y: this.pose.y + v * Math.sin(this.pose.th) * DT });
    this.pose.x = p.x;
    this.pose.y = p.y;
  }

  private moveArm() {
    const step = JOINT_SPEED * DT;
    this.joints = this.joints.map((j, i) => {
      const d = this.jointTarget[i] - j;
      return Math.abs(d) <= step ? this.jointTarget[i] : j + Math.sign(d) * step;
    }) as Joints;
    const gd = this.gripperTarget - this.gripper;
    this.gripper = Math.abs(gd) < 0.06 ? this.gripperTarget : this.gripper + Math.sign(gd) * 0.06;
  }

  private walkPeople() {
    for (const p of this.world.people) {
      if (p.isUser) continue;
      if (p.lastGreeted && this.t - p.lastGreeted < 4) continue; // stops while being greeted
      if (this.rand() < 0.01) p.heading += (this.rand() - 0.5) * 2;
      const n = { x: p.pos.x + Math.cos(p.heading) * 0.18 * DT, y: p.pos.y + Math.sin(p.heading) * 0.18 * DT };
      const { w, h } = this.world.size;
      if (n.x < 0.2 || n.x > w - 0.2 || n.y < 0.2 || n.y > h - 0.2) p.heading += Math.PI * (0.6 + this.rand() * 0.8);
      else p.pos = n;
    }
  }

  private inside(p: Vec2): Vec2 {
    const { w, h } = this.world.size;
    return { x: clamp(p.x, 0.12, w - 0.12), y: clamp(p.y, 0.12, h - 0.12) };
  }

  /* ---------------- outputs ---------------- */

  private emitTelemetry() {
    const telemetry: Telemetry = {
      t: this.t,
      mode: this.mode,
      phase: this.estop ? "Parada de emergencia" : this.phase,
      task: this.task,
      pose: { ...this.pose },
      speed: { ...this.cmd },
      joints: [...this.joints] as Joints,
      gripper: this.gripper,
      battery: this.battery,
      carrying: this.carryingLabel,
      estop: this.estop,
    };
    this.h.onMessage({ type: "telemetry", telemetry });
  }

  private emitWorld() {
    this.h.onMessage({ type: "world", world: structuredClone(this.world) });
  }

  private emitDetections() {
    const ds: Detection[] = [];
    for (const o of this.world.objects) {
      if (o.state !== "free" || !this.visible(o.pos, 1.5)) continue;
      ds.push({ id: o.id, cls: o.cls, confidence: 0.82 + 0.15 * this.hash(o.id), pos: { ...o.pos } });
    }
    for (const p of this.world.people) {
      if (!this.visible(p.pos, 2.2)) continue;
      ds.push({ id: p.id, cls: p.isUser ? "persona (tú)" : "persona", confidence: 0.9 + 0.08 * this.hash(p.id), pos: { ...p.pos } });
    }
    this.h.onMessage({ type: "detections", detections: ds });
    this.h.onMessage({ type: "stats", stats: { ...this.stats } });
  }

  private event(level: EventLevel, text: string, speak?: string) {
    this.h.onMessage({ type: "event", event: { t: Date.now(), level, text, ...(speak ? { speak } : {}) } });
  }

  private hash(id: string) {
    let h = 0;
    for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 997;
    return h / 997;
  }

  private nid(prefix: string) {
    return `${prefix}${++this.idSeq}`;
  }

  private visible(p: Vec2, range: number) {
    const d = dist(this.pose, p);
    if (d > range || d < 0.05) return false;
    const a = Math.atan2(p.y - this.pose.y, p.x - this.pose.x);
    return Math.abs(wrap(a - this.pose.th)) <= FOV;
  }

  /* ---------------- modes ---------------- */

  private setMode(mode: Mode) {
    this.mode = mode;
    this.cmd = { v: 0, w: 0 };
    this.program = null;
    this.confirmed = false;
    if (mode !== "asistente") this.requests = [];
    if (this.carrying) {
      // a mission was interrupted while carrying something: leave it on the floor where the robot is
      this.carrying.state = "free";
      this.event("warn", `Solté ${this.carrying.cls} al cambiar de modo.`);
      this.carrying = null;
    }
    this.carryingLabel = null;
    switch (mode) {
      case "idle":
        this.phase = "Listo";
        this.task = "Esperando instrucciones";
        this.jointTarget = [...POSE_PRESETS.home] as Joints;
        break;
      case "manual":
        this.phase = "Control manual";
        this.task = "Mando por el operador";
        break;
      case "ordenar":
        this.program = this.ordenar();
        this.event("info", "Modo ordenar zona: inicio de barrido.");
        break;
      case "asistente":
        this.program = this.asistente();
        this.event("info", "Modo asistente: te sigo y atiendo pedidos.");
        break;
      case "saludo":
        this.program = this.saludo();
        this.event("info", "Modo saludo: buscando personas.");
        break;
    }
  }

  private set(phase: string, task: string) {
    this.phase = phase;
    this.task = task;
  }

  /** Drive towards p until within tol; `until` may interrupt and return a value. */
  private *goto<T>(p: Vec2, tol = 0.08, until?: () => T | null): Generator<void, T | null, void> {
    while (true) {
      if (until) {
        const hit = until();
        if (hit) {
          this.cmd = { v: 0, w: 0 };
          return hit;
        }
      }
      const d = dist(this.pose, p);
      if (d <= tol) break;
      const err = wrap(Math.atan2(p.y - this.pose.y, p.x - this.pose.x) - this.pose.th);
      const w = clamp(3 * err, -MAX_W, MAX_W);
      const v = Math.abs(err) > 0.9 ? 0 : MAX_V * Math.cos(err) * clamp(d / 0.4, 0.35, 1);
      this.cmd = { v, w };
      yield;
    }
    this.cmd = { v: 0, w: 0 };
    return null;
  }

  private *face(p: Vec2): Step {
    while (true) {
      const err = wrap(Math.atan2(p.y - this.pose.y, p.x - this.pose.x) - this.pose.th);
      if (Math.abs(err) < 0.05) break;
      this.cmd = { v: 0, w: clamp(3 * err, -MAX_W, MAX_W) };
      yield;
    }
    this.cmd = { v: 0, w: 0 };
  }

  private *arm(j: Joints, grip?: number): Step {
    this.jointTarget = [...j] as Joints;
    if (grip !== undefined) this.gripperTarget = grip;
    while (this.joints.some((v, i) => Math.abs(v - this.jointTarget[i]) > 0.5) || Math.abs(this.gripper - this.gripperTarget) > 0.01) yield;
  }

  private *wait(s: number): Step {
    const end = this.t + s;
    while (this.t < end) yield;
  }

  private *ordenar(): Step {
    const { zone, drop, classes } = this.config.ordenar;
    const pts: Vec2[] = [];
    const m = 0.2;
    let row = 0;
    for (let y = zone.y0 + m; y <= zone.y1 - m + 1e-6; y += 0.4, row++) {
      const xs = [zone.x0 + m, zone.x1 - m];
      if (row % 2) xs.reverse();
      pts.push({ x: xs[0], y }, { x: xs[1], y });
    }
    const inZone = (p: Vec2) => p.x >= zone.x0 && p.x <= zone.x1 && p.y >= zone.y0 && p.y <= zone.y1;
    const target = () =>
      this.world.objects.find((o) => o.state === "free" && classes.includes(o.cls) && inZone(o.pos) && this.visible(o.pos, 0.9)) ?? null;

    yield* this.arm(POSE_PRESETS.plegado, 0.4);
    let i = 0;
    while (i < pts.length) {
      this.set("Patrullando", `Barrido ${Math.round((i / pts.length) * 100)} % de la zona`);
      const hit = yield* this.goto(pts[i], 0.08, target);
      if (!hit) {
        i++;
        continue;
      }
      // pick the object up
      this.set("Objeto detectado", `${hit.cls} a ${dist(this.pose, hit.pos).toFixed(2)} m`);
      this.event("info", `Detecté: ${hit.cls}.`);
      yield* this.wait(0.4);
      this.set("Aproximando", `Acercándome a ${hit.cls}`);
      yield* this.goto(hit.pos, 0.22);
      yield* this.face(hit.pos);
      this.set("Agarrando", `Tomando ${hit.cls}`);
      yield* this.arm(POSE_PRESETS.recoger, 1);
      yield* this.arm(POSE_PRESETS.recoger, 0.05);
      hit.state = "carried";
      this.carrying = hit;
      this.carryingLabel = hit.cls;
      yield* this.arm(POSE_PRESETS.transportar);
      this.set("Transportando", `Llevando ${hit.cls} al punto de entrega`);
      yield* this.goto(drop, 0.3);
      yield* this.face(drop);
      this.set("Depositando", `Dejando ${hit.cls}`);
      yield* this.arm(POSE_PRESETS.recoger);
      yield* this.arm(POSE_PRESETS.recoger, 1);
      hit.state = "stored";
      hit.pos = { x: drop.x + (this.rand() - 0.5) * 0.25, y: drop.y + (this.rand() - 0.5) * 0.25 };
      this.carrying = null;
      this.carryingLabel = null;
      this.stats.collected++;
      this.event("ok", `${hit.cls} guardado en el punto de entrega.`);
      yield* this.arm(POSE_PRESETS.plegado, 0.4);
    }
    const left = this.world.objects.filter((o) => o.state === "free" && classes.includes(o.cls) && inZone(o.pos)).length;
    this.set("Completado", left ? `Barrido terminado, ${left} objeto(s) sin alcanzar` : "Zona ordenada");
    this.event(left ? "warn" : "ok", left ? `Quedaron ${left} objeto(s) sin recoger.` : "¡Zona ordenada!");
    yield* this.goto({ x: drop.x - 0.4, y: drop.y }, 0.1);
    yield* this.arm(POSE_PRESETS.home, 0.4);
  }

  private *asistente(): Step {
    yield* this.arm(POSE_PRESETS.plegado, 0.4);
    const user = () => this.world.people.find((p) => p.isUser) ?? this.world.people[0];
    const follow = () => this.config.asistente.followDistance;
    const near = (d: number): Vec2 => {
      const u = user().pos;
      const a = Math.atan2(this.pose.y - u.y, this.pose.x - u.x);
      return this.inside({ x: u.x + d * Math.cos(a), y: u.y + d * Math.sin(a) });
    };
    while (true) {
      const req = this.requests.shift();
      if (!req) {
        this.set("Acompañando", `A tu lado (${dist(this.pose, user().pos).toFixed(2)} m)`);
        if (dist(this.pose, user().pos) > follow() + 0.15) {
          yield* this.goto(near(follow()), 0.06, () => (this.requests.length ? true : null));
        } else {
          yield* this.face(user().pos);
          yield;
        }
        continue;
      }
      this.confirmed = false;
      if (req.action === "entregar") {
        this.set("Buscando herramienta", `Voy por: ${req.item}`);
        yield* this.goto(this.world.toolStation, 0.3);
        yield* this.face(this.world.toolStation);
        this.set("Agarrando", `Tomando ${req.item}`);
        yield* this.arm(POSE_PRESETS.recoger, 1);
        yield* this.arm(POSE_PRESETS.recoger, 0.1);
        this.carryingLabel = req.item;
        yield* this.arm(POSE_PRESETS.transportar);
        this.set("Llevando", `Te llevo: ${req.item}`);
        yield* this.goto(near(0.55), 0.08);
        yield* this.face(user().pos);
        yield* this.arm(POSE_PRESETS.entregar);
        this.set("Entregando", `Toma ${req.item} y confirma`);
        this.event("info", `Aquí tienes: ${req.item}.`, `Aquí tienes ${req.item}`);
        const end = this.t + 25;
        while (!this.confirmed && this.t < end) yield;
        yield* this.arm(POSE_PRESETS.entregar, 1);
        this.carryingLabel = null;
        this.stats.delivered++;
        this.event("ok", `Entregado: ${req.item}.`);
      } else {
        this.set("Recibiendo", "Voy a recibir el material");
        yield* this.goto(near(0.55), 0.08);
        yield* this.face(user().pos);
        yield* this.arm(POSE_PRESETS.entregar, 1);
        this.set("Esperando material", `Pon «${req.item}» en la pinza y confirma`);
        this.event("info", `Listo para recibir: ${req.item}.`, "Pon el material en mi pinza");
        const end = this.t + 25;
        while (!this.confirmed && this.t < end) yield;
        yield* this.arm(POSE_PRESETS.entregar, 0.1);
        this.carryingLabel = req.item;
        yield* this.arm(POSE_PRESETS.transportar);
        this.set("Guardando", `Llevando ${req.item} al contenedor`);
        yield* this.goto(this.world.materialBin, 0.3);
        yield* this.face(this.world.materialBin);
        yield* this.arm(POSE_PRESETS.recoger);
        yield* this.arm(POSE_PRESETS.recoger, 1);
        this.carryingLabel = null;
        this.stats.received++;
        this.event("ok", `${req.item} guardado en el contenedor.`);
      }
      yield* this.arm(POSE_PRESETS.plegado, 0.4);
    }
  }

  private *wave(): Step {
    for (let k = 0; k < 3; k++) {
      yield* this.arm([this.joints[0], 10, 60, -20, 35], 1);
      yield* this.arm([this.joints[0], 10, 75, -35, -35], 1);
    }
    yield* this.arm(POSE_PRESETS.plegado, 0.4);
  }

  private *saludo(): Step {
    yield* this.arm(POSE_PRESETS.plegado, 0.4);
    const { w, h } = this.world.size;
    const cfg = () => this.config.saludo;
    const candidate = (): Person | null =>
      this.world.people.find(
        (p) => !p.isUser && this.visible(p.pos, cfg().range) && (!p.lastGreeted || this.t - p.lastGreeted > cfg().cooldownS),
      ) ?? null;
    let seenByCamera = this.cameraPerson;
    while (true) {
      if (this.cameraPerson !== seenByCamera) {
        seenByCamera = this.cameraPerson;
        this.set("Saludando", "Persona vista por la cámara");
        this.event("ok", "¡Hola! (persona detectada por la cámara)", cfg().greeting);
        this.stats.greeted++;
        yield* this.wave();
        continue;
      }
      const goal = { x: 0.4 + this.rand() * (w - 0.8), y: 0.4 + this.rand() * (h - 0.8) };
      this.set("Buscando personas", "Recorriendo el área");
      const p = yield* this.goto<Person | "camera">(goal, 0.15, () =>
        candidate() ?? (this.cameraPerson !== seenByCamera ? "camera" : null),
      );
      if (!p || p === "camera") continue;
      this.set("Acercándome", `Voy a saludar a ${p.name}`);
      p.lastGreeted = this.t;
      const a = Math.atan2(this.pose.y - p.pos.y, this.pose.x - p.pos.x);
      yield* this.goto(this.inside({ x: p.pos.x + 0.9 * Math.cos(a), y: p.pos.y + 0.9 * Math.sin(a) }), 0.1);
      yield* this.face(p.pos);
      p.lastGreeted = this.t;
      this.set("Saludando", `¡Hola, ${p.name}!`);
      this.event("ok", `Saludé a ${p.name}.`, cfg().greeting);
      this.stats.greeted++;
      yield* this.wave();
    }
  }
}
