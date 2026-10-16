/**
 * An app capture on a plane, with a camera that moves over it.
 *
 * Captures are 1920x1080 CSS pixels at twice the resolution (phones 390x844 at
 * three times), so the camera can push in to a sentence and stay sharp. A
 * view is the region of the capture, in its CSS pixels, that fills the box;
 * its height follows the box's shape. Keys are eased in and out.
 */
import { Img, staticFile } from "remotion";
import manifest from "../../public/captures/manifest.json";
import { clamp01, easeInOut, lerp } from "../util";
import { Cursor, type Track } from "./Cursor";

export type View = { x: number; y: number; w: number };
export type Key = { t: number; view: View };
type Shot = { file?: string; dir?: string; frames?: number; fps?: number; viewport: { width: number; height: number }; scale: number; cursor?: Track; rects?: Record<string, { x: number; y: number; w: number; h: number }>; height?: number };

export const CAPTURES = (manifest as unknown as { shots: Record<string, Shot> }).shots;

export function cap(name: string): Shot {
  const s = CAPTURES[name];
  if (!s) throw new Error(`capture "${name}" is missing: run node capture/capture.mjs`);
  return s;
}
export function rect(name: string, key: string) {
  const r = cap(name).rects?.[key];
  if (!r) throw new Error(`capture "${name}" has no rect "${key}"`);
  return r;
}
/** A view that frames a rect with a margin (fraction of its width), within a box of the given aspect. */
export function around(r: { x: number; y: number; w: number; h: number }, aspect: number, margin = 0.18): View {
  let w = r.w * (1 + 2 * margin);
  let h = w / aspect;
  if (h < r.h * (1 + 2 * margin)) { h = r.h * (1 + 2 * margin); w = h * aspect; }
  return { x: r.x + r.w / 2 - w / 2, y: r.y + r.h / 2 - h / 2, w };
}

export function viewAt(t: number, keys: Key[], aspect: number): View {
  if (t <= keys[0].t) return keys[0].view;
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i], b = keys[i + 1];
    if (t <= b.t) {
      const u = easeInOut(clamp01((t - a.t) / (b.t - a.t)));
      // Centres move linearly; the zoom moves in log space so a push-in feels even.
      const w = Math.exp(lerp(Math.log(a.view.w), Math.log(b.view.w), u));
      const cx = lerp(a.view.x + a.view.w / 2, b.view.x + b.view.w / 2, u);
      const cy = lerp(a.view.y + a.view.w / aspect / 2, b.view.y + b.view.w / aspect / 2, u);
      return { x: cx - w / 2, y: cy - w / aspect / 2, w };
    }
  }
  return keys[keys.length - 1].view;
}

export const CapturePlane: React.FC<{
  name: string;
  t: number;
  keys: Key[];
  box: { w: number; h: number };
  frameAt?: number; // for a frame sequence: the frame to show
  cursor?: { track: Track; start: number; speed?: number; until?: number };
  crossTo?: { name: string; u: number }; // dissolve to another capture of the same layout
  radius?: number;
}> = ({ name, t, keys, box, frameAt, cursor, crossTo, radius = 0 }) => {
  const s = cap(name);
  const vw = s.viewport.width;
  const vh = s.height ?? s.viewport.height;
  const view = viewAt(t, keys, box.w / box.h);
  const k = box.w / view.w;
  const src = s.dir
    ? staticFile(`captures/${s.dir}/${String(Math.max(0, Math.min((s.frames ?? 1) - 1, Math.round(frameAt ?? 0)))).padStart(4, "0")}.png`)
    : staticFile(`captures/${s.file}`);
  return (
    <div style={{ position: "absolute", width: box.w, height: box.h, overflow: "hidden", borderRadius: radius, background: "#000" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: vw, height: vh, transformOrigin: "0 0", transform: `translate(${-view.x * k}px, ${-view.y * k}px) scale(${k})` }}>
        <Img src={src} style={{ position: "absolute", width: vw, height: vh }} />
        {crossTo && crossTo.u > 0 ? (
          <Img src={staticFile(`captures/${cap(crossTo.name).file}`)} style={{ position: "absolute", width: vw, height: cap(crossTo.name).height ?? vh, opacity: crossTo.u }} />
        ) : null}
        {cursor ? <Cursor track={cursor.track} t={t} start={cursor.start} speed={cursor.speed ?? 1} until={cursor.until} scale={k} /> : null}
      </div>
    </div>
  );
};
