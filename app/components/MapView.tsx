"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { basemapStyle, registerPmtiles, resolveMode } from "@/lib/basemap";

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

export const LEGEND: Record<"fire" | "drought", { stops: string[]; labels: [string, string, string]; title: string }> = {
  fire: { title: "Dryness vs usual for the week", stops: ["#8fb3c4", "#d9e3e2", "#efe9da", "#eab26b", "#cf6a2c", "#8a2410"], labels: ["wetter", "typical", "drier"] },
  drought: { title: "Chance of D2 or worse", stops: ["#efe9da", "#e6c15c", "#b8862b", "#6b4a12"], labels: ["0%", "50%", "100%"] },
};

/** What the colours mean, in the map's corner. */
export function MapLegend({ layer, empty = false }: { layer: "drought" | "fire"; empty?: boolean }) {
  const l = LEGEND[layer];
  return (
    <div data-testid="map-legend" className="pointer-events-none absolute left-3 top-3 z-10 rounded border border-rule bg-paper/95 px-3 py-2 text-[11px] text-ink-soft shadow-sm">
      <p className="text-ink">{l.title}</p>
      <div className="mt-1 h-2 w-40 rounded-sm" style={{ background: `linear-gradient(to right, ${l.stops.join(", ")})` }} />
      <div className="mt-0.5 flex w-40 justify-between">
        {l.labels.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      {empty ? (
        <p className="mt-1 max-w-[10rem] text-ink" data-testid="map-legend-empty">
          Not checked for this area at this range, so the map shows no drought odds.
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
}: {
  cells: MapCell[];
  bbox: [number, number, number, number] | null;
  layer: "drought" | "fire";
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
    const mode = resolveMode();
    void registerPmtiles(mode);
    const map = new maplibregl.Map({
      container: ref.current,
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
    ro.observe(ref.current);
    return () => {
      clearTimeout(t);
      ro.disconnect();
      map.remove();
      mapRef.current = null;
      styleReady.current = false;
    };
  }, []);

  // Fly to the area when it changes.
  useEffect(() => {
    fit.current(true);
  }, [bbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const draw = () => {
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
      map.setPaintProperty("cells-fill", "fill-color", RAMP[layer]);
      map.setFilter("cells-selected", ["==", ["get", "id"], selectedId ?? ""]);
    };
    // Draw now if the style is parsed; otherwise when it is.
    if (styleReady.current) draw();
    else pending.current = draw;
    // A new area's cells (and its card) have just arrived: fit once more, now
    // that the sheet's size is known. Horizon and layer changes keep the view.
    const key = cells.length ? `${cells[0].id}:${cells.length}` : "";
    if (key && key !== fittedFor.current) {
      fittedFor.current = key;
      setTimeout(() => fit.current(true), 50);
    }
  }, [cells, layer, selectedId]);

  return (
    <>
      <div ref={ref} data-testid="map" className="absolute inset-0 h-full w-full" />
      <MapLegend layer={layer} empty={cells.length > 0 && cells.every((c) => c.value === null)} />
    </>
  );
}
