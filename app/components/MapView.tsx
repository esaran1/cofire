"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { basemapStyle, registerPmtiles, resolveMode } from "@/lib/basemap";
import { useT } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import type { Tracts } from "@/lib/tracts";

export type Layer = "drought" | "fire" | "burden";

export type MapCell = { id: string; lat: number; lon: number; value: number | null };

const HALF = 1 / 48; // half a gridMET cell, in degrees

/** A cell as the 4 km square it is, not a dot at its centre. */
function toGeoJSON(cells: MapCell[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: cells.map((c) => ({
      type: "Feature",
      id: c.id,
      // No `value` key at all when there is no number, so the layer can tell.
      properties: c.value === null ? { id: c.id } : { id: c.id, value: c.value },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [c.lon - HALF, c.lat - HALF],
            [c.lon + HALF, c.lat - HALF],
            [c.lon + HALF, c.lat + HALF],
            [c.lon - HALF, c.lat + HALF],
            [c.lon - HALF, c.lat - HALF],
          ],
        ],
      },
    })),
  };
}

// Fire: the forecast ERC percentile, where 50 is typical for the week. Most
// forecasts sit between 35 and 65 (the model pulls longer ranges toward
// typical), so the ramp diverges around 50: a 0-to-100 ramp drew every cell the
// same colour. Drought: the chance, in percent, of D2 or worse.
const RAMP: Record<"fire" | "drought", maplibregl.ExpressionSpecification> = {
  fire: ["interpolate", ["linear"], ["coalesce", ["get", "value"], 50], 20, "#8fb3c4", 40, "#d9e3e2", 50, "#efe9da", 60, "#eab26b", 75, "#cf6a2c", 90, "#8a2410"],
  drought: ["interpolate", ["linear"], ["coalesce", ["get", "value"], 0], 0, "#efe9da", 25, "#e6c15c", 60, "#b8862b", 100, "#6b4a12"],
};

// EnviroScreen: the statewide percentile score, 0 to 100.
const BURDEN_RAMP: maplibregl.ExpressionSpecification = ["interpolate", ["linear"], ["coalesce", ["get", "score"], 0], 0, "#eef0ea", 50, "#b9b3d6", 80, "#7b6db3", 100, "#3b2a78"];

export const LEGEND: Record<Layer, { stops: string[]; labels: [string, string, string]; title: MessageKey }> = {
  burden: { title: "legend.burden", stops: ["#eef0ea", "#b9b3d6", "#7b6db3", "#3b2a78"], labels: ["legend.less", "50", "legend.more"] },
  fire: { title: "legend.fire", stops: ["#8fb3c4", "#d9e3e2", "#efe9da", "#eab26b", "#cf6a2c", "#8a2410"], labels: ["legend.wetter", "legend.typical", "legend.drier"] },
  drought: { title: "legend.drought", stops: ["#efe9da", "#e6c15c", "#b8862b", "#6b4a12"], labels: ["0%", "50%", "100%"] },
};

/** What the colours mean, in the map's corner. */
export function MapLegend({ layer, empty = false }: { layer: Layer; empty?: boolean }) {
  const { t } = useT();
  const l = LEGEND[layer];
  const text = (k: string) => (k.startsWith("legend.") ? t(k as MessageKey) : k);
  return (
    <div data-testid="map-legend" className="pointer-events-none absolute left-3 top-3 z-10 rounded border border-rule bg-paper/95 px-3 py-2 text-[11px] text-ink-soft shadow-sm">
      <p className="text-ink">{t(l.title)}</p>
      <div className="mt-1 h-2 w-40 rounded-sm" style={{ background: `linear-gradient(to right, ${l.stops.join(", ")})` }} />
      <div className="mt-0.5 flex w-40 justify-between">
        {l.labels.map((k) => (
          <span key={k}>{text(k)}</span>
        ))}
      </div>
      {empty && layer === "drought" ? (
        <p className="mt-1 max-w-[10rem] text-ink" data-testid="map-legend-empty">
          {t("legend.empty")}
        </p>
      ) : null}
    </div>
  );
}

export function MapView({
  cells,
  bbox,
  layer,
  selectedId,
  onClick,
  label = "",
  tracts = null,
  selectedTract = null,
}: {
  /** Denver's EnviroScreen tracts, drawn when the layer is "burden". */
  tracts?: Tracts | null;
  selectedTract?: string | null;
  /** What the map shows, for screen readers; the panel's cell list is the accessible equivalent. */
  label?: string;
  cells: MapCell[];
  bbox: [number, number, number, number] | null;
  layer: Layer;
  selectedId?: string | null;
  onClick: (lat: number, lon: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;
  const pending = useRef<() => void>(() => undefined);
  // True once the style itself is parsed. The forecast cells need only that,
  // not the basemap tiles: `isStyleLoaded()` also waits for every tile source,
  // so with no network (make demo offline) the cells never drew.
  const styleReady = useRef(false);
  const bboxRef = useRef(bbox);
  bboxRef.current = bbox;

  // Fit the area into whatever size the map actually has. Called again on
  // load and on resize: on a phone the map's row gets its height after the
  // first fit, which left the area cut off in a corner.
  const fit = useRef((animate: boolean) => {
    const map = mapRef.current;
    const b = bboxRef.current;
    if (!map || !b) return;
    // The map controls float over the bottom of the map; keep the area in the
    // part they leave visible.
    const rect = map.getContainer().getBoundingClientRect();
    let bottom = 24;
    const controls = document.querySelector<HTMLElement>('[data-testid="time-scrubber"]');
    if (controls) {
      const overlap = rect.bottom - controls.getBoundingClientRect().top;
      bottom = Math.min(Math.max(24, overlap + 16), Math.max(24, rect.height - 120));
    }
    map.fitBounds(
      [
        [b[0], b[1]],
        [b[2], b[3]],
      ],
      { padding: { top: 24, left: 24, right: 24, bottom }, duration: animate ? 600 : 0 },
    );
  });
  const fittedFor = useRef("");

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    const mode = resolveMode();
    // The pmtiles protocol must be registered before the style asks for tiles,
    // or the first requests fail with an unsupported URL scheme.
    void registerPmtiles(mode).then(() => {
      if (cancelled || !ref.current || mapRef.current) return;
      cleanup = createMap(mode);
    });
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  function createMap(mode: ReturnType<typeof resolveMode>): () => void {
    const container = ref.current as HTMLDivElement;
    const map = new maplibregl.Map({
      container,
      style: basemapStyle(mode),
      center: [-104.99, 39.74],
      zoom: 9,
    });
    map.on("click", (e) => clickRef.current(e.lngLat.lat, e.lngLat.lng));
    const ready = () => {
      if (styleReady.current) return;
      styleReady.current = true;
      fit.current(false);
      pending.current();
    };
    map.on("style.load", ready);
    map.on("load", ready);
    mapRef.current = map;
    // Exposed for automated screenshot capture: synthetic DOM events cannot
    // carry maplibre's lngLat, so the harness needs a handle on the map.
    (window as unknown as { __cofireMap?: maplibregl.Map }).__cofireMap = map;
    let t: ReturnType<typeof setTimeout> | undefined;
    const ro = new ResizeObserver(() => {
      map.resize();
      clearTimeout(t);
      t = setTimeout(() => fit.current(false), 150);
    });
    ro.observe(container);
    return () => {
      clearTimeout(t);
      ro.disconnect();
      map.remove();
      mapRef.current = null;
      styleReady.current = false;
    };
  }

  // Fly to the area when it changes.
  useEffect(() => {
    fit.current(true);
  }, [bbox]);

  useEffect(() => {
    // The map is created once its tile protocol is registered, which can be
    // after the first cells arrive; then this draw waits in `pending`.
    const draw = () => {
      const map = mapRef.current;
      if (!map) return;
      const data = toGeoJSON(cells);
      const src = map.getSource("cells") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(data);
      } else {
        map.addSource("cells", { type: "geojson", data });
        // A cell without a number is left clear rather than coloured as zero.
        map.addLayer({
          id: "cells-fill",
          type: "fill",
          source: "cells",
          paint: { "fill-opacity": ["case", ["has", "value"], 0.72, 0] },
        });
        map.addLayer({
          id: "cells-line",
          type: "line",
          source: "cells",
          paint: { "line-color": "#17181b", "line-opacity": 0.12, "line-width": 0.5 },
        });
        map.addLayer({
          id: "cells-selected",
          type: "line",
          source: "cells",
          paint: { "line-color": "#17181b", "line-width": 2.5 },
          filter: ["==", ["get", "id"], ""],
        });
      }
      const burden = layer === "burden";
      if (!burden) map.setPaintProperty("cells-fill", "fill-color", RAMP[layer]);
      for (const id of ["cells-fill", "cells-line", "cells-selected"]) map.setLayoutProperty(id, "visibility", burden ? "none" : "visible");
      map.setFilter("cells-selected", ["==", ["get", "id"], selectedId ?? ""]);
      if (tracts) {
        if (!map.getSource("tracts")) {
          map.addSource("tracts", { type: "geojson", data: tracts as unknown as GeoJSON.FeatureCollection, promoteId: "geoid" });
          map.addLayer({ id: "tracts-fill", type: "fill", source: "tracts", paint: { "fill-color": BURDEN_RAMP, "fill-opacity": 0.7 } });
          map.addLayer({ id: "tracts-line", type: "line", source: "tracts", paint: { "line-color": "#17181b", "line-opacity": 0.25, "line-width": 0.6 } });
          map.addLayer({ id: "tracts-selected", type: "line", source: "tracts", paint: { "line-color": "#17181b", "line-width": 2.5 }, filter: ["==", ["get", "geoid"], ""] });
        }
        for (const id of ["tracts-fill", "tracts-line", "tracts-selected"]) map.setLayoutProperty(id, "visibility", burden ? "visible" : "none");
        map.setFilter("tracts-selected", ["==", ["get", "geoid"], selectedTract ?? ""]);
      }
    };
    // Draw now if the map and its style are ready; otherwise when they are.
    if (mapRef.current && styleReady.current) draw();
    else pending.current = draw;
    // A new area's cells (and its card) have just arrived: fit once more, now
    // that the sheet's size is known. Horizon and layer changes keep the view.
    const key = cells.length ? `${cells[0].id}:${cells.length}` : "";
    if (key && key !== fittedFor.current) {
      fittedFor.current = key;
      setTimeout(() => fit.current(true), 50);
    }
  }, [cells, layer, selectedId, tracts, selectedTract]);

  return (
    <>
      <div ref={ref} data-testid="map" role="region" aria-label={label || undefined} className="absolute inset-0 h-full w-full" />
      <MapLegend layer={layer} empty={cells.length > 0 && cells.every((c) => c.value === null)} />
    </>
  );
}
