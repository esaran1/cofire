"use client";


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
 * rolling 13-week coverage and the pale bar is ACI's on the same rows. The
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
}: {
  rows: { domain: string; horizon: number; impl: string; roll13_min: number }[];
  target?: number;
  floor?: number;
}) {
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
    const width = `${Math.max(0, Math.min(1, v)) * 100}%`;
    return (
      <div
        className={
          tone === "pid"
            ? "bar-grow h-full origin-left rounded-r-sm bg-ink"
            : "bar-grow h-full origin-left rounded-r-sm bg-ember/40"
        }
        style={{ width }}
      />
    );
  };

  return (
    <figure className="w-full">
      <div className="relative border-y border-rule py-6">
        <div
          className="pointer-events-none absolute inset-y-6 border-l border-dashed border-ink/40"
          style={{ left: `${target * 100}%` }}
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-y-6 border-l border-dashed border-ember/50"
          style={{ left: `${floor * 100}%` }}
          aria-hidden
        />
        <ul className="space-y-3">
          {pairs.map((p) => (
            <li key={`${p.domain}-${p.horizon}`} className="grid grid-cols-[7rem_1fr] items-center gap-3">
              <span className="text-[11px] uppercase tracking-wider text-mute">
                {p.domain} h{p.horizon}
              </span>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="h-3 flex-1 bg-rule/40">{bar(p.pid, "pid")}</div>
                  <span className="num w-14 text-right text-[11px] text-ink">
                    {p.pid === null ? "n/a" : p.pid.toFixed(3)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 flex-1 bg-rule/40">{bar(p.aci, "aci")}</div>
                  <span className="num w-14 text-right text-[11px] text-mute">
                    {p.aci === null ? "n/a" : p.aci.toFixed(3)}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-3 text-[11px] leading-relaxed text-mute">
        Worst rolling 13-week coverage on the sealed 2026 holdout. Dark is the reference
        conformal PID controller, pale is ACI on the same rows. Solid target 0.90, the
        pre-registered floor 0.70.
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
}: {
  byHorizon: Record<string, { mean: number; max: number; n: number }>;
  threshold?: number;
}) {
  const entries = Object.entries(byHorizon).sort((a, b) => Number(a[0]) - Number(b[0]));
  const scale = Math.max(threshold * 2, ...entries.map(([, v]) => v.max));

  return (
    <figure className="w-full">
      <div className="relative border-y border-rule py-6">
        <div
          className="pointer-events-none absolute inset-y-6 border-l border-dashed border-ember"
          style={{ left: `${(threshold / scale) * 100}%` }}
          aria-hidden
        />
        <ul className="space-y-4">
          {entries.map(([h, v]) => (
            <li key={h} className="grid grid-cols-[5rem_1fr] items-center gap-3">
              <span className="text-[11px] uppercase tracking-wider text-mute">
                {h} weeks
              </span>
              <div className="flex items-center gap-2">
                <div className="h-3 flex-1 bg-rule/40">
                  <div
                    className={
                      v.mean > threshold
                        ? "bar-grow h-full origin-left bg-ember"
                        : "bar-grow h-full origin-left bg-ink"
                    }
                    style={{ width: `${(v.mean / scale) * 100}%` }}
                  />
                </div>
                <span className="num w-16 text-right text-[11px] text-ink">
                  {v.mean.toFixed(4)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-3 text-[11px] leading-relaxed text-mute">
        Mean reliability term by horizon on the sealed 2026 holdout, lower is better. The
        dashed line is the 0.05 threshold set before the look. Two-week forecasts pass on
        both domains; the longer horizons are where it breaks.
      </figcaption>
    </figure>
  );
}
