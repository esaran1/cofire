"""Census TIGER counties and USGS WBD HUC8 polygons; cell-to-basin join."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, box, shape

from cofire.model.config import (
    COLORADO_BBOX,
    COLORADO_FIPS,
    LARIMER_BBOX,
    Settings,
    get_settings,
)
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.http import USER_AGENT, SourceFetchError, download_file, sha256_file

LOGGER = logging.getLogger("cofire.data.boundaries")

TIGER_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
HUC8_QUERY = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4/query"
)


class BoundariesSource(DataSource):
    name = "boundaries"
    optional = False
    url = TIGER_URL

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note="not fetched")

    def _root(self) -> Path:
        return self.settings.processed_dir / "boundaries"

    def fetch(self, date_range: DateRange) -> Path:
        del date_range
        root = self._root()
        root.mkdir(parents=True, exist_ok=True)
        notes: list[str] = []
        try:
            self._fetch_counties(root)
            notes.append("counties=ok")
        except SourceFetchError as exc:
            LOGGER.warning("%s", exc)
            self._write_bbox_fallback(root)
            notes.append("counties=bbox-fallback")
        try:
            self._fetch_huc8(root)
            notes.append("huc8=ok")
        except SourceFetchError as exc:
            LOGGER.warning("%s", exc)
            notes.append("huc8=unavailable")
        self._join_cells(root)
        county_path = root / "counties.geojson"
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.OK if "counties=ok" in notes else SourceState.DEGRADED,
            url=self.url,
            path=str(root),
            checksum=sha256_file(county_path) if county_path.exists() else None,
            note="; ".join(notes),
        )
        return root

    def _fetch_counties(self, root: Path) -> None:
        dest = self.settings.raw_dir / "boundaries" / "cb_2023_us_county_500k.zip"
        download_file(TIGER_URL, dest, source="TIGER")
        gdf = gpd.read_file(f"zip://{dest}")
        gdf = gdf.to_crs(epsg=4326)
        co = gdf[gdf["STATEFP"] == COLORADO_FIPS].copy()
        if self.settings.dev_subset:
            co = co[co["GEOID"] == "08069"]
        out = root / "counties.geojson"
        co.to_file(out, driver="GeoJSON")
        LOGGER.info("wrote %s (%s counties)", out, len(co))

    def _write_bbox_fallback(self, root: Path) -> None:
        west, south, east, north = self.settings.bbox
        gdf = gpd.GeoDataFrame(
            {
                "GEOID": ["08069" if self.settings.dev_subset else "08"],
                "NAME": ["Larimer" if self.settings.dev_subset else "Colorado"],
                "geometry": [box(west, south, east, north)],
            },
            crs="EPSG:4326",
        )
        gdf.to_file(root / "counties.geojson", driver="GeoJSON")

    def _fetch_huc8(self, root: Path) -> None:
        west, south, east, north = self.settings.bbox
        params = {
            "where": "1=1",
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "huc8,name",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
        try:
            response = requests.get(HUC8_QUERY, params=params, timeout=90, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SourceFetchError("HUC8", HUC8_QUERY, str(exc)) from exc
        if not payload.get("features"):
            raise SourceFetchError("HUC8", HUC8_QUERY, "empty GeoJSON")
        gdf = gpd.GeoDataFrame.from_features(payload, crs="EPSG:4326")
        gdf.to_file(root / "huc8.geojson", driver="GeoJSON")

    def _join_cells(self, root: Path) -> None:
        grid_files = sorted((self.settings.processed_dir / "gridmet").glob("weekly_*.nc"))
        huc_path = root / "huc8.geojson"
        out = root / "cell_huc8.parquet"
        if not grid_files:
            return
        import xarray as xr

        ds = xr.open_dataset(grid_files[0])
        lats = ds["lat"].values
        lons = ds["lon"].values
        ds.close()
        huc_gdf = gpd.read_file(huc_path) if huc_path.exists() else None
        rows: list[dict[str, object]] = []
        for lat in lats:
            for lon in lons:
                pt = Point(float(lon), float(lat))
                huc8 = ""
                if huc_gdf is not None:
                    hit = huc_gdf[huc_gdf.contains(pt)]
                    if len(hit):
                        huc8 = str(hit.iloc[0].get("huc8") or hit.iloc[0].get("HUC8") or "")
                rows.append(
                    {
                        "cell_id": f"{float(lat):.4f}_{float(lon):.4f}",
                        "lat": float(lat),
                        "lon": float(lon),
                        "huc8": huc8,
                    }
                )
        pd.DataFrame(rows).to_parquet(out, index=False)

    def load(self) -> gpd.GeoDataFrame:
        path = self._root() / "counties.geojson"
        if not path.exists():
            west, south, east, north = LARIMER_BBOX if self.settings.dev_subset else COLORADO_BBOX
            return gpd.GeoDataFrame({"NAME": ["fallback"], "geometry": [box(west, south, east, north)]}, crs="EPSG:4326")
        return gpd.read_file(path)

    def status(self) -> SourceStatus:
        return self._last


def load_counties_geojson(settings: Settings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    path = settings.processed_dir / "boundaries" / "counties.geojson"
    if not path.exists():
        west, south, east, north = settings.bbox
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"NAME": "Larimer" if settings.dev_subset else "Colorado"},
                    "geometry": json.loads(gpd.GeoSeries([box(west, south, east, north)]).to_json())["features"][0]["geometry"]
                    if False
                    else shape(box(west, south, east, north)).__geo_interface__,
                }
            ],
        }
    return json.loads(path.read_text())  # type: ignore[no-any-return]
