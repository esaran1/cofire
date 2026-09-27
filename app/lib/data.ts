import { getParsed } from "./api";
import {
  Bundle,
  BundleCell,
  BundleSchema,
  DomainsIndex,
  DomainsIndexSchema,
  Place,
  PlaceSchema,
} from "./schemas";

/**
 * Forecast data for the map, the Place Card and anything that needs a cell.
 *
 * Reads the per-domain bundles, from the API or, when the app is deployed as a
 * static site, from the same files served beside the pages
 * (`NEXT_PUBLIC_DATA_BASE`). Both paths go through the same schemas.
 */
const STATIC_BASE = process.env.NEXT_PUBLIC_DATA_BASE;

async function fetchStatic<T>(path: string, parse: (raw: unknown) => T): Promise<T> {
  const res = await fetch(`${STATIC_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return parse(await res.json());
}

let indexCache: Promise<DomainsIndex> | null = null;

export function getDomains(): Promise<DomainsIndex> {
  if (!indexCache) {
    indexCache = (
      STATIC_BASE
        ? fetchStatic("/domains/index.json", (r) => DomainsIndexSchema.parse(r))
        : getParsed("/domains", DomainsIndexSchema)
    ).catch((e: unknown) => {
      indexCache = null;
      throw e;
    });
  }
  return indexCache;
}

const bundleCache = new Map<string, Promise<Bundle>>();

export function getBundle(domain: string, issue: string): Promise<Bundle> {
  const key = `${domain}/${issue}`;
  let p = bundleCache.get(key);
  if (!p) {
    p = (
      STATIC_BASE
        ? fetchStatic(`/domains/${key}.json`, (r) => BundleSchema.parse(r))
        : getParsed(`/domains/${key}`, BundleSchema)
    ).catch((e: unknown) => {
      bundleCache.delete(key);
      throw e;
    });
    bundleCache.set(key, p);
  }
  return p;
}

/** The cell whose centre is closest to a point, within one bundle. */
export function nearestCell(bundle: Bundle, lat: number, lon: number): BundleCell | null {
  let best: BundleCell | null = null;
  let d = Infinity;
  for (const c of bundle.cells) {
    const e = (c.lat - lat) ** 2 + (c.lon - lon) ** 2;
    if (e < d) {
      d = e;
      best = c;
    }
  }
  return best;
}

/** Rebuild a Place, the Place Card's input, from one bundle cell. */
export function placeFromCell(bundle: Bundle, cell: BundleCell, historyYears: string): Place {
  const targets: Record<string, { p: number | null; state: Bundle["decisions"]["targets"][string][0]; reason: string | null }> = {};
  bundle.targets.forEach((t, i) => {
    const [state, reason] = bundle.decisions.targets[t] ?? [null, null];
    targets[t] = { p: cell.p[i] ?? null, state, reason };
  });
  const horizons: Record<string, unknown> = {};
  for (const [h, [point, lo, hi, week]] of Object.entries(cell.h)) {
    const [state, reason] = bundle.decisions.horizons[h] ?? [null, null];
    horizons[h] = { point, state, reason, hist_lo: lo, hist_hi: hi, hist_years: historyYears, target_week: week };
  }
  return PlaceSchema.parse({
    cell_id: cell.id,
    lat: cell.lat,
    lon: cell.lon,
    issue: bundle.issue,
    domain: bundle.domain,
    resolution_m: 4000,
    erc: cell.erc,
    erc_pct: cell.erc_pct,
    usdm: cell.usdm,
    horizons,
    targets,
  });
}

/** The latest forecast for the cell nearest a point, in a domain. */
export async function resolvePlace(domain: string, lat?: number, lon?: number): Promise<Place> {
  const idx = await getDomains();
  const issue = idx.issues[idx.issues.length - 1];
  const b = await getBundle(domain, issue);
  const meta = idx.domains[domain];
  const [clon, clat] = meta?.center ?? [b.cells[0].lon, b.cells[0].lat];
  const cell = nearestCell(b, lat ?? clat, lon ?? clon);
  if (!cell) throw new Error(`no forecast cells for ${domain}`);
  return placeFromCell(b, cell, idx.history_years);
}
