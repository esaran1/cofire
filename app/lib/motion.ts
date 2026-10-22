"use client";

import { useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

/**
 * Reduced motion, without a hydration mismatch.
 *
 * Motion's useReducedMotion is null on the server and the real preference on
 * the client's first render, so anything that branches the markup on it (an
 * `initial` style, a `style` of motion values) renders differently on each side
 * for a reader who has reduced motion on: React then discards the server HTML,
 * or keeps attributes that do not match.
 *
 * Two rules follow:
 * - useReduceMotion() is false until the component has mounted, on both sides,
 *   then the real preference. Use it for anything that changes the markup.
 * - usePrefersReducedMotion() is the real preference from the first client
 *   render. Use it only for transition timing, which is never in the markup, so
 *   a reader who asked for no motion gets none, not even on the first frame.
 */
export function useReduceMotion(): boolean {
  const prefers = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted && !!prefers;
}

export function usePrefersReducedMotion(): boolean {
  return !!useReducedMotion();
}
