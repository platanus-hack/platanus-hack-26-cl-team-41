"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "ghost" | "danger" | "subtle" | "ok";

export function Button({
  variant = "subtle",
  size = "md",
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg" }) {
  const v: Record<Variant, string> = {
    primary: "bg-accent text-[#04141a] hover:brightness-110 shadow-[0_0_24px_-6px_var(--accent)]",
    ok: "bg-ok text-[#03170f] hover:brightness-110",
    danger: "bg-danger text-white hover:brightness-110 shadow-[0_0_24px_-8px_var(--danger)]",
    ghost: "bg-transparent text-text hover:bg-white/5 border border-line",
    subtle: "bg-white/[0.04] text-text hover:bg-white/[0.08] border border-line",
  };
  const s = { sm: "h-8 px-3 text-xs", md: "h-10 px-4 text-sm", lg: "h-12 px-5 text-base" }[size];
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:opacity-40 disabled:pointer-events-none select-none",
        v[variant],
        s,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Card({
  title,
  icon,
  actions,
  className,
  bodyClassName,
  children,
}: {
  title?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx("panel flex flex-col min-w-0", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 px-4 pt-3.5 pb-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-text/90">
            {icon && <span className="text-accent">{icon}</span>}
            {title}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cx("px-4 pb-4 min-h-0", !title && !actions && "pt-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Badge({ tone = "muted", children, className }: { tone?: "muted" | "accent" | "ok" | "warn" | "danger"; children: ReactNode; className?: string }) {
  const t = {
    muted: "text-muted bg-white/[0.04] border-line",
    accent: "text-accent bg-accent/10 border-accent/30",
    ok: "text-ok bg-ok/10 border-ok/30",
    warn: "text-warn bg-warn/10 border-warn/30",
    danger: "text-danger bg-danger/10 border-danger/30",
  }[tone];
  return <span className={cx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", t, className)}>{children}</span>;
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-4 py-1.5 cursor-pointer select-none">
      <span className="text-sm text-text/90">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx("relative h-6 w-11 rounded-full transition border", checked ? "bg-accent/80 border-accent" : "bg-white/5 border-line")}
      >
        <span className={cx("absolute top-0.5 h-[18px] w-[18px] rounded-full bg-white transition-all", checked ? "left-[22px]" : "left-0.5")} />
      </button>
    </label>
  );
}

export function Stat({ label, value, sub, icon, tone }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode; tone?: "accent" | "ok" | "warn" | "danger" }) {
  const c = tone ? { accent: "text-accent", ok: "text-ok", warn: "text-warn", danger: "text-danger" }[tone] : "text-text";
  return (
    <div className="panel px-4 py-3.5 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="label">{label}</div>
        <div className={cx("mt-1 text-xl font-semibold truncate", c)}>{value}</div>
        {sub && <div className="mt-0.5 text-xs text-muted truncate">{sub}</div>}
      </div>
      {icon && <div className="text-muted">{icon}</div>}
    </div>
  );
}

export function Slider({
  label,
  value,
  min,
  max,
  step = 1,
  unit = "",
  onChange,
}: {
  label: ReactNode;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block py-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-text/90">{label}</span>
        <span className="num text-muted text-xs">
          {Number.isInteger(step) ? Math.round(value) : value.toFixed(2)}
          {unit}
        </span>
      </div>
      <input className="w-full mt-1" type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block py-1.5">
      <div className="label mb-1.5">{label}</div>
      {children}
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </label>
  );
}

export const inputCls =
  "w-full h-10 rounded-xl bg-black/30 border border-line px-3 text-sm text-text placeholder:text-muted/60 outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20";
