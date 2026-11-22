import type { Metadata } from "next";
import Link from "next/link";
import { RoverViewer } from "./viewer";

export const metadata: Metadata = {
  title: "Nexa · Cámara del rover",
  robots: { index: false, follow: false },
};

export default function RoverPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8">
      <Link href="/" className="text-sm text-accent hover:underline">Volver a la consola</Link>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">Cámara del rover</h1>
      <p className="mt-2 mb-6 text-sm text-muted">Vista en directo compartida desde el computador del rover.</p>
      <RoverViewer />
    </main>
  );
}
