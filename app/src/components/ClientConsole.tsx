"use client";

import dynamic from "next/dynamic";

const Console = dynamic(() => import("./Console"), {
  ssr: false,
  loading: () => (
    <div className="grid min-h-screen place-items-center">
      <div className="flex items-center gap-3 text-sm text-muted">
        <span className="h-2 w-2 rounded-full bg-accent animate-pulse" /> Iniciando consola…
      </div>
    </div>
  ),
});

export function ClientConsole() {
  return <Console />;
}
