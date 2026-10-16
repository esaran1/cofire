/**
 * The synthetic cursor: a plain arrow, drawn in code, that follows the path
 * the capture script actually moved the pointer along (manifest.json), with a
 * ripple on every recorded click. It lives on the capture's plane, so it
 * moves with the camera, and is counter-scaled so it stays one size on screen.
 */
import { T } from "../theme";
import { clamp01, easeOut } from "../util";

export type Track = { t: number; x: number; y: number; click?: boolean }[];

export const Cursor: React.FC<{ track: Track; t: number; start: number; speed: number; until?: number; scale: number }> = ({ track, t, start, speed, until, scale }) => {
  if (!track.length) return null;
  const t0 = track[0].t;
  // Page time (ms) that corresponds to film time t.
  const pt = t0 + (t - start) * 1000 * speed;
  let x = track[0].x, y = track[0].y;
  if (pt >= track[track.length - 1].t) { x = track[track.length - 1].x; y = track[track.length - 1].y; }
  else if (pt > t0) {
    for (let i = 0; i < track.length - 1; i++) {
      const a = track[i], b = track[i + 1];
      if (pt <= b.t) {
        const u = b.t === a.t ? 1 : (pt - a.t) / (b.t - a.t);
        x = a.x + (b.x - a.x) * u; y = a.y + (b.y - a.y) * u;
        break;
      }
    }
  }
  const fadeIn = clamp01((t - start + 0.25) / 0.25);
  const fadeOut = until === undefined ? 1 : 1 - clamp01((t - until) / 0.3);
  const op = Math.min(fadeIn, fadeOut);
  const clicks = track.filter((p) => p.click);
  const inv = 1 / scale;
  return (
    <>
      {clicks.map((c, i) => {
        const age = (pt - c.t) / 1000 / speed; // film seconds since the click
        if (age < 0 || age > 0.7) return null;
        const u = easeOut(clamp01(age / 0.7));
        const r = (14 + 46 * u) * inv;
        return (
          <div key={i} style={{ position: "absolute", left: c.x - r, top: c.y - r, width: 2 * r, height: 2 * r, borderRadius: "50%", border: `${3 * inv}px solid ${T.emberBright}`, opacity: (1 - u) * 0.9 * op, background: `rgba(226,100,60,${0.18 * (1 - u)})` }} />
        );
      })}
      <svg width={30 * inv} height={36 * inv} viewBox="0 0 30 36" style={{ position: "absolute", left: x - 3 * inv, top: y - 2 * inv, opacity: op, filter: `drop-shadow(0 ${2 * inv}px ${4 * inv}px rgba(0,0,0,0.45))` }}>
        <path d="M3 2 L3 28 L10 21.5 L15 33 L19.5 31 L14.6 19.8 L24 19.8 Z" fill="#fff" stroke={T.ink} strokeWidth={1.6} strokeLinejoin="round" />
      </svg>
    </>
  );
};
