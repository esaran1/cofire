"use client";

import { motion, useReducedMotion } from "motion/react";
import { ReactNode } from "react";

/**
 * Scroll-reveal wrapper for a landing act. Motion is motivated: content enters
 * in reading order so the argument arrives in sequence rather than all at once.
 * Collapses to static under prefers-reduced-motion.
 */
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
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** A full landing section. One theme, generous rhythm. */
export function Act({
  id,
  children,
  className = "",
}: {
  id: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`relative px-6 py-24 md:py-32 ${className}`}>
      <div className="mx-auto max-w-6xl">{children}</div>
    </section>
  );
}

/** Large display figure pulled from artifacts. Mono, because it is a measurement. */
export function Figure({
  value,
  label,
  tone = "paper",
}: {
  value: string;
  label: string;
  tone?: "paper" | "fire" | "drought";
}) {
  const color = tone === "fire" ? "text-fire" : tone === "drought" ? "text-drought" : "text-paper";
  return (
    <div>
      <div className={`font-mono text-4xl md:text-5xl tracking-tight ${color}`}>{value}</div>
      <div className="mt-2 text-sm text-mute leading-snug max-w-[28ch]">{label}</div>
    </div>
  );
}
