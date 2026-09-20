"use client";

import { motion, useReducedMotion } from "motion/react";

/**
 * The calibration result, drawn from real measured coverage.
 *
 * This is not decoration and not a hand-rolled illustration: it is the actual
 * finding rendered as a chart, which is what the section is about. Values come
 * from facts.json, generated from artifacts.
 *
 * Reading it: each bar is one pool variant's measured coverage on LODO folds.
 * The dashed line is the 0.90 target none of them reach.
 */
export function CoverageFigure({
  variants,
  target = 0.9,
}: {
  variants: { label: string; mean: number }[];
  target?: number;
}) {
  const reduce = useReducedMotion();
  const max = 1;
  const rows = variants.slice(0, 6);

  return (
    <figure className="w-full">
      <div className="relative border-y border-rule py-6">
        {/* Target line, the thing nothing reaches. */}
        <div
          className="pointer-events-none absolute inset-y-6 border-l border-dashed border-ember/50"
          style={{ left: `${(target / max) * 100}%` }}
          aria-hidden
        >
          {/* Anchored right of the line so it cannot push past a narrow
              viewport. */}
          <span className="absolute -top-5 right-1 whitespace-nowrap text-[11px] text-ember">
            target 0.90
          </span>
        </div>

        <ul className="space-y-3">
          {rows.map((v, i) => (
            <li key={v.label} className="grid grid-cols-[5.5rem_1fr_3rem] items-center gap-3">
              <span className="num text-xs text-mute">{v.label}</span>
              <span className="relative h-2.5 bg-paper-sunk">
                {/* Width is set on the element itself, so the bar is correct
                    with JS disabled or if the viewport callback never fires.
                    Motion only scales it in. */}
                <motion.span
                  className="absolute inset-y-0 left-0 origin-left bg-slate"
                  style={{ width: `${(v.mean / max) * 100}%` }}
                  initial={reduce ? false : { scaleX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true, amount: 0.2 }}
                  transition={{ duration: 0.7, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                />
              </span>
              <span className="num text-xs text-ink-soft">{v.mean.toFixed(3)}</span>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="mt-3 text-xs leading-relaxed text-mute">
        Measured coverage of each pre-registered calibration pool on leave-one-year-out folds,
        4-week ERC percentile. Every variant was rejected against a bar fixed before the run.
      </figcaption>
    </figure>
  );
}

/**
 * Residual inflation by year: the diagnostic that explains the null result.
 * Training years sit low, held-out years sit ~2.4x higher, uniformly.
 */
export function InflationFigure({
  series,
}: {
  series: { year: number; p90: number; heldOut: boolean }[];
}) {
  const reduce = useReducedMotion();
  const max = Math.max(...series.map((s) => s.p90)) * 1.1;

  return (
    <figure className="w-full">
      {/* Grid rather than flex: a percentage height needs a definite parent
          height on each column, which `flex-1` alone does not give. */}
      <div className="grid h-44 items-end gap-2 border-b border-rule" style={{ gridTemplateColumns: `repeat(${series.length}, minmax(0, 1fr))` }}>
        {series.map((s, i) => (
          <div key={s.year} className="flex h-full flex-col justify-end gap-2">
            <span className={`num text-center text-[11px] ${s.heldOut ? "text-ember" : "text-mute"}`}>
              {s.p90.toFixed(0)}
            </span>
            <motion.div
              className={`w-full origin-bottom ${s.heldOut ? "bg-ember" : "bg-rule"}`}
              style={{ height: `${(s.p90 / max) * 100}%` }}
              initial={reduce ? false : { scaleY: 0 }}
              whileInView={{ scaleY: 1 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ duration: 0.6, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        ))}
      </div>
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${series.length}, minmax(0, 1fr))` }}>
        {series.map((s) => (
          <span key={s.year} className="num pt-2 text-center text-[11px] text-mute">
            {String(s.year).slice(2)}
          </span>
        ))}
      </div>
      <figcaption className="mt-3 text-xs leading-relaxed text-mute">
        90th-percentile forecast error by year, in ERC points. Grey years were in training. Red years
        were held out, and every one of them carries the same inflation.
      </figcaption>
    </figure>
  );
}
