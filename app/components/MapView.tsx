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
    map.on("load", () => pending.current());
    mapRef.current = map;
    // Exposed for automated screenshot capture: synthetic DOM events cannot
    // carry maplibre's lngLat, so the harness needs a handle on the map.
    (window as unknown as { __cofireMap?: maplibregl.Map }).__cofireMap = map;
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Fly to the area when it changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !bbox) return;
    map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: 40, duration: 600 },
    );
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
  }, [cells, layer, selectedId]);

  return <div ref={ref} data-testid="map" className="absolute inset-0 h-full w-full" />;
}
