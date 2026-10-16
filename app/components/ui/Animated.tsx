"use client";

import { animate, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

/**
 * The controls that animate with the Motion library: the segmented picker's
 * sliding pill and the count-up numeral. Kept apart from ./Controls so pages
 * that do not use them never download the library.
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
              {o.hint && <span className="relative z-10 block text-[11px] leading-tight opacity-90">{o.hint}</span>}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * A number that counts up when it scrolls into view.
 *
 * Motivated, not decorative: it draws the eye to the headline verdict of a
 * section before the reader starts scanning detail. Collapses to the final
 * value instantly under reduced motion.
 */
export function CountUp({
  to,
  decimals = 0,
  suffix = "",
}: {
  to: number;
  decimals?: number;
  suffix?: string;
}) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? to : 0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });

  useEffect(() => {
    if (reduce || !inView) return;
    const controls = animate(0, to, {
      duration: 0.9,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setShown(v),
    });
    return () => controls.stop();
  }, [inView, to, reduce]);

  return (
    <span ref={ref} className="num">
      {shown.toFixed(decimals)}
      {suffix}
    </span>
  );
}
