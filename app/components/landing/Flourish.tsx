"use client";

import { motion, type MotionValue, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { useReduceMotion } from "@/lib/motion";

/**
 * Homepage-only motion, each with one job. Written here from ideas seen in the
 * Skiper UI library; no code from it is used.
 *
 * - RollText: a link or button label that rolls up and is replaced by a fresh
 *   copy on hover or keyboard focus. Feedback that the control is live.
 * - ScrollWords: a statement that darkens word by word as it scrolls through
 *   the reading zone, so the claim is read at reading pace. Words go from the
 *   muted text colour (5.4:1 on paper, readable) to ink, never from invisible,
 *   so the line is whole without JavaScript or with reduced motion.
 */

/** The label rolls on hover or focus of the nearest `group` (the link). */
export function RollText({ children }: { children: string }) {
  return (
    <span className="relative inline-flex overflow-hidden align-bottom">
      <span className="transition-transform duration-[450ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:-translate-y-full group-focus-visible:-translate-y-full">
        {children}
      </span>
      <span
        aria-hidden
        className="absolute inset-0 translate-y-full transition-transform duration-[450ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-y-0 group-focus-visible:translate-y-0"
      >
        {children}
      </span>
    </span>
  );
}

/** `join` attaches a segment to the word before it, with no space (a closing period). */
type Segment = { text: string; em?: boolean; join?: boolean };

function Word({ word, i, n, progress, em }: { word: string; i: number; n: number; progress: MotionValue<number>; em?: boolean }) {
  // Each word darkens across its own slice of the scroll range, with a little
  // overlap so the line reads as one movement rather than a ticker.
  const start = i / n;
  const end = Math.min(1, start + 1.6 / n);
  const color = useTransform(progress, [start, end], ["#5f655f", "#161a19"]);
  const Tag = em ? motion.em : motion.span;
  return <Tag style={{ color }}>{word}</Tag>;
}

export function ScrollWords({ segments }: { segments: Segment[] }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReduceMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 85%", "end 40%"] });
  const words = segments.flatMap((s) =>
    s.text
      .split(/\s+/)
      .filter(Boolean)
      .map((w, k) => ({ w, em: s.em, join: !!s.join && k === 0 })),
  );
  if (reduce) {
    return (
      <span ref={ref}>
        {segments.map((s, k) => (
          <span key={k}>
            {k > 0 && !s.join ? " " : null}
            {s.em ? <em>{s.text}</em> : s.text}
          </span>
        ))}
      </span>
    );
  }
  return (
    <span ref={ref}>
      {words.map(({ w, em, join }, i) => (
        <span key={i}>
          {i > 0 && !join ? " " : null}
          <Word word={w} i={i} n={words.length} progress={scrollYProgress} em={em} />
        </span>
      ))}
    </span>
  );
}
