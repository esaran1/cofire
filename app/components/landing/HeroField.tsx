"use client";

import { useRef } from "react";
import { useReduceMotion } from "@/lib/motion";
import { colour } from "@/components/landing/StoryMap";
import story from "@/lib/story.json";

/**
 * The forecast itself, faint, behind the wordmark.
 *
 * Every square is a real 4 km cell from the latest issue (app/lib/story.json).
 * At rest the grid is a quiet spruce silhouette of where COFIRE forecasts; a
 * soft light under the pointer shows the cells near it in their real colours,
 * exactly as the map below colours them at two weeks out. It is decoration
 * here (aria-hidden; the map further down is the readable one), so it may
 * arrive: the cells wave in once from the north-west. Under reduced motion it
 * is the still silhouette.
 *
 * Written from ideas seen in the Skiper UI library (grid reveal, pointer
 * spotlight); no code from it is used.
 */
export function HeroField() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReduceMotion();
  const m = story.map;
  const [vx, vy, vw, vh] = m.view;
  const [cw, ch] = m.cell;
  // The wave: each cell starts by its distance from the top-left of the grid.
  const delay = (x: number, y: number) => ((x - vx) / vw) * 0.9 + ((y - vy) / vh) * 0.6;
  const field = (className: string, animate: boolean, real: boolean) => (
    <svg viewBox={`${vx} ${vy} ${vw} ${vh}`} preserveAspectRatio="xMidYMid slice" className={className}>
      {m.cells.map((c, i) => (
        <rect
          key={i}
          x={c.x - cw / 2}
          y={c.y - ch / 2}
          width={cw * 0.86}
          height={ch * 0.86}
          rx={0.4}
          fill={real ? colour(c.v[0]) : "#245e50"}
          className={animate ? "field-cell" : undefined}
          style={animate ? { animationDelay: `${delay(c.x, c.y).toFixed(2)}s` } : undefined}
        />
      ))}
    </svg>
  );
  return (
    // The pointer position (--fx, --fy) is set by the hero section, which
    // sits above this layer and receives the pointer.
    <div ref={ref} aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* The resting field: faint, fading out toward the edges of the hero. */}
      {field("absolute inset-0 h-full w-full opacity-[0.1] [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_75%)]", !reduce, false)}
      {/* The same field at full strength, seen only through the pointer's light. */}
      {reduce ? null : field("hero-field-lit absolute inset-0 h-full w-full", false, true)}
    </div>
  );
}
