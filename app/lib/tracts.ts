/**
 * Denver's census tracts with their Colorado EnviroScreen 2.0 percentiles
 * (cofire/ship/enviroscreen.py). Context for the forecast, never part of it.
 * Loaded on demand, so the map's first paint does not wait for it.
 */
export type TractProps = { geoid: string; pop: number | null; score: number | null; heat: number | null; pm25: number | null; asthma: number | null };
export type TractFeature = { type: "Feature"; properties: TractProps; geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] } };
export type Tracts = { type: "FeatureCollection"; meta: { source: string; published: string; page: string; fetched: string }; features: TractFeature[] };

let cache: Promise<Tracts> | null = null;

export function loadTracts(): Promise<Tracts> {
  cache ??= import("./enviroscreen_denver.json").then((m) => (m.default ?? m) as unknown as Tracts);
  return cache;
}

function inRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** The tract containing a point, or null outside Denver. Holes are respected. */
export function tractAt(tracts: Tracts, lat: number, lon: number): TractFeature | null {
  for (const f of tracts.features) {
    const polys = (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates) as number[][][][];
    for (const rings of polys) {
      if (inRing(lon, lat, rings[0]) && !rings.slice(1).some((h) => inRing(lon, lat, h))) return f;
    }
  }
  return null;
}

/** A point inside the tract, for selecting its forecast cell: the middle of its bounding box if that falls inside, else its first vertex. */
export function tractPoint(f: TractFeature): [number, number] {
  const polys = (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates) as number[][][][];
  const ring = polys[0][0];
  const xs = ring.map((p) => p[0]);
  const ys = ring.map((p) => p[1]);
  const lon = (Math.min(...xs) + Math.max(...xs)) / 2;
  const lat = (Math.min(...ys) + Math.max(...ys)) / 2;
  const t = { type: "FeatureCollection", meta: {}, features: [f] } as unknown as Tracts;
  return tractAt(t, lat, lon) ? [lat, lon] : [ring[0][1], ring[0][0]];
}
