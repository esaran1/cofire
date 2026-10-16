"use client";

import { ReactNode, useState } from "react";
import { useT } from "@/lib/i18n";

/**
 * Shared control layer. One radius rule (surfaces near-sharp at 2px,
 * interactive elements full-pill), one accent (ember), one numeral treatment.
 * Route files use these; they do not invent values.
 *
 * Nothing here imports the animation library, so a page that uses only these
 * (the map, the brief) does not download it. The animated controls,
 * Segmented and CountUp, are in ./Animated.
 */

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
  const { t } = useT();
  return (
    <div className="rounded border border-ember/40 bg-ember-soft p-4">
      <p className="text-sm text-ember">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-ink underline underline-offset-4">
          {t("ui.retry")}
        </button>
      )}
    </div>
  );
}

export function OfflineNote() {
  // The static site has no service at all; saying "no connection" there would
  // suggest retrying something that will never answer.
  const isStatic = !!process.env.NEXT_PUBLIC_DATA_BASE;
  const { t } = useT();
  return (
    <div className="rounded border border-ochre/40 bg-ochre-soft p-4" data-testid="offline-note">
      <p className="text-sm text-ochre">
        {isStatic ? t("ui.offlineStatic") : t("ui.offline")}
      </p>
    </div>
  );
}

/** Page header. One shape for every route, so the app feels like one app. */
export function PageHeader({ title, lede }: { title: ReactNode; lede: string }) {
  return (
    <header className="border-b border-rule bg-paper-raised">
      <div className="measure px-6 py-12 md:py-16">
        <h1 className="display max-w-[18ch] text-4xl md:text-5xl">{title}</h1>
        <p className="mt-4 max-w-prose leading-relaxed text-ink-soft">{lede}</p>
      </div>
    </header>
  );
}

/** Standard content well, so every route shares one measure. */
export function Well({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`measure px-6 py-12 ${className}`}>{children}</div>;
}

/**
 * Progressive disclosure. The summary is always visible; the detail is one
 * click away.
 *
 * This exists because the reason strings that justify every number are
 * genuinely useful and genuinely long. Printing them inline repeated the same
 * 30-word paragraph nine times on a single Place Card, which buried the
 * numbers the card exists to show. A reader who wants the justification asks
 * for it; a reader who does not gets a scannable page.
 */
export function Disclosure({
  summary,
  children,
  detail,
}: {
  summary: ReactNode;
  children: ReactNode;
  /** Short label for the toggle, e.g. "Why". */
  detail?: string;
}) {
  const [open, setOpen] = useState(false);
  const { t } = useT();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 flex-1">{summary}</div>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="text-mute hover:text-ink shrink-0 text-[11px] underline underline-offset-2 transition-colors"
        >
          {open ? t("ui.hide") : (detail ?? t("ui.why"))}
        </button>
      </div>
      {open && (
        // Slides a few pixels into place (globals.css); never fades from nothing.
        <div className="disclosure-in">
          <div className="text-mute pt-2 text-[11px] leading-relaxed">{children}</div>
        </div>
      )}
    </div>
  );
}

/**
 * A headline result: the number, what it means, and whether it passed.
 *
 * Replaces the pattern of leading a section with a paragraph that the reader
 * has to parse to find the verdict. The verdict is the first thing rendered.
 */
export function Verdict({
  value,
  label,
  tone = "neutral",
  sub,
}: {
  value: string;
  label: string;
  tone?: "pass" | "fail" | "neutral";
  sub?: string;
}) {
  const color =
    tone === "fail" ? "text-ember" : tone === "pass" ? "text-ink" : "text-ink";
  return (
    <div>
      <div className={`display text-4xl font-normal md:text-5xl ${color}`}>{value}</div>
      <div className="text-ink mt-1 text-sm">{label}</div>
      {sub ? <div className="text-mute mt-0.5 text-xs">{sub}</div> : null}
    </div>
  );
}

/**
 * One measurement in a scannable row. Used instead of a table when the reader
 * needs to compare a handful of values rather than read a dataset.
 */
export function StatRow({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "pass" | "fail" | "neutral";
}) {
  return (
    <div className="border-rule flex items-baseline justify-between gap-4 border-b py-2 last:border-b-0">
      <span className="text-ink-soft text-sm">{label}</span>
      <span
        className={`num text-sm ${tone === "fail" ? "text-ember" : "text-ink"}`}
      >
        {value}
      </span>
    </div>
  );
}
