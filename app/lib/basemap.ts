/**
 * Basemap sources. Keyless in every mode - the zero-API-key requirement is a
 * hard constraint of the project, not a preference.
 *
 * Policy note that drove this abstraction: the OSM Foundation tile servers are
 * a donated-bandwidth service intended for modest use. Their tile usage policy
 * requires a descriptive identifying User-Agent/Referer and discourages
 * app-embedded and bulk usage. That makes OSM fine for a local demo on one
 * laptop and **not** fine for a deployed build, so a deployed build must serve
 * its own tiles.
 *
 * Switch with NEXT_PUBLIC_BASEMAP = "osm" | "selfhost" | "auto" (default auto:
 * osm in dev, selfhost in a production build).
 */

import { asset } from "./asset";
import type maplibregl from "maplibre-gl";

export type BasemapMode = "osm" | "selfhost";

/** Identifies the project and a contact, as the OSM tile policy requires. */
export const TILE_UA = "COFIRE/0.7 (Congressional App Challenge 2026; contact: tech.mahi@gmail.com)";

/** Where self-hosted tiles live. A PMTiles extract of Colorado, served static. */
export const SELFHOST_PMTILES =
  process.env.NEXT_PUBLIC_PMTILES_URL ?? asset("/tiles/colorado.pmtiles");

export function resolveMode(): BasemapMode {
  const explicit = process.env.NEXT_PUBLIC_BASEMAP;
  if (explicit === "osm" || explicit === "selfhost") return explicit;
  // auto: OSM for local dev, self-hosted for a deployed build.
  return process.env.NODE_ENV === "production" ? "selfhost" : "osm";
}

/** Raster OSM style. Local demo only - see the policy note above. */
function osmStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap" }],
  } as unknown as maplibregl.StyleSpecification;
}

/**
 * Self-hosted vector style from a PMTiles extract. Needs the pmtiles protocol
 * registered (see registerPmtiles). Falls back to a plain background if the
 * archive is missing, so the forecast layer still renders.
 */
function selfhostStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "vector",
        url: `pmtiles://${SELFHOST_PMTILES}`,
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, © <a href="https://protomaps.com">Protomaps</a>',
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0d0f14" } },
      {
        id: "water",
        type: "fill",
        source: "basemap",
        "source-layer": "water",
        paint: { "fill-color": "#16202e" },
      },
      {
        id: "landuse",
        type: "fill",
        source: "basemap",
        "source-layer": "landuse",
        paint: { "fill-color": "#141a17", "fill-opacity": 0.6 },
      },
      {
        id: "roads",
        type: "line",
        source: "basemap",
        "source-layer": "roads",
        paint: { "line-color": "#2a2f3a", "line-width": 0.6 },
      },
      {
        id: "boundaries",
        type: "line",
        source: "basemap",
        "source-layer": "boundaries",
        paint: { "line-color": "#3a4150", "line-width": 0.8 },
      },
    ],
  } as unknown as maplibregl.StyleSpecification;
}

export function basemapStyle(mode: BasemapMode = resolveMode()): maplibregl.StyleSpecification {
  return mode === "selfhost" ? selfhostStyle() : osmStyle();
}

/** Register the pmtiles:// protocol lazily; no-op when not self-hosting. */
export async function registerPmtiles(mode: BasemapMode = resolveMode()): Promise<void> {
  if (mode !== "selfhost") return;
  try {
    const pmtiles = await import("pmtiles");
    const maplibregl = (await import("maplibre-gl")).default;
    const protocol = new pmtiles.Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);
  } catch {
    // pmtiles not installed or archive absent: the background layer still
    // renders and the forecast overlay is unaffected.
  }
}
