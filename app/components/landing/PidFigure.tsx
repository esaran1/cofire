"use client";

import { domainLabel } from "@/lib/domainNames";
import { useT } from "@/lib/i18n";

/*
 * Bars grow by transform, not by width.
 *
 * Animating `width` from 0 means the bar has no length until the animation
 * runs, so any renderer that does not scroll shows an empty chart. Scaling a
 * bar that already has its real width degrades to a correct, static chart.
 */

/**
 * PID against ACI on the sealed 2026 holdout, drawn from the look-3 artifacts.
 *
 * Not decoration: this is the finding. Each pair of bars is one domain and
 * horizon; the dark bar is the reference conformal PID controller's worst
 * rolling 13-week coverage and the red bar is ACI's on the same rows. The
 * dashed line is the 0.90 target, and the floor the preregistration set was
 * 0.70.
 *
 * Values come from facts.json, generated from artifacts. Nothing here is typed
 * by hand.
 */
export function PidVsAciFigure({
  rows,
  target = 0.9,
  floor = 0.7,
  caption,
}: {
  rows: { domain: string; horizon: number; impl: string; roll13_min: number }[];
  target?: number;
  floor?: number;
  /** Plain-language caption for the story; the default is the technical one. */
  caption?: string;
}) {
  const { t } = useT();
  const axisMin = floor;
  const targetAt = (target - axisMin) / (1 - axisMin);
  const pairs = [...new Set(rows.map((r) => `${r.domain}|${r.horizon}`))].map((key) => {
    const [domain, horizon] = key.split("|");
    const pid = rows.find(
      (r) => r.domain === domain && String(r.horizon) === horizon && r.impl === "reference_pid",
    );
    const aci = rows.find(
      (r) => r.domain === domain && String(r.horizon) === horizon && r.impl === "aci",
    );
    return { domain, horizon, pid: pid?.roll13_min ?? null, aci: aci?.roll13_min ?? null };
  });

  const bar = (v: number | null, tone: "pid" | "aci") => {
    if (v === null) return null;
    // The axis starts at the pre-registered floor, not at zero.
    //
    // Every value here sits between 0.61 and 0.94, so a 0-to-1 axis pushes the
    // entire comparison into the right-hand third of the chart and the bars
    // read as identical. The floor is the number the forecast had to clear, so
    // starting there is the honest frame as well as the legible one, and the
    // caption states it.
    const span = 1 - axisMin;
    const width = `${Math.max(0, Math.min(1, (v - axisMin) / span)) * 100}%`;
    return (
      <div
        className={
          tone === "pid"
            ? "bar-grow h-full origin-left rounded-r-sm bg-ink"
            : "bar-grow h-full origin-left rounded-r-sm bg-ember"
        }
        style={{ width }}
      />
    );
  };

  return (
    <figure className="w-full">
      <div className="relative border-y border-rule py-8 md:py-10">
        <ul className="space-y-5">
          {pairs.map((p) => (
            <li key={`${p.domain}-${p.horizon}`} className="grid grid-cols-[6rem_1fr] items-center gap-5 md:grid-cols-[9rem_1fr]">
              <span className="text-xs leading-snug md:text-sm">
                <span className="block text-ink-soft">{domainLabel(p.domain)}</span>
                <span className="block text-mute">{t("scrub.weeks", { h: String(p.horizon) })}</span>
              </span>
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <Track at={targetAt} tone="ink">{bar(p.pid, "pid")}</Track>
                  <span className="num w-16 text-right text-sm text-ink md:text-base">
                    {p.pid === null ? "n/a" : p.pid.toFixed(3)}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <Track at={targetAt} tone="ink">{bar(p.aci, "aci")}</Track>
                  <span className="num w-16 text-right text-sm text-mute md:text-base">
                    {p.aci === null ? "n/a" : p.aci.toFixed(3)}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-5 max-w-[68ch] text-xs leading-relaxed text-mute md:text-sm">
        {caption ??
          "Worst rolling 13-week coverage on the sealed 2026 holdout. Dark is the reference conformal PID controller, pale is ACI on the same rows. The axis starts at the pre-registered floor of 0.70; the dashed line is the 0.90 target."}
      </figcaption>
    </figure>
  );
}

/**
 * Reliability by horizon, the test that failed.
 *
 * Each bar is the mean Murphy reliability term across the shipped probabilistic
 * targets at that horizon, against the 0.05 threshold the preregistration set
 * before the look. Lower is better: reliability near zero means stated
 * probabilities match observed frequencies.
 */
export function ReliabilityFigure({
  byHorizon,
  threshold = 0.05,
  caption,
}: {
  byHorizon: Record<string, { mean: number; max: number; n: number }>;
  threshold?: number;
  caption?: string;
}) {
  const { t } = useT();
  const entries = Object.entries(byHorizon).sort((a, b) => Number(a[0]) - Number(b[0]));
  const scale = Math.max(threshold * 2, ...entries.map(([, v]) => v.max));

  return (
    <figure className="w-full">
      <div className="relative border-y border-rule py-8 md:py-10">
        <ul className="space-y-6">
          {entries.map(([h, v]) => (
            <li key={h} className="grid grid-cols-[6rem_1fr] items-center gap-5 md:grid-cols-[9rem_1fr]">
              <span className="text-xs text-ink-soft md:text-sm">{t("scrub.weeks", { h })}</span>
              <div className="flex items-center gap-3">
                <Track at={threshold / scale} tone="ember">
                  <div
                    className={
                      v.mean > threshold
                        ? "bar-grow h-full origin-left bg-ember"
                        : "bar-grow h-full origin-left bg-ink"
                    }
                    style={{ width: `${(v.mean / scale) * 100}%` }}
                  />
                </Track>
                <span className="num w-20 text-right text-sm text-ink md:text-base">
                  {v.mean.toFixed(4)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-5 max-w-[68ch] text-xs leading-relaxed text-mute md:text-sm">
        {caption ??
          "Mean reliability term by horizon on the sealed 2026 holdout, lower is better. The dashed line is the 0.05 threshold set before the look. Two-week forecasts pass on both domains; the longer horizons are where it breaks."}
      </figcaption>
    </figure>
  );
}

/**
 * A bar's track, with the reference line drawn inside it.
 *
 * The line used to be positioned against the whole figure, label column
 * included, while the bars were positioned against this track. The two scales
 * disagreed, and on the reliability chart the 0.05 line landed left of where it
 * belonged, so the 4-week bar (0.0386, a pass) appeared to cross it and fail.
 * Drawing the line in the same box as the bar makes that impossible.
 */
function Track({
  at,
  tone,
  children,
}: {
  at: number;
  tone: "ink" | "ember";
  children: React.ReactNode;
}) {
  return (
    <div className="relative h-5 flex-1 bg-rule/40 md:h-6">
      {children}
      <div
        className={`pointer-events-none absolute -inset-y-1.5 border-l border-dashed ${
          tone === "ember" ? "border-ember" : "border-ink/45"
        }`}
        style={{ left: `${Math.max(0, Math.min(1, at)) * 100}%` }}
        aria-hidden
      />
    </div>
  );
}
