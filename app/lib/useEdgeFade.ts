"use client";

import { type RefObject, useEffect } from "react";

/**
 * Fades the top and bottom edges of a scrolling area while there is more to
 * scroll in that direction (`.edge-fade` in globals.css).
 *
 * The map's side panel holds about three screens of content in one, and a
 * clean bottom edge gave no hint that the forecast odds, the watersheds and the
 * actions were below. The fade says "more" and goes away at the end.
 *
 * The element's own scroll and resize events, read once per frame, set two
 * data attributes; React never re-renders for it.
 */
export function useEdgeFade(ref: RefObject<HTMLElement | null>, watch?: unknown): void {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const top = el.scrollTop > 4;
      const bottom = el.scrollTop + el.clientHeight < el.scrollHeight - 4;
      if (top) el.setAttribute("data-fade-top", "");
      else el.removeAttribute("data-fade-top");
      if (bottom) el.setAttribute("data-fade-bottom", "");
      else el.removeAttribute("data-fade-bottom");
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    el.addEventListener("scroll", schedule, { passive: true });
    const ro = new ResizeObserver(schedule);
    ro.observe(el);
    // Content grows as the forecast loads and disclosures open.
    const mo = new MutationObserver(schedule);
    mo.observe(el, { childList: true, subtree: true });
    return () => {
      el.removeEventListener("scroll", schedule);
      ro.disconnect();
      mo.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [ref, watch]);
}
