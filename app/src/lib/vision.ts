"use client";

// In-browser detector (COCO-SSD on TensorFlow.js). Loaded lazily, only when a camera is started.
export type BrowserDetection = { cls: string; label: string; score: number; bbox: [number, number, number, number] };

const ES: Record<string, string> = {
  person: "persona",
  bottle: "botella",
  cup: "taza",
  "wine glass": "copa",
  bowl: "bol",
  "cell phone": "celular",
  book: "libro",
  scissors: "tijeras",
  "teddy bear": "juguete",
  "sports ball": "pelota",
  keyboard: "teclado",
  mouse: "mouse",
  remote: "control",
  laptop: "notebook",
  backpack: "mochila",
  banana: "plátano",
  apple: "manzana",
  orange: "naranja",
  chair: "silla",
  "potted plant": "planta",
  clock: "reloj",
  vase: "florero",
  toothbrush: "cepillo",
  spoon: "cuchara",
  fork: "tenedor",
  knife: "cuchillo",
};

type Model = { detect: (img: HTMLVideoElement, max?: number, minScore?: number) => Promise<{ class: string; score: number; bbox: [number, number, number, number] }[]> };

let modelPromise: Promise<Model> | null = null;

export function loadDetector(): Promise<Model> {
  if (!modelPromise) {
    modelPromise = (async () => {
      const tf = await import("@tensorflow/tfjs");
      await tf.ready();
      const coco = await import("@tensorflow-models/coco-ssd");
      return (await coco.load({ base: "lite_mobilenet_v2" })) as unknown as Model;
    })();
    modelPromise.catch(() => {
      modelPromise = null;
    });
  }
  return modelPromise;
}

export async function detect(video: HTMLVideoElement, minScore: number): Promise<BrowserDetection[]> {
  const model = await loadDetector();
  const out = await model.detect(video, 20, minScore);
  return out.map((d) => ({ cls: d.class, label: ES[d.class] ?? d.class, score: d.score, bbox: d.bbox }));
}
