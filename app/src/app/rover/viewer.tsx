"use client";

import { Camera } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

export function RoverViewer() {
  const [code, setCode] = useState("");
  const [key, setKey] = useState("");
  const [image, setImage] = useState("");
  const [status, setStatus] = useState("Ingresa el código que te dio el operador.");

  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let objectUrl = "";

    async function refresh() {
      let again = true;
      try {
        const response = await fetch("/api/rover-camera", {
          headers: { Authorization: `Bearer ${key}` },
          cache: "no-store",
          signal: controller.signal,
        });
        const nextUrl = response.status === 200 ? URL.createObjectURL(await response.blob()) : "";
        if (controller.signal.aborted) {
          if (nextUrl) URL.revokeObjectURL(nextUrl);
          return;
        }
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = nextUrl;
        setImage(nextUrl);
        if (response.status === 200) setStatus("En directo");
        else if (response.status === 204) setStatus("Esperando que el operador comparta la cámara.");
        else if (response.status === 401) {
          setStatus("Código incorrecto. Pide el código al operador.");
          again = false;
        } else if (response.status === 503) {
          setStatus("La cámara del rover todavía no está configurada.");
          again = false;
        } else setStatus("Conexión interrumpida. Reintentando…");
      } catch {
        if (controller.signal.aborted) return;
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = "";
        setImage("");
        setStatus("Conexión interrumpida. Reintentando…");
      }
      if (again && !controller.signal.aborted) timer = setTimeout(refresh, 850);
    }

    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [key]);

  function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const entered = code.trim().toLowerCase();
    if (!/^[a-f0-9]{64}$/.test(entered)) {
      setStatus("Ingresa el código completo de 64 caracteres.");
      return;
    }
    if (entered === key) return;
    setImage("");
    setStatus("Conectando…");
    setKey(entered);
    setCode("");
  }

  function disconnect() {
    setKey("");
    setImage("");
    setStatus("Vista de cámara cerrada.");
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex aspect-video items-center justify-center bg-black/40">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element -- ephemeral authenticated snapshot
          <img className="h-full w-full object-contain" alt="Imagen de la cámara del rover" src={image} />
        ) : (
          <Camera size={44} strokeWidth={1.2} className="text-muted" aria-hidden="true" />
        )}
      </div>
      <div className="border-t border-line p-4">
        <p role="status" className={`mb-3 text-sm ${image ? "text-ok" : "text-muted"}`}>{status}</p>
        <form onSubmit={connect} className="flex flex-wrap items-end gap-2">
          <label className="grid min-w-48 flex-1 gap-1 text-xs text-muted">
            Código de acceso
            <input autoComplete="off" type="password" value={code}
              onChange={(event) => setCode(event.target.value)}
              className="rounded-lg border border-line-strong bg-bg px-3 py-2 text-base text-text" />
          </label>
          <button className="rounded-lg bg-accent px-4 py-2 font-medium text-bg" type="submit">Ver cámara</button>
          {key && <button className="rounded-lg border border-line-strong px-4 py-2 text-sm"
            onClick={disconnect} type="button">Cerrar vista</button>}
        </form>
      </div>
    </section>
  );
}
