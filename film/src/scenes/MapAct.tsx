/**
 * Parts 1 and 2 on one map: the 2026 drought week by week (cold open), then
 * Denver, its two source watersheds, Dillon Reservoir and the Roberts Tunnel.
 *
 * The map is MapLibre with the app's own style (app/lib/basemap.ts) and its
 * own self-hosted basemap, read by byte ranges from the production build
 * served locally (scripts/serve_static.py). Every frame sets the camera and the
 * layers for its time, then waits for the map to finish drawing before the
 * frame is taken. Labels and lines are drawn in React on top, placed with
 * the same Web Mercator maths MapLibre uses (mercator.ts).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { AbsoluteFill, continueRender, delayRender } from "remotion";
import * as maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import { basemapStyle } from "../../../app/lib/basemap";
import { LINKS } from "../../../app/lib/links";
import { DATA } from "../data";
import { fit, mix, project, union, type BBox, type Cam } from "../mercator";
import { DROUGHT, FONT, T } from "../theme";
import { field, type Lang } from "../trace";
import { clamp01, easeInOut, easeOut, inOut, ramp, useT } from "../util";
import { Kinetic, Label, SourceLine } from "../components/Type";

export const SITE = "http://127.0.0.1:4100/cofire"; // scripts/serve_static.py
export const HALF = 1 / 48; // half a cell, as the app draws them (components/MapView.tsx)

export const proto = { added: false };
export function style(): maplibregl.StyleSpecification {
  const s = structuredClone(basemapStyle("selfhost")) as maplibregl.StyleSpecification & { glyphs: string };
  s.glyphs = `${SITE}/fonts/{fontstack}/{range}.pbf`;
  (s.sources.basemap as maplibregl.VectorSourceSpecification).url = `pmtiles://${SITE}/tiles/colorado.pmtiles`;
  // The extract covers Colorado's middle; a wide 16:9 frame reaches past it.
  // Paint the background the land colour so its edge does not show as a seam.
  const bg = s.layers.find((l) => l.id === "bg") as maplibregl.BackgroundLayerSpecification | undefined;
  if (bg) bg.paint = { "background-color": T.land };
  return s;
}

const D = DATA.drought;
const areaBox = (d: string): BBox => {
  const a = DATA.areas[d];
  const cs = D.cells.slice(a.first, a.first + a.n);
  return [Math.min(...cs.map((c) => c[2])) - HALF, Math.min(...cs.map((c) => c[1])) - HALF, Math.max(...cs.map((c) => c[2])) + HALF, Math.max(...cs.map((c) => c[1])) + HALF];
};
export const BOX = { denver: areaBox("denver"), usp: areaBox("upper_south_platte"), dillon: areaBox("dillon"), larimer: areaBox("larimer"), pueblo: areaBox("pueblo") };
const ALL = union(BOX.denver, BOX.usp, BOX.dillon, BOX.larimer, BOX.pueblo);
const THREE = union(BOX.denver, BOX.usp, BOX.dillon);
export const RES = DATA.reservoirs as unknown as Record<string, { lon: number; lat: number; name: string }>;

function geojson(issue: number): GeoJSON.FeatureCollection {
  const row = D.cat[issue];
  return {
    type: "FeatureCollection",
    features: D.cells.map(([d, lat, lon], i) => ({
      type: "Feature",
      properties: { d, c: row[i] === "x" ? -1 : Number(row[i]) },
      geometry: { type: "Polygon", coordinates: [[[lon - HALF, lat - HALF], [lon + HALF, lat - HALF], [lon + HALF, lat + HALF], [lon - HALF, lat + HALF], [lon - HALF, lat - HALF]]] },
    })),
  };
}

/** Which published issue is on screen at film time t (cold open steps through all of them). */
export function issueAt(t: number): number {
  const n = D.issues.length;
  return Math.max(0, Math.min(n - 1, Math.floor(((t - 0.7) / 8.4) * n)));
}

type State = { cam: Cam; issue: number; op: Record<string, number>; threat: number };

export function cameras(W: number, H: number) {
  const portrait = H > W;
  const pad: [number, number, number, number] = portrait ? [360, 70, 420, 70] : [150, 140, 150, 140];
  const all = fit(ALL, W, H, pad);
  const denver = fit(BOX.denver, W, H, portrait ? [520, 120, 620, 120] : [200, 480, 200, 480]);
  const three = fit(THREE, W, H, pad);
  const tun = fit([RES.dillon.lon - 0.16, Math.min(RES.dillon.lat, RES.tunnel_end.lat) - 0.2, RES.tunnel_end.lon + 0.3, Math.max(RES.dillon.lat, RES.tunnel_end.lat) + 0.14], W, H, pad);
  return { all, denver, three, tun, portrait };
}

/** The finale: Denver and its watersheds at the latest issue, pulling back to all five areas. */
function finaleState(t: number, W: number, H: number): State {
  const c = cameras(W, H);
  const u = easeInOut(clamp01(t / 5.1));
  const cam = mix({ ...c.three, zoom: c.three.zoom + 0.3 }, { ...c.all, zoom: c.all.zoom - 0.08 }, u);
  const rest = 0.2 + 0.6 * ramp(t, 1.4, 3.4);
  return { cam, issue: D.issues.length - 1, op: { denver: 0.85, upper_south_platte: 0.85, dillon: 0.85, larimer: rest, pueblo: rest }, threat: 0 };
}

function stateAt(t: number, W: number, H: number, finale = false): State {
  if (finale) return finaleState(t, W, H);
  const c = cameras(W, H);
  const out = (cam: Cam, dz: number): Cam => ({ ...cam, zoom: cam.zoom + dz });
  const keys: [number, Cam][] = [
    [0, out(c.all, -0.22)],
    [5, c.all],
    [10, mix(out(c.all, 0.35), c.denver, 0.18)],
    [15.0, out(c.denver, -0.35)],
    [19.4, c.three],
    [22.6, mix(c.three, c.tun, 0.55)],
    [27.5, c.tun],
    [33, out(c.three, -0.12)],
  ];
  let cam = keys[keys.length - 1][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [ta, a] = keys[i], [tb, b] = keys[i + 1];
    if (t <= tb) { cam = mix(a, b, easeInOut(clamp01((t - ta) / (tb - ta)))); break; }
  }
  const dim = ramp(t, 10.2, 12.0);
  const ws = ramp(t, 15.8, 17.4);
  const op = {
    denver: 0.78,
    upper_south_platte: 0.78 - 0.6 * dim + 0.55 * ws,
    dillon: 0.78 - 0.6 * dim + 0.55 * ws,
    larimer: 0.78 - 0.66 * dim,
    pueblo: 0.78 - 0.66 * dim,
  };
  const threat = t < 27.5 ? 0 : 0.5 + 0.18 * Math.sin((t - 27.5) * 2.4) - 0.5 * (1 - ramp(t, 27.6, 28.6));
  return { cam, issue: t < 10 ? issueAt(t) : D.issues.length - 1, op, threat: Math.max(0, threat) };
}

function apply(m: maplibregl.Map, s: State, applied: { issue: number }) {
  m.jumpTo({ center: [s.cam.lon, s.cam.lat], zoom: s.cam.zoom });
  if (applied.issue !== s.issue) {
    (m.getSource("cells") as maplibregl.GeoJSONSource).setData(geojson(s.issue));
    applied.issue = s.issue;
  }
  m.setPaintProperty("cells-fill", "fill-opacity", ["match", ["get", "d"], "denver", s.op.denver, "upper_south_platte", s.op.upper_south_platte, "dillon", s.op.dillon, "larimer", s.op.larimer, s.op.pueblo]);
  m.setPaintProperty("cells-threat", "fill-opacity", s.threat);
}

export const MapAct: React.FC<{ offset?: number; W: number; H: number; lang?: Lang; finale?: boolean }> = ({ offset = 0, W, H, lang = "en", finale = false }) => {
  const t = useT() + offset;
  const ref = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const applied = useRef({ issue: -1, key: "" });
  const latest = useRef<State>(stateAt(t, W, H, finale));
  const s = useMemo(() => stateAt(t, W, H, finale), [t, W, H, finale]);
  latest.current = s;
  const [ready, setReady] = useState(false);
  const [initHandle] = useState(() => delayRender("map: style and tiles", { timeoutInMilliseconds: 180000 }));

  useEffect(() => {
    if (!proto.added) { maplibregl.addProtocol("pmtiles", new Protocol().tile); proto.added = true; }
    maplibregl.setWorkerUrl(`${SITE}/maplibre/maplibre-gl-worker.mjs`);
    const m = new maplibregl.Map({ container: ref.current as HTMLDivElement, style: style(), interactive: false, attributionControl: false, fadeDuration: 0, pixelRatio: 1, center: [latest.current.cam.lon, latest.current.cam.lat], zoom: latest.current.cam.zoom });
    m.on("error", (e) => { throw new Error(`map error: ${e.error?.message ?? e}`); });
    m.on("load", () => {
      m.addSource("cells", { type: "geojson", data: geojson(latest.current.issue) });
      applied.current.issue = latest.current.issue;
      const before = "places";
      m.addLayer({ id: "cells-fill", type: "fill", source: "cells", paint: { "fill-color": ["match", ["get", "c"], 1, DROUGHT[1], 2, DROUGHT[2], 3, DROUGHT[3], 4, DROUGHT[4], "rgba(0,0,0,0)"], "fill-opacity": 0.78, "fill-antialias": false } }, before);
      m.addLayer({ id: "cells-threat", type: "fill", source: "cells", filter: ["in", ["get", "d"], ["literal", ["upper_south_platte", "dillon"]]], paint: { "fill-color": T.ember, "fill-opacity": 0 } }, before);
      m.addLayer({ id: "cells-line", type: "line", source: "cells", paint: { "line-color": T.ink, "line-opacity": 0.22, "line-width": 0.6 } }, before);
      map.current = m;
      apply(m, latest.current, applied.current);
      m.once("idle", () => { setReady(true); continueRender(initHandle); });
    });
    return () => m.remove();
  }, [initHandle]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const key = `${t.toFixed(4)}`;
    if (applied.current.key === key) return;
    applied.current.key = key;
    const h = delayRender(`map frame ${key}`, { timeoutInMilliseconds: 180000 });
    apply(m, s, applied.current);
    m.once("idle", () => continueRender(h));
    m.triggerRepaint();
  }, [ready, t, s]);

  const P = (lon: number, lat: number) => project(lon, lat, s.cam, W, H);
  const portrait = H > W;
  const top = (b: BBox) => P((b[0] + b[2]) / 2, b[3]);
  const issue = s.issue;
  const tick = t < 10.4;
  const dil = P(RES.dillon.lon, RES.dillon.lat);
  const tend = P(RES.tunnel_end.lon, RES.tunnel_end.lat);
  const draw = ramp(t, 23.0, 25.6, easeInOut);
  const src = (id: keyof typeof LINKS) => `${lang === "es" ? "Fuente" : "Source"}: ${LINKS[id].publisher}, “${LINKS[id].title}”, ${LINKS[id].url.replace(/^https:\/\/(www\.)?/, "")}`;

  return (
    <AbsoluteFill style={{ background: T.ink }}>
      <div ref={ref} style={{ position: "absolute", inset: 0, width: W, height: H }} />
      <ExtractEdges P={P} zoom={s.cam.zoom} W={W} H={H} />

      {finale ? (
        <>
          <AreaLabel W={W} at={top(BOX.denver)} text="Denver" op={ramp(t, 0.3, 1.0) * (1 - ramp(t, 4.3, 4.9))} big />
          <AreaLabel W={W} at={top(BOX.usp)} text={DATA.areas.upper_south_platte.label} op={ramp(t, 0.6, 1.3) * (1 - ramp(t, 2.0, 2.6))} />
          <AreaLabel W={W} at={top(BOX.dillon)} text={DATA.areas.dillon.label} op={ramp(t, 0.8, 1.5) * (1 - ramp(t, 2.0, 2.6))} />
          <AreaLabel W={W} at={top(BOX.larimer)} text={DATA.areas.larimer.label} op={ramp(t, 2.4, 3.1) * (1 - ramp(t, 4.3, 4.9))} />
          <AreaLabel W={W} at={top(BOX.pueblo)} text={DATA.areas.pueblo.label} op={ramp(t, 2.6, 3.3) * (1 - ramp(t, 4.3, 4.9))} />
          <AbsoluteFill style={{ background: `radial-gradient(90% 80% at 50% 50%, rgba(23,24,27,0) 55%, rgba(23,24,27,0.75) 100%)` }} />
          <AbsoluteFill style={{ background: T.ink, opacity: ramp(t, 4.75, 5.1) }} />
        </>
      ) : (
        <>
      {/* Cold open: the week ticker and the one line of kinetic type. */}
      {tick ? (
        <div style={{ position: "absolute", left: portrait ? 70 : 96, top: portrait ? 150 : 84, opacity: inOut(t, 0.9, 10.4, 0.5) }}>
          <Label size={portrait ? 34 : 26} color="rgba(244,242,236,0.7)" style={{ fontFamily: FONT.mono, letterSpacing: "0.04em" }}>{field(`issue_${issue}`, lang)}, {field("year")}</Label>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginTop: 10 }}>
            <Label size={portrait ? 92 : 76} weight={500} style={{ fontFamily: FONT.mono }}>{field(`d2_${issue}`)}</Label>
            <Label size={portrait ? 34 : 28} color="rgba(244,242,236,0.75)">{lang === "es" ? "de" : "of"} {field("n_cells")} {lang === "es" ? "cuadros en sequía severa o peor" : "squares in severe drought or worse"}</Label>
          </div>
          <div style={{ display: "flex", gap: 18, marginTop: 18 }}>
            {[1, 2, 3, 4].map((n) => (
              <div key={n} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 22, height: 22, background: DROUGHT[n], borderRadius: 2 }} />
                <Label size={portrait ? 28 : 25} color="rgba(244,242,236,0.8)">{field(`cat_${n}`)} {field(`cat_${n}_name`, lang)}</Label>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {t < 5.4 ? (
        <div style={{ position: "absolute", left: 0, right: 0, top: portrait ? H * 0.42 : H * 0.6, display: "flex", justifyContent: "center", padding: "0 60px" }}>
          <Kinetic text={lang === "es" ? `${field("year")}, semana a semana.` : `${field("year")}, week by week.`} t={t} start={0.6} end={5.2} size={portrait ? 104 : 120} />
        </div>
      ) : null}
      {t < 10.4 ? <SourceLine t={t} start={1.2} end={10.2} text={lang === "es" ? "Sequía: U.S. Drought Monitor, como la publicó COFIRE cada semana" : "Drought: U.S. Drought Monitor, as COFIRE published it each week"} /> : null}

      {/* Part 2: the areas. */}
      {t >= 10 && t < 16.2 ? <AreaLabel W={W} at={top(BOX.denver)} text="Denver" op={inOut(t, 10.4, 16.2)} big /> : null}
      {t >= 15.6 && t < 22.8 ? (
        <>
          <AreaLabel W={W} at={top(BOX.usp)} text={DATA.areas.upper_south_platte.label} op={inOut(t, 16.2, 22.8)} />
          <AreaLabel W={W} at={top(BOX.dillon)} text={DATA.areas.dillon.label} op={inOut(t, 16.6, 22.8)} />
          <AreaLabel W={W} at={top(BOX.denver)} text="Denver" op={inOut(t, 15.6, 22.8) * 0.7} />
        </>
      ) : null}
      {t >= 19.4 && t < 28 ? <Marker at={dil} text={RES.dillon.name} op={inOut(t, 19.8, 28)} /> : null}
      {t >= 22.6 && t < 28 ? (
        <svg width={W} height={H} style={{ position: "absolute", inset: 0, opacity: inOut(t, 22.8, 28) }}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={T.paper} />
            </marker>
          </defs>
          <path d={`M ${dil.x} ${dil.y} L ${dil.x + (tend.x - dil.x) * draw} ${dil.y + (tend.y - dil.y) * draw}`} stroke={T.paper} strokeWidth={4} strokeDasharray="14 10" fill="none" markerEnd={draw > 0.97 ? "url(#arrow)" : undefined} />
          <foreignObject x={(dil.x + tend.x) / 2 - 300} y={(dil.y + tend.y) / 2 + 26} width={600} height={120}>
            <div style={{ textAlign: "center", opacity: ramp(t, 23.6, 24.2) }}>
              <Label size={portrait ? 34 : 30} weight={500}>Roberts Tunnel</Label>
              <Label size={portrait ? 26 : 24} color="rgba(244,242,236,0.8)">{lang === "es" ? "ruta esquemática" : "route drawn schematically"}</Label>
            </div>
          </foreignObject>
        </svg>
      ) : null}
      {t >= 27.5 ? (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: portrait ? "52%" : "62%", opacity: inOut(t, 27.7, 33.4, 0.5), background: portrait ? "linear-gradient(0deg, rgba(23,24,27,0.92) 30%, rgba(23,24,27,0) 100%)" : "linear-gradient(20deg, rgba(23,24,27,0.94) 22%, rgba(23,24,27,0.55) 48%, rgba(23,24,27,0) 70%)" }} />
      ) : null}
      {t >= 27.5 ? (
        <div style={{ position: "absolute", left: portrait ? 70 : 120, right: portrait ? 70 : undefined, bottom: portrait ? 260 : 150, maxWidth: portrait ? undefined : 820, opacity: inOut(t, 27.9, 33.4, 0.5) }}>
          <div style={{ fontFamily: FONT.serif, fontStyle: "italic", fontSize: portrait ? 54 : 50, lineHeight: 1.18, color: T.paper }}>
            {lang === "es" ? "“Los incendios moderados y graves son la mayor amenaza para el suministro de agua sin tratar de Denver.”" : "“Moderate and severe wildfires are the greatest threat to Denver's raw water supply.”"}
          </div>
          <Label size={portrait ? 28 : 24} color="rgba(244,242,236,0.7)" style={{ marginTop: 14 }}>Denver Water</Label>
        </div>
      ) : null}
      {t >= 15.6 && t < 27.6 ? <SourceLine t={t} start={15.9} end={27.6} text={src("denver_water_sources")} /> : null}
      {t >= 27.5 ? <SourceLine t={t} start={27.8} end={33.4} text={src("denver_water_watershed")} /> : null}

        </>
      )}
      <div style={{ position: "absolute", right: 22, bottom: 16, fontFamily: FONT.sans, fontSize: 18, color: "rgba(244,242,236,0.6)" }}>© OpenStreetMap contributors · © Protomaps</div>
    </AbsoluteFill>
  );
};

/**
 * The basemap extract covers Colorado's middle; a wide frame reaches past its
 * east and west edges, where the map would stop in a straight line. Feather
 * those edges into the dark ground instead.
 */
const ExtractEdges: React.FC<{ P: (lon: number, lat: number) => { x: number; y: number }; zoom: number; W: number; H: number }> = ({ P, zoom, W, H }) => {
  // What is drawn is whole tiles at the zoom MapLibre loads (512-pixel tiles:
  // the floor of the camera zoom, at most the extract's maximum), so the map
  // really ends at those tiles' outer edges, past the extract's own bounds.
  const [w, , e] = DATA.basemap.bounds;
  const z = Math.max(0, Math.min(DATA.basemap.maxZoom, Math.floor(zoom)));
  const n = 2 ** z;
  const west = (Math.floor(((w + 180) / 360) * n) / n) * 360 - 180;
  const east = ((Math.floor(((e + 180) / 360) * n) + 1) / n) * 360 - 180;
  const x0 = P(west, 39.4).x, x1 = P(east, 39.4).x;
  const F = 160;
  return (
    <>
      {x0 + F > 0 ? <div style={{ position: "absolute", left: 0, top: 0, width: x0 + F, height: H, background: `linear-gradient(90deg, ${T.ink} 0px, ${T.ink} ${Math.max(0, x0)}px, rgba(23,24,27,0) ${x0 + F}px)` }} /> : null}
      {x1 - F < W ? <div style={{ position: "absolute", left: x1 - F, top: 0, width: W - x1 + F, height: H, background: `linear-gradient(90deg, rgba(23,24,27,0) 0px, ${T.ink} ${F}px, ${T.ink} 100%)` }} /> : null}
    </>
  );
};

const AreaLabel: React.FC<{ at: { x: number; y: number }; text: string; op: number; big?: boolean; W: number }> = ({ at, text, op, big, W }) => (
  // Kept inside the frame: a label whose area runs off the edge stays readable.
  <div style={{ position: "absolute", left: Math.min(Math.max(at.x, W * 0.17), W * 0.83) - 400, top: at.y - (big ? 74 : 56), width: 800, textAlign: "center", opacity: op, transform: `translateY(${(1 - op) * 10}px)` }}>
    <Label size={big ? 48 : 34} weight={500} style={{ textShadow: "0 2px 12px rgba(0,0,0,0.8)" }}>{text}</Label>
  </div>
);

const Marker: React.FC<{ at: { x: number; y: number }; text: string; op: number }> = ({ at, text, op }) => {
  const u = easeOut(op);
  return (
    <div style={{ position: "absolute", left: at.x, top: at.y, opacity: op }}>
      <div style={{ position: "absolute", left: -9, top: -9, width: 18, height: 18, borderRadius: "50%", background: T.paper, boxShadow: `0 0 0 ${6 * u}px rgba(244,242,236,0.25)` }} />
      <div style={{ position: "absolute", left: -300, top: -64, width: 600, textAlign: "center" }}>
        <Label size={28} weight={500} style={{ textShadow: "0 2px 10px rgba(0,0,0,0.85)" }}>{text}</Label>
      </div>
    </div>
  );
};
