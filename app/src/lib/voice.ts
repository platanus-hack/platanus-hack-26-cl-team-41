"use client";

import { TOOLS, type AssistantRequest } from "./robot/types";

type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

export function speechSupported() {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** Listens once in Spanish and resolves with the transcript. */
export function listenOnce(): Promise<string> {
  return new Promise((resolve, reject) => {
    const w = window as unknown as Record<string, new () => Recognition>;
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Ctor) return reject(new Error("Este navegador no reconoce voz (usa Chrome o Edge)."));
    const r = new Ctor();
    r.lang = "es-ES";
    r.interimResults = false;
    r.maxAlternatives = 1;
    let done = false;
    r.onresult = (e) => {
      done = true;
      resolve(e.results[0][0].transcript);
    };
    r.onerror = (e) => {
      done = true;
      reject(new Error(e.error === "not-allowed" ? "Permiso de micrófono denegado." : `Error de voz: ${e.error}`));
    };
    r.onend = () => {
      if (!done) reject(new Error("No escuché nada."));
    };
    r.start();
  });
}

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

/** "pásame el destornillador" -> entregar Destornillador; "recibe estos tornillos" -> recibir tornillos. */
export function parseCommand(text: string): AssistantRequest | "confirm" | null {
  const t = norm(text);
  if (/\b(listo|ya esta|recibido|gracias|toma|suelta)\b/.test(t)) return "confirm";
  const tool = TOOLS.find((x) => t.includes(norm(x)) || t.includes(norm(x).split(" ")[0]));
  if (/\b(pasame|pasa|traeme|trae|dame|necesito|alcanzame)\b/.test(t) && tool) return { action: "entregar", item: tool };
  const recv = t.match(/\b(?:recibe|recibeme|guarda|guardame|llevate|lleva)\b\s+(?:el|la|los|las|este|esta|estos|estas|esto)?\s*(.+)$/);
  if (recv) return { action: "recibir", item: recv[1].trim() || "material" };
  if (tool) return { action: "entregar", item: tool };
  return null;
}
