/**
 * The tap motif: a drop followed backward from a Denver tap to the watershed
 * it came from (cold open), and forward again at the close. One camera move
 * each way, never cut, on the app's own map and palette (MapLibre with the
 * app's self-hosted basemap, as in scenes/MapAct.tsx).
 *
 * The route is drawn schematically: the Denver garden cell the demo uses,
 * Strontia Springs Reservoir, the east end of the Roberts Tunnel (the Upper
 * South Platte cell nearest Dillon), Dillon Reservoir. The watershed cells
 * take the latest published Drought Monitor week, spreading out from Dillon.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { AbsoluteFill, continueRender, delayRender } from "remotion";
import * as maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import { DATA } from "../data";
import { fit, mx, my, project, type Cam } from "../mercator";
import { BOX, cameras, HALF, proto, RES, SITE, style } from "../scenes/MapAct";
import { DROUGHT, FONT, T } from "../theme";
import { field } from "../trace";
import { clamp01, easeInOut, easeOut, inOut, lerp, ramp } from "../util";
import { Label, SourceLine } from "../components/Type";

export type TLine = { id: string; start: number; end: number; len: number };
export type TBeat = { id: string; start: number; end: number; dir?: "back" | "forward" };

const SPRUCE = "#245e50";
const SPRUCE_LIGHT = "#8cc2b2";
const D = DATA.drought;
const LAST = D.issues.length - 1;
const TAP = { lon: -104.975, lat: 39.7333 }; // the demo's garden cell (39.7333_-104.9750)
const ROUTE = [TAP, RES.strontia, RES.tunnel_end, RES.dillon];
const ZCITY = 12.1;

const unmy = (y: number) => (360 / Math.PI) * Math.atan(Math.exp((0.5 - y) * 2 * Math.PI)) - 90;

/** A point a fraction s along a polyline, measured in Mercator space. */
function along(pts: { lon: number; lat: number }[], s: number) {
  const xy = pts.map((p) => [mx(p.lon), my(p.lat)]);
  const seg = xy.slice(1).map((q, i) => Math.hypot(q[0] - xy[i][0], q[1] - xy[i][1]));
  const total = seg.reduce((a, b) => a + b, 0);
  let d = clamp01(s) * total;
  for (let i = 0; i < seg.length; i++) {
    if (d <= seg[i] || i === seg.length - 1) {
      const u = seg[i] ? Math.min(1, d / seg[i]) : 0;
      const x = lerp(xy[i][0], xy[i + 1][0], u), y = lerp(xy[i][1], xy[i + 1][1], u);
      return { lon: x * 360 - 180, lat: unmy(y), seg: i };
    }
    d -= seg[i];
  }
  return { ...pts[pts.length - 1], seg: seg.length - 1 };
}
/** The fraction of the route at which it reaches vertex i. */
function vertexAt(pts: { lon: number; lat: number }[], i: number) {
  const xy = pts.map((p) => [mx(p.lon), my(p.lat)]);
  const seg = xy.slice(1).map((q, k) => Math.hypot(q[0] - xy[k][0], q[1] - xy[k][1]));
  const total = seg.reduce((a, b) => a + b, 0);
  return seg.slice(0, i).reduce((a, b) => a + b, 0) / total;
}
const blend = (a: Cam, b: { lon: number; lat: number; zoom?: number }, u: number): Cam => {
  const x = lerp(mx(a.lon), mx(b.lon), u), y = lerp(my(a.lat), my(b.lat), u);
  return { lon: x * 360 - 180, lat: unmy(y), zoom: a.zoom };
};

// Watershed cells, ordered by distance from Dillon Reservoir, for the spread.
const WS = new Set(["dillon", "upper_south_platte"]);
function cellsGeojson(): GeoJSON.FeatureCollection {
  const row = D.cat[LAST];
  const dist = D.cells.map(([, lat, lon]) => Math.hypot(lon - RES.dillon.lon, (lat - RES.dillon.lat) * 1.3));
  const ws = D.cells.map(([d], i) => (WS.has(d) ? dist[i] : -1)).filter((x) => x >= 0);
  const max = Math.max(...ws);
  return {
    type: "FeatureCollection",
    features: D.cells.map(([d, lat, lon], i) => ({
      type: "Feature",
      properties: { d, c: row[i] === "x" ? 0 : Number(row[i]), o: WS.has(d) ? dist[i] / max : 2 },
      geometry: { type: "Polygon", coordinates: [[[lon - HALF, lat - HALF], [lon + HALF, lat - HALF], [lon + HALF, lat + HALF], [lon - HALF, lat + HALF], [lon - HALF, lat - HALF]]] },
    })),
  };
}

type State = { cam: Cam; reveal: number; ws: number; others: number; breathe: number };

type Times = Record<string, number>;

/** Cold open: hold on the tap, follow the drop back to Dillon, then pull back for the numbers. */
function backState(t: number, k: Times, W: number, H: number): State {
  const c = cameras(W, H);
  const end = fit(BOX.dillon, W, H, [170, 260, 170, 260]);
  const tapCam: Cam = { ...TAP, zoom: ZCITY + 0.12 * ramp(t, k.mapIn, k.m0, (u) => u) };
  let cam: Cam;
  if (t <= k.m0) cam = tapCam;
  else if (t <= k.m1) {
    const p = easeInOut(clamp01((t - k.m0) / (k.m1 - k.m0)));
    const pt = along(ROUTE, p);
    cam = blend({ ...pt, zoom: 0 }, end, ramp(p, 0.72, 1));
    cam.zoom = lerp(ZCITY + 0.12, end.zoom, p) - 0.9 * Math.sin(Math.PI * p);
  } else if (t <= k.n0) cam = { ...end, zoom: end.zoom + 0.14 * ramp(t, k.m1, k.n0, (u) => u) };
  else {
    const u = easeInOut(clamp01((t - k.n0) / (k.n1 - k.n0)));
    const a = { ...end, zoom: end.zoom + 0.14 };
    const b = { ...c.three, zoom: c.three.zoom + 0.1 };
    cam = blend(a, b, u);
    cam.zoom = lerp(a.zoom, b.zoom, u);
  }
  return { cam, reveal: lerp(-0.05, 1.05, ramp(t, k.reveal, k.reveal + 1.7, (u) => u)), ws: 0.62 * ramp(t, k.m1 - 1.6, k.m1 - 0.2), others: 0, breathe: 0 };
}

/** Close: the whole Front Range breathing, then the drop forward from Dillon to the tap. */
function forwardState(t: number, k: Times, W: number, H: number): State {
  const c = cameras(W, H);
  const start = { ...c.all, zoom: c.all.zoom + 0.05 };
  const route = [{ lon: start.lon, lat: start.lat }, ...[...ROUTE].reverse()];
  let cam: Cam;
  if (t <= k.f0) cam = { ...start, zoom: start.zoom + 0.16 * ramp(t, k.s, k.f0, (u) => u) };
  else {
    const p = easeInOut(clamp01((t - k.f0) / (k.f1 - k.f0)));
    const pt = along(route, p);
    const z0 = start.zoom + 0.16;
    cam = { lon: pt.lon, lat: pt.lat, zoom: lerp(z0, ZCITY, easeInOut(p)) + 0.5 * Math.sin(Math.PI * p) * ramp(p, 0, 0.3) };
    if (t > k.f1) cam.zoom = ZCITY + 0.1 * ramp(t, k.f1, k.f1 + 2, (u) => u);
  }
  const fade = 1 - ramp(t, k.f0 + 0.4, k.f1 - 0.6);
  return { cam, reveal: 3, ws: 0.72, others: 0.72 * fade, breathe: Math.sin(t * 2.2) * 0.06 * fade };
}

function times(dir: "back" | "forward", b: TBeat, L: (id: string) => TLine | undefined): Times {
  if (dir === "back") {
    const tap1 = L("tap1"), tap2 = L("tap2"), tap3 = L("tap3"), n1 = L("num1"), n4 = L("num4");
    const hit = (tap1?.start ?? b.start + 1.5) - 0.3;
    return {
      s: b.start,
      form: b.start + 0.15,
      hit,
      mapIn: hit + 0.1,
      m0: (tap2?.start ?? hit + 2) - 0.7,
      m1: (tap3?.start ?? hit + 8) - 0.2,
      reveal: (tap3?.start ?? hit + 8) + 0.05,
      n0: n1?.start ?? b.end - 12,
      // The pull-back runs to the cut, so the open never sits still.
      n1: Math.max(n4?.end ?? b.end, b.end),
      e: b.end,
    };
  }
  const c2 = L("close2"), c3 = L("close3");
  return { s: b.start, f0: (c2?.start ?? b.end - 6) - 0.6, f1: (c3?.end ?? b.end) - 0.1, e: b.end };
}

export const Trace: React.FC<{ b: TBeat; t: number; W: number; H: number; L: (id: string) => TLine | undefined }> = ({ b, t, W, H, L }) => {
  const dir = b.dir ?? "back";
  const k = useMemo(() => times(dir, b, L), [dir, b, L]);
  const s = useMemo(() => (dir === "back" ? backState(t, k, W, H) : forwardState(t, k, W, H)), [dir, t, k, W, H]);
  const ref = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const latest = useRef(s);
  latest.current = s;
  const done = useRef("");
  const [ready, setReady] = useState(false);
  const [initHandle] = useState(() => delayRender("trace map: style and tiles", { timeoutInMilliseconds: 180000 }));

  useEffect(() => {
    if (!proto.added) { maplibregl.addProtocol("pmtiles", new Protocol().tile); proto.added = true; }
    maplibregl.setWorkerUrl(`${SITE}/maplibre/maplibre-gl-worker.mjs`);
    const st = latest.current;
    const m = new maplibregl.Map({ container: ref.current as HTMLDivElement, style: style(), interactive: false, attributionControl: false, fadeDuration: 0, pixelRatio: 1, center: [st.cam.lon, st.cam.lat], zoom: st.cam.zoom });
    m.on("error", (e) => { throw new Error(`map error: ${e.error?.message ?? e}`); });
    m.on("load", () => {
      m.addSource("cells", { type: "geojson", data: cellsGeojson() });
      const before = "places";
      m.addLayer({ id: "cells-fill", type: "fill", source: "cells", paint: { "fill-color": SPRUCE, "fill-opacity": 0, "fill-antialias": false } }, before);
      m.addLayer({ id: "cells-line", type: "line", source: "cells", paint: { "line-color": T.ink, "line-opacity": 0, "line-width": 0.6 } }, before);
      map.current = m;
      paint(m, latest.current);
      m.once("idle", () => { setReady(true); continueRender(initHandle); });
    });
    return () => m.remove();
  }, [initHandle]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const key = t.toFixed(4);
    if (done.current === key) return;
    done.current = key;
    const h = delayRender(`trace frame ${key}`, { timeoutInMilliseconds: 180000 });
    paint(m, s);
    m.once("idle", () => continueRender(h));
    m.triggerRepaint();
  }, [ready, t, s]);

  const P = (lon: number, lat: number) => project(lon, lat, s.cam, W, H);
  return (
    <AbsoluteFill style={{ background: T.ink }}>
      <div ref={ref} style={{ position: "absolute", inset: 0, width: W, height: H }} />
      {dir === "back" ? <BackOverlay t={t} k={k} P={P} W={W} H={H} L={L} /> : <ForwardOverlay t={t} k={k} P={P} W={W} H={H} startCam={cameras(W, H).all} />}
      <div style={{ position: "absolute", right: 22, bottom: 16, fontFamily: FONT.sans, fontSize: 18, color: "rgba(244,242,236,0.6)", opacity: dir === "back" ? ramp(t, k.mapIn, k.mapIn + 0.6) : 1 }}>© OpenStreetMap contributors · © Protomaps</div>
    </AbsoluteFill>
  );
};

function paint(m: maplibregl.Map, s: State) {
  m.jumpTo({ center: [s.cam.lon, s.cam.lat], zoom: s.cam.zoom });
  const cat = ["match", ["get", "c"], 1, DROUGHT[1], 2, DROUGHT[2], 3, DROUGHT[3], 4, DROUGHT[4], SPRUCE];
  m.setPaintProperty("cells-fill", "fill-color", ["case", ["<", ["get", "o"], s.reveal], cat, SPRUCE] as never);
  const ws = s.ws + s.breathe;
  m.setPaintProperty("cells-fill", "fill-opacity", ["match", ["get", "d"], "dillon", ws, "upper_south_platte", ws, s.others + s.breathe * (s.others > 0 ? 1 : 0)] as never);
  m.setPaintProperty("cells-line", "line-opacity", ["match", ["get", "d"], "dillon", 0.25 * (s.ws > 0 ? 1 : 0), "upper_south_platte", 0.25 * (s.ws > 0 ? 1 : 0), 0.25 * (s.others > 0 ? 1 : 0)] as never);
}

// ---------------------------------------------------------------------------
type PFn = (lon: number, lat: number) => { x: number; y: number };

/** The drop: forms, falls, and becomes the point of light the camera follows. */
const Drop: React.FC<{ x: number; y: number; size: number; op: number; stretch?: number }> = ({ x, y, size, op, stretch = 1 }) => (
  <svg width={size * 2} height={size * 3} viewBox="-20 -34 40 54" style={{ position: "absolute", left: x - size, top: y - size * 2.2, opacity: op, overflow: "visible", transform: `scaleY(${stretch})`, transformOrigin: "50% 80%" }}>
    <defs>
      <radialGradient id="dropg" cx="35%" cy="62%" r="70%">
        <stop offset="0%" stopColor="#f4f2ec" />
        <stop offset="55%" stopColor={SPRUCE_LIGHT} />
        <stop offset="100%" stopColor={SPRUCE} />
      </radialGradient>
    </defs>
    <path d="M0 -32 C 6 -18, 16 -6, 16 6 A 16 16 0 1 1 -16 6 C -16 -6, -6 -18, 0 -32 Z" fill="url(#dropg)" />
  </svg>
);

const Glow: React.FC<{ x: number; y: number; r: number; op: number }> = ({ x, y, r, op }) => (
  <div style={{ position: "absolute", left: x - r, top: y - r, width: 2 * r, height: 2 * r, borderRadius: "50%", opacity: op, background: `radial-gradient(circle, #f4f2ec 0%, ${SPRUCE_LIGHT} 28%, rgba(140,194,178,0.25) 55%, rgba(140,194,178,0) 72%)` }} />
);

const Pin: React.FC<{ at: { x: number; y: number }; text: string; sub?: string; op: number; below?: boolean }> = ({ at, text, sub, op, below }) => (
  <div style={{ position: "absolute", left: at.x, top: at.y, opacity: op }}>
    <div style={{ position: "absolute", left: -8, top: -8, width: 16, height: 16, borderRadius: "50%", background: T.paper, boxShadow: `0 0 0 ${5 * easeOut(op)}px rgba(244,242,236,0.25)` }} />
    <div style={{ position: "absolute", left: -360, width: 720, top: below ? 22 : sub ? -104 : -66, textAlign: "center", textShadow: "0 2px 12px rgba(0,0,0,0.85)" }}>
      <Label size={34} weight={500}>{text}</Label>
      {sub ? <Label size={28} color="rgba(244,242,236,0.82)" style={{ marginTop: 2 }}>{sub}</Label> : null}
    </div>
  </div>
);

/** The route drawn up to a fraction, as a glowing line. */
const Route: React.FC<{ pts: { lon: number; lat: number }[]; upTo: number; P: PFn; W: number; H: number; op: number }> = ({ pts, upTo, P, W, H, op }) => {
  const xy: { x: number; y: number }[] = [];
  const head = along(pts, upTo);
  for (let i = 0; i <= head.seg; i++) xy.push(P(pts[i].lon, pts[i].lat));
  xy.push(P(head.lon, head.lat));
  const d = xy.map((p, i) => `${i ? "L" : "M"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  return (
    <svg width={W} height={H} style={{ position: "absolute", inset: 0, opacity: op }}>
      <path d={d} stroke={SPRUCE_LIGHT} strokeOpacity={0.35} strokeWidth={14} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d={d} stroke="#e9f3ef" strokeWidth={4} fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

const NUMBERS = [
  { line: "num1", big: () => field("ext_drought_pct"), sub: "of Colorado is in drought", src: () => field("ext_drought_src") },
  { line: "num2", big: () => field("ext_strontia_pct"), sub: "of Denver's drinking water passes through one reservoir", src: () => field("ext_strontia_src") },
  { line: "num3", big: () => field("ext_sediment"), sub: "cubic yards of mud in it, after two past fires", src: () => field("ext_sediment_src") },
];

const BackOverlay: React.FC<{ t: number; k: Times; P: PFn; W: number; H: number; L: (id: string) => TLine | undefined }> = ({ t, k, P, W, H, L }) => {
  // The drop forms at the top of the frame and falls to the tap.
  const formU = easeOut(clamp01((t - k.form) / 0.7));
  const fallU = clamp01((t - (k.hit - 0.45)) / 0.45);
  const dropY = lerp(H * 0.28, H * 0.5, fallU * fallU);
  const preHit = t < k.hit;
  const mapIn = ramp(t, k.mapIn, k.mapIn + 1.1);
  const p = easeInOut(clamp01((t - k.m0) / (k.m1 - k.m0)));
  const head = along(ROUTE, p);
  const hp = P(head.lon, head.lat);
  const routeOp = t < k.m0 ? 0 : 1 - 0.55 * ramp(t, k.n0, k.n0 + 1);
  const ripple = clamp01((t - k.hit) / 0.9);
  const strAt = vertexAt(ROUTE, 1), tunAt = vertexAt(ROUTE, 2);
  const sPin = P(RES.strontia.lon, RES.strontia.lat), dPin = P(RES.dillon.lon, RES.dillon.lat);
  const tunMid = along(ROUTE, tunAt + 0.35 * (1 - tunAt)), tm = P(tunMid.lon, tunMid.lat);
  const num2 = L("num2"), num3 = L("num3"), num4 = L("num4"), tap2 = L("tap2");
  return (
    <>
      {/* Black until the drop lands; the map comes up under it. */}
      <AbsoluteFill style={{ background: T.ink, opacity: 1 - mapIn }} />
      <AbsoluteFill style={{ background: "radial-gradient(85% 75% at 50% 50%, rgba(23,24,27,0) 50%, rgba(23,24,27,0.7) 100%)" }} />
      {preHit ? <Drop x={W / 2} y={dropY} size={lerp(4, 22, formU)} op={formU} stretch={1 + 0.35 * fallU} /> : null}
      {!preHit && t < k.m0 + 0.6 ? (
        <>
          <div style={{ position: "absolute", left: W / 2 - 160 * ripple, top: H / 2 - 160 * ripple, width: 320 * ripple, height: 320 * ripple, borderRadius: "50%", border: `3px solid rgba(232,243,239,${0.9 * (1 - ripple)})` }} />
          <Glow x={W / 2} y={H / 2} r={lerp(22, 30, ripple)} op={1 - ramp(t, k.m0, k.m0 + 0.6)} />
        </>
      ) : null}
      <div style={{ position: "absolute", left: 0, right: 0, top: H / 2 + 70, textAlign: "center", opacity: inOut(t, k.form + 0.3, k.m0 + 0.4, 0.4) }}>
        <Label size={34} color="rgba(244,242,236,0.86)" style={{ letterSpacing: "0.14em", textTransform: "uppercase", textShadow: "0 2px 12px rgba(0,0,0,0.85)" }}>Denver, Colorado</Label>
      </div>
      {t >= k.m0 ? (
        <>
          <Route pts={ROUTE} upTo={p} P={P} W={W} H={H} op={routeOp} />
          {t < k.m1 + 0.6 ? <Glow x={hp.x} y={hp.y} r={30} op={1 - ramp(t, k.m1, k.m1 + 0.6)} /> : null}
        </>
      ) : null}
      {/* Passing Strontia Springs, then under the Divide to Dillon. */}
      <Pin at={sPin} text={RES.strontia.name} op={t < k.n0 ? inOut(t, k.m0 + (k.m1 - k.m0) * (strAt - 0.08), k.m0 + (k.m1 - k.m0) * (strAt + 0.3)) : inOut(t, num2?.start ?? k.n0, (num4?.start ?? k.n1) + 0.2)} below />
      <div style={{ position: "absolute", left: tm.x - 380, top: tm.y + 44, width: 760, textAlign: "center", opacity: inOut(t, k.m0 + (k.m1 - k.m0) * (tunAt + 0.02), k.m1 + 1.2), textShadow: "0 2px 12px rgba(0,0,0,0.85)" }}>
        <Label size={34} weight={500}>Roberts Tunnel, under the Divide</Label>
        <Label size={26} color="rgba(244,242,236,0.8)">route drawn schematically</Label>
      </div>
      <Pin at={dPin} text={RES.dillon.name} sub="West of the Continental Divide" op={inOut(t, k.m1 - 0.8, k.reveal + 0.9)} />
      {t >= (tap2?.start ?? k.m0) - 0.2 && t < k.reveal + 0.2 ? <SourceLine t={t} start={(tap2?.start ?? k.m0) + 0.2} end={k.reveal + 0.2} text={`About half: ${field("ext_half_src")}, “Where does your water come from?”`} /> : null}
      {/* This year: the watershed in the latest published week. */}
      <div style={{ position: "absolute", left: 96, top: 84, opacity: inOut(t, k.reveal + 0.3, k.n0 + 0.1, 0.4) }}>
        <Label size={28} color="rgba(244,242,236,0.78)" style={{ fontFamily: FONT.mono }}>U.S. Drought Monitor, week of {field(`issue_${LAST}`)}, {field("year")}</Label>
        <div style={{ display: "flex", gap: 18, marginTop: 14 }}>
          {[1, 2, 3, 4].map((n) => (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 22, height: 22, background: DROUGHT[n], borderRadius: 2 }} />
              <Label size={26} color="rgba(244,242,236,0.86)">{field(`cat_${n}`)} {field(`cat_${n}_name`)}</Label>
            </div>
          ))}
        </div>
      </div>
      {/* The numbers land on the map, one at a time. */}
      {t >= k.n0 - 0.2 ? <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(23,24,27,0.9) 0%, rgba(23,24,27,0.72) 40%, rgba(23,24,27,0) 72%)", opacity: inOut(t, k.n0 - 0.2, (num4?.start ?? k.n1) + 0.9, 0.5) }} /> : null}
      {NUMBERS.map((c, i) => {
        const l = L(c.line);
        if (!l) return null;
        const next = i < 2 ? L(NUMBERS[i + 1].line)?.start ?? l.end + 1 : (num4?.start ?? l.end) + 0.8;
        if (t < l.start - 0.1 || t > next + 0.3) return null;
        const hit = easeOut(clamp01((t - l.start + 0.06) / 0.22));
        const leave = ramp(t, next - 0.12, next + 0.1);
        return (
          <div key={c.line} style={{ position: "absolute", left: 140, top: 0, bottom: 0, width: 1000, display: "flex", flexDirection: "column", justifyContent: "center", opacity: hit * (1 - leave) }}>
            <div style={{ transform: `scale(${lerp(1.18, 1, hit)})`, transformOrigin: "0 50%" }}>
              <div style={{ fontFamily: FONT.serif, fontWeight: 300, fontSize: i === 2 ? 220 : 290, lineHeight: 1, color: T.paper, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{c.big()}</div>
              <div style={{ fontFamily: FONT.sans, fontSize: 50, lineHeight: 1.2, color: "rgba(244,242,236,0.9)", marginTop: 20, maxWidth: 1150 }}>{c.sub}</div>
            </div>
          </div>
        );
      })}
      {NUMBERS.map((c, i) => {
        const l = L(c.line);
        if (!l) return null;
        const next = i < 2 ? L(NUMBERS[i + 1].line)?.start ?? l.end + 1 : (num4?.start ?? l.end) + 0.8;
        return t >= l.start - 0.1 && t <= next + 0.2 ? <SourceLine key={c.line + "s"} t={t} start={l.start} end={next + 0.1} text={`Source: ${c.src()}`} /> : null;
      })}
      {num3 ? null : null}
    </>
  );
};

const ForwardOverlay: React.FC<{ t: number; k: Times; P: PFn; W: number; H: number; startCam: Cam }> = ({ t, k, P, W, H, startCam }) => {
  const route = [{ lon: startCam.lon, lat: startCam.lat }, ...[...ROUTE].reverse()];
  const p = easeInOut(clamp01((t - k.f0) / (k.f1 - k.f0)));
  const dilAt = vertexAt(route, 1);
  const water = [...ROUTE].reverse();
  // The water's route starts at Dillon: map the camera's progress onto it.
  const wp = clamp01((p - dilAt) / (1 - dilAt));
  const head = along(water, wp);
  const hp = P(head.lon, head.lat);
  const top = (bb: [number, number, number, number]) => P((bb[0] + bb[2]) / 2, bb[3]);
  const areas: [keyof typeof BOX, string][] = [["larimer", DATA.areas.larimer.label], ["denver", "Denver"], ["usp", DATA.areas.upper_south_platte.label], ["dillon", DATA.areas.dillon.label], ["pueblo", DATA.areas.pueblo.label]];
  const labelsOp = inOut(t, k.s + 0.3, k.f0 + 0.3, 0.4);
  const end = ramp(t, k.f1 + 0.1, k.e - 0.25);
  return (
    <>
      <AbsoluteFill style={{ background: "radial-gradient(85% 75% at 50% 50%, rgba(23,24,27,0) 50%, rgba(23,24,27,0.7) 100%)" }} />
      {areas.map(([key, label], i) => {
        // Dillon and the Upper South Platte touch: the second is labelled under its area.
        const bb = BOX[key];
        const under = key === "usp";
        const at = under ? P((bb[0] + bb[2]) / 2, bb[1]) : top(bb);
        return (
          <div key={key} style={{ position: "absolute", left: Math.min(Math.max(at.x, W * 0.12), W * 0.88) - 300, top: under ? at.y + 10 : at.y - 54, width: 600, textAlign: "center", opacity: labelsOp * ramp(t, k.s + 0.2 + i * 0.25, k.s + 0.6 + i * 0.25), textShadow: "0 2px 12px rgba(0,0,0,0.85)" }}>
            <Label size={34} weight={500}>{label}</Label>
          </div>
        );
      })}
      {t > k.f0 && p > dilAt ? (
        <>
          <Route pts={water} upTo={wp} P={P} W={W} H={H} op={1 - end} />
          <Glow x={hp.x} y={hp.y} r={30} op={1 - end} />
        </>
      ) : null}
      {/* Back at the tap: the drop, and the frame goes to black for the end card. */}
      <AbsoluteFill style={{ background: T.ink, opacity: end * 0.92 }} />
      {t > k.f1 - 0.2 ? <Drop x={W / 2} y={H / 2 + 20} size={22} op={ramp(t, k.f1 - 0.2, k.f1 + 0.3) * (1 - ramp(t, k.e - 0.3, k.e))} /> : null}
      {t > k.f1 - 0.6 ? (
        <div style={{ position: "absolute", left: 0, right: 0, top: H / 2 + 80, textAlign: "center", opacity: inOut(t, k.f1 - 0.6, k.e, 0.3) }}>
          <Label size={34} color="rgba(244,242,236,0.86)" style={{ letterSpacing: "0.14em", textTransform: "uppercase", textShadow: "0 2px 12px rgba(0,0,0,0.85)" }}>Denver, Colorado</Label>
        </div>
      ) : null}
    </>
  );
};
