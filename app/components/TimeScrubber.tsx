"use client";

import type { CSSProperties } from "react";
import { locale, useT } from "@/lib/i18n";

/**
 * Map controls. Floats over the map because it controls the map, but it is a
 * real surface on paper rather than a dark box, so it belongs to the page.
 */
export function TimeScrubber({
  issues,
  issue,
  horizon,
  layer,
  onIssue,
  onHorizon,
  onLayer,
  burden = false,
}: {
  issues: string[];
  issue: string;
  horizon: string;
  layer: "drought" | "fire" | "burden";
  onIssue: (v: string) => void;
  onHorizon: (v: string) => void;
  onLayer: (v: "drought" | "fire" | "burden") => void;
  /** Offer the EnviroScreen neighborhoods layer (Denver only). */
  burden?: boolean;
}) {
  const { lang, t } = useT();
  const idx = Math.max(0, issues.indexOf(issue));
  const single = issues.length <= 1;

  // Each layer button carries a swatch of its own data colour: selection is ink,
  // as everywhere else, and the swatch keys the button to what the map draws.
  const layers: { key: "fire" | "drought" | "burden"; label: string; swatch: string; testid?: string }[] = [
    { key: "fire", label: t("scrub.fire"), swatch: "bg-ember" },
    { key: "drought", label: t("scrub.drought"), swatch: "bg-ochre" },
    ...(burden ? [{ key: "burden" as const, label: t("scrub.burden"), swatch: "bg-[#3b2a78]", testid: "layer-burden" }] : []),
  ];
  const pill = (on: boolean) =>
    `inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] transition-colors sm:px-3 sm:py-1.5 sm:text-sm ${
      on ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
    }`;
  const pct = single ? 100 : (idx / Math.max(1, issues.length - 1)) * 100;
  // The week timeline under the slider: one tick per weekly issue, a taller one
  // and a short month name where each month starts. Positions follow the
  // thumb's travel (16 px wide, so its centre runs from 8 px to 100% - 8 px).
  const at = (i: number) => `calc(8px + (100% - 16px) * ${i / Math.max(1, issues.length - 1)})`;
  const monthStarts = issues
    .map((iso, i) => ({ iso, i }))
    .filter(({ iso, i }) => i === 0 || issues[i - 1].slice(0, 7) !== iso.slice(0, 7));
  const monthName = (iso: string) =>
    new Date(`${iso}T12:00:00Z`).toLocaleDateString(locale(lang), { month: "short", timeZone: "UTC" });

  return (
    <div data-testid="time-scrubber" className="absolute inset-x-2 bottom-2 z-20 rounded border border-rule bg-paper/95 p-3 shadow-[0_2px_16px_rgba(22,26,25,0.08)] backdrop-blur sm:inset-x-4 sm:bottom-4 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex items-center gap-0.5 sm:gap-1" role="group" aria-label={t("scrub.horizon")}>
          {(["2", "4", "8"] as const).map((h) => (
            <button key={h} onClick={() => onHorizon(h)} aria-pressed={horizon === h} className={pill(horizon === h)}>
              {t("scrub.weeks", { h })}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-0.5 sm:gap-1" role="group" aria-label={t("scrub.layer")}>
          {layers.map((l) => (
            <button
              key={l.key}
              onClick={() => onLayer(l.key)}
              aria-pressed={layer === l.key}
              data-testid={l.testid}
              className={pill(layer === l.key)}
            >
              <span aria-hidden className={`h-2 w-2 shrink-0 rounded-[1px] ${l.swatch}`} />
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {!single && (
        <div className="mt-3 sm:mt-4">
          <label htmlFor="issue-scrub" className="flex items-baseline justify-between text-xs">
            <span className="text-mute">{t("scrub.issue")}</span>
            <span className="num text-ink">{issue || "n/a"}</span>
          </label>
          <input
            id="issue-scrub"
            type="range"
            min={0}
            max={Math.max(0, issues.length - 1)}
            value={idx}
            onChange={(e) => onIssue(issues[Number(e.target.value)] ?? issue)}
            className="range mt-1 w-full"
            style={{ "--pct": `${pct}%` } as CSSProperties}
          />
          <div aria-hidden className="relative -mt-1 h-5 select-none" data-testid="issue-timeline">
            {issues.map((iso, i) => {
              const starts = monthStarts.some((m) => m.i === i);
              return (
                <span
                  key={iso}
                  className={`absolute top-0 w-px ${starts ? "h-2 bg-ink-soft/50" : "h-1 bg-rule"}`}
                  style={{ left: at(i) }}
                />
              );
            })}
            {monthStarts.map(({ iso, i }) => (
              <span
                key={`m-${iso}`}
                className={`absolute top-2.5 text-[10px] leading-none text-mute ${
                  i / Math.max(1, issues.length - 1) > 0.92 ? "-translate-x-full" : ""
                }`}
                style={{ left: at(i) }}
              >
                {monthName(iso)}
              </span>
            ))}
          </div>
        </div>
      )}
      {single && issue && (
        <p className="mt-3 text-xs text-mute">
          {t("scrub.issued")} <span className="num text-ink">{issue}</span>. {t("scrub.single")}
        </p>
      )}
    </div>
  );
}
