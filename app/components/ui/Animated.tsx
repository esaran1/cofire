"use client";

import { animate, motion, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useReduceMotion } from "@/lib/motion";

/**
 * The controls that animate with the Motion library: the segmented picker's
 * sliding pill and the count-up numeral. Kept apart from ./Controls so pages
 * that do not use them never download the library.
 */

/**
 * Segmented picker. A real control, not a styled <select>.
 *
 * The selected option is ink, as every selection in the app is. The options
 * share the row and shrink rather than wrap, so on a phone the group stays one
 * pill instead of breaking into a two-line blob.
 */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; hint?: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  const reduce = useReduceMotion();
  return (
    <fieldset>
      <legend className="text-sm font-medium text-ink">{label}</legend>
      <div
        role="radiogroup"
        aria-label={label}
        className="mt-2 flex gap-0.5 rounded-full border border-rule bg-paper-raised p-1 sm:gap-1"
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
              className={`relative min-w-0 flex-1 rounded-full px-1.5 py-2 text-[13px] transition-transform active:scale-[0.97] sm:px-3 sm:text-sm ${
                active ? "text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {active && (
                <motion.span
                  layoutId={`seg-${label}`}
                  className="absolute inset-0 rounded-full bg-ink"
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <span className="relative z-10 block font-medium leading-tight">{o.label}</span>
              {o.hint && (
                <span className="relative z-10 mt-0.5 block text-[10px] leading-tight opacity-80 sm:text-[11px]">{o.hint}</span>
              )}
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
  // The real number is what the server renders and what a reader without
  // JavaScript (or with reduced motion) sees. Only once it scrolls into view
  // does it count up from zero.
  const reduce = useReduceMotion();
  const [shown, setShown] = useState(to);
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
