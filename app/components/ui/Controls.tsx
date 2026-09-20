"use client";

import { motion, useReducedMotion } from "motion/react";
import { ReactNode } from "react";

/**
 * Shared control layer for the product routes. One vocabulary, one radius scale
 * (lg for surfaces, full for interactive pills), one accent (fire). No ad hoc
 * values in route files.
 */

/** Segmented picker. Real control, not a <select>. */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
  tone = "fire",
}: {
  options: { value: T; label: string; hint?: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  tone?: "fire" | "drought";
}) {
  const reduce = useReducedMotion();
  const accent = tone === "drought" ? "bg-drought" : "bg-fire";
  return (
    <fieldset>
      <legend className="text-xs uppercase tracking-wide text-mute">{label}</legend>
      <div
        role="radiogroup"
        aria-label={label}
        className="mt-2 flex flex-wrap gap-1.5 rounded-lg border border-white/10 p-1.5"
      >
        {options.map((o) => {
          const active = o.value === value;
          return (
            <button
              key={String(o.value)}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(o.value)}
              className={`relative flex-1 min-w-[4.5rem] rounded-full px-3 py-2 text-sm transition-transform active:scale-[0.97] ${
                active ? "text-ink" : "text-mute hover:text-paper"
              }`}
            >
              {active && (
                <motion.span
                  layoutId={`seg-${label}`}
                  className={`absolute inset-0 rounded-full ${accent}`}
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <span className="relative z-10 font-medium">{o.label}</span>
              {o.hint && <span className="relative z-10 block text-[10px] opacity-70">{o.hint}</span>}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Mono numeral treatment, used for every figure in the app. */
export function Numeral({
  value,
  suffix,
  tone = "paper",
  size = "lg",
}: {
  value: string | number;
  suffix?: string;
  tone?: "paper" | "fire" | "drought" | "mute";
  size?: "sm" | "lg" | "xl";
}) {
  const color =
    tone === "fire" ? "text-fire" : tone === "drought" ? "text-drought" : tone === "mute" ? "text-mute" : "text-paper";
  const scale = size === "xl" ? "text-4xl" : size === "sm" ? "text-lg" : "text-2xl";
  return (
    <span className={`font-mono tabular-nums tracking-tight ${scale} ${color}`}>
      {value}
      {suffix && <span className="text-sm opacity-60 ml-0.5">{suffix}</span>}
    </span>
  );
}

/** Primary action. One label per intent across the app. */
export function Action({
  children,
  onClick,
  type = "button",
  disabled,
  busy,
  variant = "primary",
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "quiet";
}) {
  const base =
    variant === "primary"
      ? "bg-fire text-ink disabled:bg-fire/40 disabled:text-ink/60"
      : "border border-white/15 text-paper hover:border-white/30 disabled:opacity-50";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-3 font-medium transition-transform active:scale-[0.98] disabled:active:scale-100 ${base}`}
    >
      {busy && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}

/** Section surface. Grouping by border and space, not nested cards. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-white/10 p-4 ${className}`}>{children}</section>;
}

/** Skeleton matching the final layout's shape, never a spinner. */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-9 animate-pulse rounded-lg bg-white/5" />
      ))}
    </div>
  );
}

/** Composed empty state that says how to populate it. */
export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-white/15 p-6 text-center">
      <p className="text-paper">{title}</p>
      <p className="mx-auto mt-1 max-w-[38ch] text-sm leading-relaxed text-mute">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Inline error. Contextual, not a toast. */
export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-fire/40 bg-fire/10 p-3">
      <p className="text-sm text-fire">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-paper underline underline-offset-4">
          Try again
        </button>
      )}
    </div>
  );
}

/** Offline banner. The app is demo-first and must say when it cannot reach the API. */
export function OfflineNote() {
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
      <p className="text-sm text-amber-300">
        No connection to the forecast service. Showing what is cached on this device.
      </p>
    </div>
  );
}
