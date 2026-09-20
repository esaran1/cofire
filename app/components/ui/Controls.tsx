"use client";

import { motion, useReducedMotion } from "motion/react";
import { ReactNode } from "react";

/**
 * Shared control layer. One radius rule (surfaces near-sharp at 2px,
 * interactive elements full-pill), one accent (ember), one numeral treatment.
 * Route files use these; they do not invent values.
 */

/** Segmented picker. A real control, not a styled <select>. */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
  tone = "ember",
}: {
  options: { value: T; label: string; hint?: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  tone?: "ember" | "ochre";
}) {
  const reduce = useReducedMotion();
  const fill = tone === "ochre" ? "bg-ochre" : "bg-ember";
  return (
    <fieldset>
      <legend className="text-sm font-medium text-ink">{label}</legend>
      <div
        role="radiogroup"
        aria-label={label}
        className="mt-2 flex flex-wrap gap-1 rounded-full border border-rule bg-paper-raised p-1"
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
              className={`relative flex-1 min-w-[5rem] rounded-full px-3 py-2 text-sm transition-transform active:scale-[0.97] ${
                active ? "text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {active && (
                <motion.span
                  layoutId={`seg-${label}`}
                  className={`absolute inset-0 rounded-full ${fill}`}
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <span className="relative z-10 block font-medium leading-tight">{o.label}</span>
              {o.hint && <span className="relative z-10 block text-[11px] leading-tight opacity-75">{o.hint}</span>}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Every measurement in the app renders through this. Mono, tabular. */
export function Numeral({
  value,
  suffix,
  tone = "ink",
  size = "lg",
}: {
  value: string | number;
  suffix?: string;
  tone?: "ink" | "ember" | "ochre" | "mute";
  size?: "sm" | "lg" | "xl";
}) {
  const color =
    tone === "ember" ? "text-ember" : tone === "ochre" ? "text-ochre" : tone === "mute" ? "text-mute" : "text-ink";
  const scale = size === "xl" ? "text-4xl" : size === "sm" ? "text-base" : "text-2xl";
  return (
    <span className={`num ${scale} ${color}`}>
      {value}
      {suffix && <span className="ml-0.5 text-[0.55em] opacity-70">{suffix}</span>}
    </span>
  );
}

/** Primary action. One label per intent across the whole app. */
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
      ? "bg-ember text-paper disabled:bg-ember/40"
      : "border border-rule text-ink hover:border-ink-soft disabled:opacity-50";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full px-5 py-2.5 text-sm font-medium transition-transform active:scale-[0.98] disabled:active:scale-100 ${base}`}
    >
      {busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}

/** A grouped surface. Used sparingly; most grouping is rules and space. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded border border-rule bg-paper-raised p-5 ${className}`}>{children}</section>;
}

/** Skeleton shaped like the content it replaces, never a spinner. */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded bg-paper-sunk" />
      ))}
    </div>
  );
}

/** Empty state that says how to fill it. */
export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-rule bg-paper-raised p-8 text-center">
      <p className="font-medium text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-[40ch] text-sm leading-relaxed text-mute">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Inline, contextual error. Never a toast for a persistent problem. */
export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded border border-ember/40 bg-ember-soft p-4">
      <p className="text-sm text-ember">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-ink underline underline-offset-4">
          Try again
        </button>
      )}
    </div>
  );
}

export function OfflineNote() {
  return (
    <div className="rounded border border-ochre/40 bg-ochre-soft p-4">
      <p className="text-sm text-ochre">
        No connection to the forecast service. Showing what is cached on this device.
      </p>
    </div>
  );
}

/** Page header. One shape for every route, so the app feels like one app. */
export function PageHeader({ title, lede }: { title: ReactNode; lede: string }) {
  return (
    <header className="border-b border-rule bg-paper-raised">
      <div className="mx-auto max-w-[1400px] px-6 py-12 md:py-16">
        <h1 className="display max-w-[18ch] text-4xl md:text-5xl">{title}</h1>
        <p className="mt-4 max-w-prose leading-relaxed text-ink-soft">{lede}</p>
      </div>
    </header>
  );
}

/** Standard content well, so every route shares one measure. */
export function Well({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto max-w-[1400px] px-6 py-12 ${className}`}>{children}</div>;
}
