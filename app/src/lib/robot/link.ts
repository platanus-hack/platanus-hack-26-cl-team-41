import type { ClientMessage, RobotMessage, Vec2 } from "./types";

/** A connection to a robot: the real one over WebSocket, or the built-in simulator. */
export interface RobotLink {
  readonly kind: "sim" | "ws";
  send(msg: ClientMessage): void;
  close(): void;
}

/** Extra controls only the simulator has (moving people around, resetting the world). */
export interface SimControls {
  movePerson(id: string, pos: Vec2): void;
  addPerson(pos: Vec2): void;
  scatterObjects(n: number): void;
  resetWorld(): void;
}

export type LinkHandlers = {
  onMessage: (msg: RobotMessage) => void;
  onStatus: (status: "connecting" | "open" | "closed" | "error", detail?: string) => void;
};

export class WebSocketLink implements RobotLink {
  readonly kind = "ws" as const;
  private ws: WebSocket;
  private closedByUser = false;

  constructor(url: string, private h: LinkHandlers) {
    h.onStatus("connecting", url);
    this.ws = new WebSocket(url);
    this.ws.onopen = () => {
      h.onStatus("open", url);
      this.send({ type: "hello", client: "nexa-console", version: 1 });
    };
    this.ws.onerror = () => h.onStatus("error", "No se pudo conectar con el robot");
    this.ws.onclose = () => {
      if (!this.closedByUser) h.onStatus("closed", "Conexión cerrada");
    };
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(typeof ev.data === "string" ? ev.data : "") as RobotMessage;
        if (msg && typeof msg === "object" && "type" in msg) h.onMessage(msg);
      } catch {
        // ignore malformed frames
      }
    };
  }

  send(msg: ClientMessage) {
    if (this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  close() {
    this.closedByUser = true;
    this.ws.close();
    this.h.onStatus("closed");
  }
}
