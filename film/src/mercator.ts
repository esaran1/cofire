/**
 * Web Mercator camera maths, the same as MapLibre's (512-pixel world tiles),
 * so overlays drawn in React land exactly on the map MapLibre draws.
 */
export type Cam = { lon: number; lat: number; zoom: number };
export type BBox = [number, number, number, number]; // west, south, east, north

export const mx = (lon: number) => (lon + 180) / 360;
export const my = (lat: number) => {
  const s = Math.sin((lat * Math.PI) / 180);
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
};
const unmy = (y: number) => (360 / Math.PI) * Math.atan(Math.exp((0.5 - y) * 2 * Math.PI)) - 90;

/** Screen position of a coordinate for a camera over a W x H viewport. */
export function project(lon: number, lat: number, cam: Cam, W: number, H: number): { x: number; y: number } {
  const ws = 512 * 2 ** cam.zoom;
  return { x: W / 2 + (mx(lon) - mx(cam.lon)) * ws, y: H / 2 + (my(lat) - my(cam.lat)) * ws };
}

/** The camera that fits a box into W x H with padding (pixels): top, right, bottom, left. */
export function fit(b: BBox, W: number, H: number, pad: [number, number, number, number] = [80, 80, 80, 80]): Cam {
  const [t, r, bo, l] = pad;
  const x1 = mx(b[0]), x2 = mx(b[2]), y1 = my(b[3]), y2 = my(b[1]);
  const scale = Math.min((W - l - r) / ((x2 - x1) * 512), (H - t - bo) / ((y2 - y1) * 512));
  const zoom = Math.log2(scale);
  // Centre the box in the padded area.
  const ws = 512 * 2 ** zoom;
  const cx = (x1 + x2) / 2 + ((r - l) / 2) / ws;
  const cy = (y1 + y2) / 2 + ((bo - t) / 2) / ws;
  return { lon: cx * 360 - 180, lat: unmy(cy), zoom };
}

/** Ease between two cameras: centre in Mercator space, zoom linear. */
export function mix(a: Cam, b: Cam, u: number): Cam {
  const x = mx(a.lon) + (mx(b.lon) - mx(a.lon)) * u;
  const y = my(a.lat) + (my(b.lat) - my(a.lat)) * u;
  return { lon: x * 360 - 180, lat: unmy(y), zoom: a.zoom + (b.zoom - a.zoom) * u };
}

export function union(...bs: BBox[]): BBox {
  return [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))];
}
