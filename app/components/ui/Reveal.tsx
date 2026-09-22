"use client";

import { ReactNode } from "react";

/**
 * Section wrapper with a scroll-reveal that cannot hide its own content.
 *
 * Three JS-driven versions of this were tried and all three failed the same
 * way: `whileInView`, `whileInView` with `amount: 0`, and `useInView` with a
 * ref each left sections below the fold stranded at zero opacity in any
 * renderer that does not scroll like a human. A full-page screenshot showed a
 * finished-looking page with three of five sections missing.
 *
 * The lesson is that visibility should never depend on JavaScript observing a
 * scroll. This version uses a CSS scroll-driven animation where supported and
 * degrades to plain visible content everywhere else, including print, reader
 * mode, screenshots, and browsers without `animation-timeline`. The content is
 * opaque by default; the animation only ever animates it *from* transparent,
 * and if the animation never runs the element is simply visible.
 */
export function Reveal({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`reveal ${className}`}>{children}</div>;
}
