"use client";

import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { useEffect, useRef } from "react";
import { useReduceMotion } from "@/lib/motion";
import { colour } from "@/components/landing/StoryMap";
import story from "@/lib/story.json";

/**
 * The forecast itself, faint, behind the wordmark.
 *
 * Every square is a real 4 km cell from the latest issue (app/lib/story.json).
 * At rest the grid is a quiet spruce silhouette of where COFIRE forecasts; a
 * lens of light that follows the pointer shows the cells under it in their
 * real colours, exactly as the map below colours them at two weeks out. It is
 * decoration here (aria-hidden; the map further down is the readable one), so
 * it may arrive: the cells grow in once, in a wave from the north-west.
 *
 * Built for smoothness: both layers are canvases drawn once (the wave is one
 * animation-frame loop that stops when it lands, about 1.6 s), and the lens
 * moves by transform alone, behind a spring, so following the pointer never
 * repaints anything. Under reduced motion it is the still silhouette, no lens.
 *
 * Written from ideas seen in the Skiper UI library (grid reveal, pointer
 * spotlight); no code from it is used.
 */
const LENS = 300; // lens diameter, CSS px
const SPRUCE = "#245e50";

type Fit = { s: number; ox: number; oy: number };

function fitView(W: number, H: number): Fit {
  // "slice": cover the box, centred, like preserveAspectRatio="xMidYMid slice".
  const [vx, vy, vw, vh] = story.map.view;
  const s = Math.max(W / vw, H / vh);
  return { s, ox: (W - vw * s) / 2 - vx * s, oy: (H - vh * s) / 2 - vy * s };
}

/** Draws the cells; `grow(i)` in 0..1 sizes each one (1 = full). */
function draw(ctx: CanvasRenderingContext2D, W: number, H: number, real: boolean, grow: (i: number) => number) {
  const m = story.map;
  const [cw, ch] = m.cell;
  const f = fitView(W, H);
  ctx.clearRect(0, 0, W, H);
  if (!real) ctx.fillStyle = SPRUCE;
  for (let i = 0; i < m.cells.length; i++) {
    const g = grow(i);
    if (g <= 0) continue;
    const c = m.cells[i];
    const w = cw * 0.84 * f.s * g, h = ch * 0.84 * f.s * g;
    const x = c.x * f.s + f.ox - w / 2, y = c.y * f.s + f.oy - h / 2;
    if (real) ctx.fillStyle = colour(c.v[0]);
    ctx.globalAlpha = Math.min(1, g * 1.4);
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, Math.min(3, w * 0.12));
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

const easeOutExpo = (u: number) => (u >= 1 ? 1 : 1 - Math.pow(2, -10 * u));

export function HeroField() {
  const box = useRef<HTMLDivElement>(null);
  const base = useRef<HTMLCanvasElement>(null);
  const lit = useRef<HTMLCanvasElement>(null);
  const reduce = useReduceMotion();
  // The lens: the raw pointer, and a spring behind it for the glide.
  const px = useMotionValue(-LENS), py = useMotionValue(-LENS);
  const sx = useSpring(px, { stiffness: 170, damping: 24, mass: 0.6 });
  const sy = useSpring(py, { stiffness: 170, damping: 24, mass: 0.6 });
  const shown = useSpring(0, { stiffness: 120, damping: 22 });
  const lensX = useTransform(sx, (v) => v - LENS / 2);
  const lensY = useTransform(sy, (v) => v - LENS / 2);
  const innerX = useTransform(sx, (v) => LENS / 2 - v);
  const innerY = useTransform(sy, (v) => LENS / 2 - v);
  const lensScale = useTransform(shown, [0, 1], [0.6, 1]);

  useEffect(() => {
    const el = box.current, b = base.current, l = lit.current;
    if (!el || !b) return;
    let raf = 0;
    let t0 = 0;
    const m = story.map;
    const [vx, vy, vw, vh] = m.view;
    // Each cell's start in the wave, from the north-west corner, 0..1.
    const order = m.cells.map((c) => ((c.x - vx) / vw) * 0.62 + ((c.y - vy) / vh) * 0.38);
    const size = () => {
      const r = el.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      for (const c of [b, l]) {
        if (!c) continue;
        c.width = Math.round(r.width * dpr);
        c.height = Math.round(r.height * dpr);
        c.style.width = `${r.width}px`;
        c.style.height = `${r.height}px`;
        c.getContext("2d")!.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      return r;
    };
    const paint = (u: number) => {
      const r = el.getBoundingClientRect();
      // Wave: 1.0 s of stagger across the grid, 0.7 s for each cell to grow.
      draw(b.getContext("2d")!, r.width, r.height, false, (i) => easeOutExpo(Math.max(0, Math.min(1, (u * 1.7 - order[i]) / 0.7))));
    };
    const all = () => {
      const r = size();
      if (l) draw(l.getContext("2d")!, r.width, r.height, true, () => 1);
    };
    all();
    if (reduce) {
      paint(1);
    } else {
      const step = (now: number) => {
        if (!t0) t0 = now;
        const u = (now - t0) / 1000 / 1.6;
        paint(Math.min(1, u));
        if (u < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }
    const ro = new ResizeObserver(() => {
      all();
      paint(1);
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [reduce]);

  // The hero section above this layer receives the pointer and forwards it.
  useEffect(() => {
    if (reduce) return;
    const el = box.current;
    const section = el?.closest("section");
    if (!el || !section || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      if (shown.get() < 0.02) {
        // Arrive where the pointer is, not glide in from the corner.
        sx.jump(e.clientX - r.left);
        sy.jump(e.clientY - r.top);
      }
      px.set(e.clientX - r.left);
      py.set(e.clientY - r.top);
      shown.set(1);
    };
    const leave = () => shown.set(0);
    section.addEventListener("pointermove", move);
    section.addEventListener("pointerleave", leave);
    return () => {
      section.removeEventListener("pointermove", move);
      section.removeEventListener("pointerleave", leave);
    };
  }, [reduce, px, py, sx, sy, shown]);

  return (
    <div ref={box} aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <canvas
        ref={base}
        className="absolute inset-0 opacity-[0.11] [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_78%)]"
      />
      {reduce ? null : (
        <motion.div
          className="absolute left-0 top-0 overflow-hidden rounded-full [mask-image:radial-gradient(circle,black_30%,transparent_70%)] will-change-transform"
          style={{ width: LENS, height: LENS, x: lensX, y: lensY, opacity: shown, scale: lensScale }}
        >
          <motion.canvas ref={lit} className="absolute left-0 top-0 will-change-transform" style={{ x: innerX, y: innerY }} />
        </motion.div>
      )}
    </div>
  );
}
