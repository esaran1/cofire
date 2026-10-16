import { useCurrentFrame, useVideoConfig } from "remotion";

/** Seconds since the start of the enclosing Sequence. Everything is timed in seconds, so any frame rate renders the same film. */
export function useT(): number {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
}

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const easeInOut = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2);
export const easeOut = (u: number) => 1 - (1 - u) ** 3;
export const easeIn = (u: number) => u * u * u;
export const lerp = (a: number, b: number, u: number) => a + (b - a) * u;

/** 0 before t0, 1 after t1, eased in between. */
export function ramp(t: number, t0: number, t1: number, ease: (u: number) => number = easeInOut): number {
  if (t1 <= t0) return t >= t1 ? 1 : 0;
  return ease(clamp01((t - t0) / (t1 - t0)));
}

/** Opacity for an element that fades in at t0 and out at t1. */
export function inOut(t: number, t0: number, t1: number, fade = 0.35): number {
  return Math.min(ramp(t, t0, t0 + fade, easeOut), 1 - ramp(t, t1 - fade, t1, easeIn));
}

/** Interpolate keyframes [{t, ...numbers}] with easing between neighbours. */
export function keyed<K extends string>(t: number, keys: ({ t: number } & Record<K, number>)[], names: K[]): Record<K, number> {
  if (t <= keys[0].t) return pick(keys[0], names);
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i], b = keys[i + 1];
    if (t <= b.t) {
      const u = easeInOut(clamp01((t - a.t) / (b.t - a.t)));
      const out = {} as Record<K, number>;
      for (const n of names) out[n] = lerp(a[n], b[n], u);
      return out;
    }
  }
  return pick(keys[keys.length - 1], names);
}
function pick<K extends string>(k: Record<K, number>, names: K[]): Record<K, number> {
  const o = {} as Record<K, number>;
  for (const n of names) o[n] = k[n];
  return o;
}
