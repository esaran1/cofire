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
      properties: { id: c.id, value: c.value },
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

// 0 to 100 on both layers: the forecast ERC percentile, or the chance in percent.
const RAMP: Record<"fire" | "drought", maplibregl.ExpressionSpecification> = {
  fire: ["interpolate", ["linear"], ["coalesce", ["get", "value"], 0], 0, "#efe9da", 50, "#e6a24a", 80, "#c8541f", 100, "#7d1d0c"],
  drought: ["interpolate", ["linear"], ["coalesce", ["get", "value"], 0], 0, "#efe9da", 25, "#e6c15c", 60, "#b8862b", 100, "#6b4a12"],
};

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
    map.on("load", () => {
      fit.current(false);
      pending.current();
    });
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
        map.addLayer({ id: "cells-fill", type: "fill", source: "cells", paint: { "fill-opacity": 0.72 } });
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
    if (map.isStyleLoaded()) draw();
    else pending.current = draw;
    // A new area's cells (and its card) have just arrived: fit once more, now
    // that the sheet's size is known. Horizon and layer changes keep the view.
    const key = cells.length ? `${cells[0].id}:${cells.length}` : "";
    if (key && key !== fittedFor.current) {
      fittedFor.current = key;
      setTimeout(() => fit.current(true), 50);
    }
  }, [cells, layer, selectedId]);

  return <div ref={ref} data-testid="map" className="absolute inset-0 h-full w-full" />;
}
