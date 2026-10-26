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

import { motion, useScroll, useSpring, useTransform } from "motion/react";
import { usePrefersReducedMotion, useReduceMotion, useSmooth } from "@/lib/motion";
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
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
  if (reduce) return null;
  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="fixed left-0 right-0 top-16 z-50 h-px origin-left bg-spruce"
    />
  );
}

/**
 * Hero that recedes as you leave it. The next section then reads as arriving
 * over the top of it rather than simply following it.
 */
export function RecedingHero({ children, backdrop }: { children: ReactNode; backdrop?: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReduceMotion();
  const raw = useScroll({ target: ref, offset: ["start start", "end start"] }).scrollYProgress;
  const scrollYProgress = useSmooth(raw);
  const opacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.92]);
  const y = useTransform(scrollYProgress, [0, 1], [0, 90]);
  const blur = useTransform(scrollYProgress, [0.15, 0.8], ["blur(0px)", "blur(6px)"]);
  // The backdrop moves the other way: it grows and drifts up as the title
  // recedes, so the page opens into the map rather than sliding past it.
  const backScale = useTransform(scrollYProgress, [0, 1], [1, 1.18]);
  const backY = useTransform(scrollYProgress, [0, 1], [0, -70]);

  return (
    <section
      ref={ref}
      className="relative flex min-h-[88dvh] items-center justify-center overflow-hidden px-6 pt-16"
    >
      {backdrop ? (
        <motion.div className="absolute inset-0 will-change-transform" style={reduce ? undefined : { scale: backScale, y: backY }}>
          {backdrop}
        </motion.div>
      ) : null}
      <motion.div style={reduce ? undefined : { opacity, scale, y, filter: blur }} className="relative text-center will-change-transform">
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
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
  return (
    <p className={className}>
      {lines.map((line, i) => (
        <motion.span
          key={i}
          className="block"
          initial={reduce ? false : { y: "0.35em" }}
          whileInView={{ y: 0 }}
          viewport={{ once: true, amount: 0 }}
          transition={instant ? { duration: 0 } : { duration: 0.7, delay: i * 0.12, ease: [0.16, 1, 0.3, 1] }}
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
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
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
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { y: 18 }}
      whileInView={{ y: 0 }}
      viewport={{ once: true, amount: 0 }}
      transition={instant ? { duration: 0 } : { duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
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
  const reduce = useReduceMotion();
  const instant = usePrefersReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.9", "start 0.5"] });
  const v = useTransform(scrollYProgress, [0, 1], [0, to]);
  const text = useTransform(v, (n) => `${n.toFixed(decimals)}${suffix}`);
  if (reduce) return <span>{`${to.toFixed(decimals)}${suffix}`}</span>;
  return <motion.span ref={ref}>{text}</motion.span>;
}

/**
 * Settles into place as it arrives: from slightly smaller, with softer corners,
 * to full size. Scale only, so the content is whole at every scroll position
 * (a screenshot or print shows it at nearly full size). Used on the two
 * pictures of the product, the map and the card.
 */
export function ZoomIn({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReduceMotion();
  const raw = useScroll({ target: ref, offset: ["start end", "start 0.3"] }).scrollYProgress;
  const p = useSmooth(raw);
  const scale = useTransform(p, [0, 1], [0.88, 1]);
  const y = useTransform(p, [0, 1], [60, 0]);
  return (
    <motion.div ref={ref} className={`will-change-transform ${className}`} style={reduce ? undefined : { scale, y, transformOrigin: "50% 30%" }}>
      {children}
    </motion.div>
  );
}
