"use client";

/*
 * Reveals here animate POSITION only, never opacity.
 *
 * Animating from `opacity: 0` with `whileInView` means anything that does not
 * scroll the way a human does leaves the content permanently invisible: a
 * full-page screenshot, print, reader mode. On this page that silently blanked
 * two whole sections and a row of headline statistics while the DOM looked
 * correct. A reveal that can hide content will hide content.
 */

import { motion, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { ReactNode, useRef } from "react";

/**
 * Scroll behaviour for the landing sequence.
 *
 * Every effect here is motivated (skill 5): the hero recedes so the first
 * section arrives rather than merely appearing; display statements reveal by
 * line so the argument is read in order; the photograph parallaxes so the page
 * has depth at the one point where a full-bleed image earns it; and the reading
 * progress line tells you how far through the argument you are.
 *
 * All of it collapses to static under prefers-reduced-motion, and every value
 * is driven by a motion value, never by React state on a scroll listener
 * (skill 5.D).
 */

/** Thin progress line under the nav. Tells you where you are in the argument. */
export function ReadingProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 30, restDelta: 0.001 });
  const reduce = useReducedMotion();
  if (reduce) return null;
  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="fixed left-0 right-0 top-16 z-50 h-px origin-left bg-ember"
    />
  );
}

/**
 * Hero that recedes as you leave it. The next section then reads as arriving
 * over the top of it rather than simply following it.
 */
export function RecedingHero({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const opacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.94]);
  const y = useTransform(scrollYProgress, [0, 1], [0, 60]);

  return (
    <section ref={ref} className="relative flex min-h-[88dvh] items-center justify-center px-6 pt-16">
      <motion.div style={reduce ? undefined : { opacity, scale, y }} className="text-center">
        {children}
      </motion.div>
    </section>
  );
}

/**
 * Reveals a display statement line by line as it enters. The sentence lands in
 * reading order, which is the point: it is an argument, not a banner.
 */
export function LineReveal({
  lines,
  className = "",
}: {
  lines: ReactNode[];
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <p className={className}>
      {lines.map((line, i) => (
        <motion.span
          key={i}
          className="block"
          initial={reduce ? false : { y: "0.35em" }}
          whileInView={{ y: 0 }}
          viewport={{ once: true, amount: 0 }}
          transition={{ duration: 0.7, delay: i * 0.12, ease: [0.16, 1, 0.3, 1] }}
        >
          {line}
        </motion.span>
      ))}
    </p>
  );
}

/** Full-bleed image with a parallax interior, so the page has depth once. */
export function ParallaxFigure({
  src,
  alt,
  caption,
}: {
  src: string;
  alt: string;
  caption: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["-12%", "12%"]);

  return (
    <figure>
      <div ref={ref} className="relative h-[52vh] overflow-hidden md:h-[72vh]">
        <motion.img
          src={src}
          alt={alt}
          style={reduce ? undefined : { y }}
          className="absolute inset-0 h-[126%] w-full object-cover"
        />
      </div>
      <figcaption className="measure px-6 py-3 text-xs text-mute">{caption}</figcaption>
    </figure>
  );
}

/** Generic in-view reveal for supporting content. */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { y: 18 }}
      whileInView={{ y: 0 }}
      viewport={{ once: true, amount: 0 }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

/**
 * A counter that runs up to its value as it enters view. Used only on the
 * discipline figures, where the number is the content.
 */
export function CountUp({ to, suffix = "", decimals = 0 }: { to: number; suffix?: string; decimals?: number }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.9", "start 0.5"] });
  const v = useTransform(scrollYProgress, [0, 1], [0, to]);
  const text = useTransform(v, (n) => `${n.toFixed(decimals)}${suffix}`);
  if (reduce) return <span>{`${to.toFixed(decimals)}${suffix}`}</span>;
  return <motion.span ref={ref}>{text}</motion.span>;
}
