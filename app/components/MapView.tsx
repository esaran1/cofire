"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { API } from "@/lib/api";

export function MapView({
  issue,
  horizon,
  layer,
  onClick,
}: {
  issue: string;
  horizon: string;
  layer: "drought" | "fire";
  onClick: (lat: number, lon: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: {
        version: 8,
        sources: {
          carto: {
            type: "raster",
            tiles: ["https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
            tileSize: 256,
            attribution: "© CARTO © OSM",
          },
        },
        layers: [{ id: "carto", type: "raster", source: "carto" }],
      },
      center: [-105.1, 40.58],
      zoom: 8,
    });
    map.on("click", (e) => clickRef.current(e.lngLat.lat, e.lngLat.lng));
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !issue) return;
    const srcId = "forecast";
    const url = `${API}/overlay/${issue}/${horizon}/${layer}.png`;
    const boundsUrl = `${API}/overlay/${issue}/${horizon}/${layer}.json`;
    fetch(boundsUrl)
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => {
        if (!map.getStyle() || !b) return;
        if (map.getLayer("forecast-img")) map.removeLayer("forecast-img");
        if (map.getSource(srcId)) map.removeSource(srcId);
        map.addSource(srcId, {
          type: "image",
          url,
          coordinates: [
            [b.west, b.north],
            [b.east, b.north],
            [b.east, b.south],
            [b.west, b.south],
          ],
        });
        map.addLayer({ id: "forecast-img", type: "raster", source: srcId, paint: { "raster-opacity": 0.65 } });
      })
      .catch(() => {
        /* overlay optional in fixture mode */
      });
    fetch(`${API}/forecast/grid?issue=${issue}&horizon=${horizon}&variable=${layer}`)
      .then((r) => r.json())
      .then((gj) => {
        if (!map.getStyle()) return;
        if (map.getLayer("cells")) map.removeLayer("cells");
        if (map.getSource("cells")) map.removeSource("cells");
        map.addSource("cells", { type: "geojson", data: gj });
        map.addLayer({
          id: "cells",
          type: "circle",
          source: "cells",
          paint: {
            "circle-radius": 6,
            "circle-color": layer === "fire" ? "#ff5a2a" : "#e6c15c",
            "circle-opacity": ["coalesce", ["get", "confidence"], 0.6],
          },
        });
      })
      .catch(() => undefined);
  }, [issue, horizon, layer]);

  return <div ref={ref} data-testid="map" className="absolute inset-0" />;
}
