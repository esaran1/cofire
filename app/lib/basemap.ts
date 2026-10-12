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
import type * as maplibregl from "maplibre-gl";

export type BasemapMode = "osm" | "selfhost" | "plain";

/** Identifies the project and a contact, as the OSM tile policy requires. */
export const TILE_UA = "COFIRE/0.7 (Congressional App Challenge 2026; contact: tech.mahi@gmail.com)";

/** Where self-hosted tiles live. A PMTiles extract of Colorado, served static. */
export const SELFHOST_PMTILES =
  process.env.NEXT_PUBLIC_PMTILES_URL ?? asset("/tiles/colorado.pmtiles");

export function resolveMode(): BasemapMode {
  const explicit = process.env.NEXT_PUBLIC_BASEMAP;
  if (explicit === "osm" || explicit === "selfhost" || explicit === "plain") return explicit;
  // auto: OSM for local dev; self-hosted tiles for a deployed build when the
  // archive was built, and a plain background when it was not.
  if (process.env.NODE_ENV !== "production") return "osm";
  return process.env.NEXT_PUBLIC_HAS_TILES ? "selfhost" : "plain";
}

/** No basemap: the paper colour, so the forecast cells still read. */
function plainStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [{ id: "bg", type: "background", paint: { "background-color": "#eceae2" } }],
  } as unknown as maplibregl.StyleSpecification;
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
 * Self-hosted vector style from the Protomaps extract of Colorado
 * (app/public/tiles/colorado.pmtiles, zooms 0 to 13, overzoomed beyond).
 * Dark and low contrast, built from the app's ink tokens, so the forecast
 * cells carry the colour; place names in a muted light grey with a dark halo,
 * legible on a phone. Glyphs are self-hosted (Noto Sans Regular, OFL), so the
 * deployed map needs no third-party server.
 */
const INK = "#17181b";
const LAND = "#1f2126";
const MUTED = "#2a2d33";
const ROAD = "#353941";
const ROAD_MAJOR = "#454a54";
const WATER = "#142130";
const LABEL = "#b9bcc3";

function glyphsUrl(): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  return `${origin}${asset("/fonts/{fontstack}/{range}.pbf")}`;
}

/** Ids of the layers drawn from the tile archive, hidden if it fails to load. */
export const BASEMAP_LAYERS = ["earth", "landcover", "landuse", "water", "roads-minor", "roads-major", "boundaries", "buildings", "places"];

function selfhostStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    glyphs: glyphsUrl(),
    sources: {
      basemap: {
        type: "vector",
        url: `pmtiles://${SELFHOST_PMTILES}`,
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · © <a href="https://protomaps.com">Protomaps</a>',
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": INK } },
      { id: "earth", type: "fill", source: "basemap", "source-layer": "earth", paint: { "fill-color": LAND } },
      { id: "landcover", type: "fill", source: "basemap", "source-layer": "landcover", paint: { "fill-color": MUTED, "fill-opacity": 0.35 } },
      { id: "landuse", type: "fill", source: "basemap", "source-layer": "landuse", paint: { "fill-color": MUTED, "fill-opacity": 0.45 } },
      { id: "water", type: "fill", source: "basemap", "source-layer": "water", paint: { "fill-color": WATER } },
      {
        id: "roads-minor", type: "line", source: "basemap", "source-layer": "roads",
        filter: ["!", ["in", ["get", "kind"], ["literal", ["highway", "major_road"]]]],
        minzoom: 11,
        paint: { "line-color": ROAD, "line-width": ["interpolate", ["linear"], ["zoom"], 11, 0.3, 14, 1.2] },
      },
      {
        id: "roads-major", type: "line", source: "basemap", "source-layer": "roads",
        filter: ["in", ["get", "kind"], ["literal", ["highway", "major_road"]]],
        paint: { "line-color": ROAD_MAJOR, "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 10, 1, 14, 2.4] },
      },
      {
        id: "boundaries", type: "line", source: "basemap", "source-layer": "boundaries",
        paint: { "line-color": "#565c67", "line-width": 0.8, "line-dasharray": [3, 2] },
      },
      { id: "buildings", type: "fill", source: "basemap", "source-layer": "buildings", minzoom: 13, paint: { "fill-color": MUTED, "fill-opacity": 0.6 } },
      {
        id: "places", type: "symbol", source: "basemap", "source-layer": "places",
        filter: ["==", ["get", "kind"], "locality"],
        layout: {
          "text-field": ["coalesce", ["get", "name:en"], ["get", "name"]],
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 6, 11, 10, 13, 13, 15],
          "text-max-width": 8,
        },
        paint: { "text-color": LABEL, "text-halo-color": INK, "text-halo-width": 1.4 },
      },
    ],
  } as unknown as maplibregl.StyleSpecification;
}

export function basemapStyle(mode: BasemapMode = resolveMode()): maplibregl.StyleSpecification {
  if (mode === "plain") return plainStyle();
  return mode === "selfhost" ? selfhostStyle() : osmStyle();
}

/** Register the pmtiles:// protocol lazily; no-op when not self-hosting. */
export async function registerPmtiles(mode: BasemapMode = resolveMode()): Promise<void> {
  if (mode !== "selfhost") return;
  try {
    const pmtiles = await import("pmtiles");
    const maplibregl = await import("maplibre-gl");
    const protocol = new pmtiles.Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);
  } catch {
    // pmtiles not installed or archive absent: the background layer still
    // renders and the forecast overlay is unaffected.
  }
}
