"use client";

import { motion, type MotionValue, useMotionValue, useScroll, useSpring, useTransform } from "motion/react";
import { ReactNode, useRef } from "react";
import { usePrefersReducedMotion, useReduceMotion, useSmooth } from "@/lib/motion";

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
 * - Letters: the wordmark assembles letter by letter on load, each rising out
 *   of a soft blur. It plays once, on mount, so it always finishes.
 * - Magnetic: a primary button leans a few pixels toward the pointer and
 *   springs back, so the one action on the screen feels within reach.
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

const TONES = { light: ["#5f655f", "#161a19"], dark: ["#8d938e", "#f3f3ee"] } as const;

function Word({ word, i, n, progress, em, tone }: { word: string; i: number; n: number; progress: MotionValue<number>; em?: boolean; tone: keyof typeof TONES }) {
  // Each word darkens across its own slice of the scroll range, with a little
  // overlap so the line reads as one movement rather than a ticker.
  const start = i / n;
  const end = Math.min(1, start + 1.6 / n);
  const color = useTransform(progress, [start, end], [...TONES[tone]]);
  // Each word also settles a hair as it darkens: position only, never hidden.
  const y = useTransform(progress, [start, end], ["0.14em", "0em"]);
  const Tag = em ? motion.em : motion.span;
  return <Tag className="inline-block" style={{ color, y }}>{word}</Tag>;
}

export function ScrollWords({ segments, tone = "light" }: { segments: Segment[]; tone?: keyof typeof TONES }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReduceMotion();
  // From the line's top at 85% down the screen to its bottom at 40%.
  const raw = useScroll({ target: ref, offset: [[0, 0.85], [1, 0.4]] }).scrollYProgress;
  const scrollYProgress = useSmooth(raw);
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
          <Word word={w} i={i} n={words.length} progress={scrollYProgress} em={em} tone={tone} />
        </span>
      ))}
    </span>
  );
}

/**
 * The wordmark, letter by letter. `em` letters are set in the display italic,
 * as in the logo (CO<em>FIRE</em>). The whole word is in the accessible name
 * once; the letters themselves are hidden from assistive technology.
 */
export function Letters({ plain, em }: { plain: string; em: string }) {
  const instant = usePrefersReducedMotion();
  const reduce = useReduceMotion();
  const letters = [...plain.split("").map((c) => ({ c, em: false })), ...em.split("").map((c) => ({ c, em: true }))];
  return (
    <span aria-label={plain + em} role="img" className="inline-block [perspective:900px]">
      {letters.map((l, i) => {
        const Tag = l.em ? motion.em : motion.span;
        return (
          <Tag
            key={i}
            aria-hidden
            className="inline-block"
            initial={reduce ? false : { y: "0.42em", rotateX: -55, filter: "blur(12px)", opacity: 0.001 }}
            animate={{ y: 0, rotateX: 0, filter: "blur(0px)", opacity: 1 }}
            transition={
              instant
                ? { duration: 0 }
                : {
                    delay: 0.1 + i * 0.065,
                    y: { type: "spring", stiffness: 140, damping: 18, mass: 0.9 },
                    rotateX: { type: "spring", stiffness: 140, damping: 18, mass: 0.9 },
                    filter: { duration: 0.7, ease: [0.16, 1, 0.3, 1] },
                    opacity: { duration: 0.5, ease: "easeOut" },
                  }
            }
            style={{ transformOrigin: "50% 100%" }}
          >
            {l.c}
          </Tag>
        );
      })}
    </span>
  );
}

/** How much further the label travels than the button, for depth. */
const LABEL_DEPTH = 0.45;

/** Leans toward the pointer (at most `pull` of the offset) and springs back on leave. */
export function Magnetic({ children, pull = 0.22 }: { children: ReactNode; pull?: number }) {
  const reduce = useReduceMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 16, mass: 0.5 });
  const sy = useSpring(y, { stiffness: 220, damping: 16, mass: 0.5 });
  // The label inside travels a little further than the button: depth.
  const ix = useTransform(sx, (v) => v * LABEL_DEPTH);
  const iy = useTransform(sy, (v) => v * LABEL_DEPTH);
  if (reduce) return <>{children}</>;
  return (
    <motion.span
      className="inline-block will-change-transform [&>*]:will-change-transform"
      style={{ x: sx, y: sy }}
      onPointerMove={(e) => {
        if (e.pointerType !== "mouse") return;
        const r = e.currentTarget.getBoundingClientRect();
        x.set((e.clientX - (r.left + r.width / 2)) * pull);
        y.set((e.clientY - (r.top + r.height / 2)) * pull);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      <motion.span className="inline-block" style={{ x: ix, y: iy }}>
        {children}
      </motion.span>
    </motion.span>
  );
}
