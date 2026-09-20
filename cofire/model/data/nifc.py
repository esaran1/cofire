"""NIFC WFIGS fire perimeters. Evaluation / overlay only — never a training feature."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import requests

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.http import USER_AGENT, SourceFetchError, sha256_file

LOGGER = logging.getLogger("cofire.data.nifc")

# Current-year perimeters. History service is tried if this is empty.
CURRENT_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0/query"
)
HISTORY_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "InteragencyFirePerimeterHistory_All_Years_View/FeatureServer/0/query"
)


class NifcSource(DataSource):
    name = "NIFC WFIGS"
    optional = False
    url = CURRENT_URL

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note="not fetched")

    def _out_path(self) -> Path:
        return self.settings.processed_dir / "nifc" / "perimeters_2026.geojson"

    def fetch(self, date_range: DateRange) -> Path:
        del date_range
        gdf = self._query(CURRENT_URL, "poly_GISAcres > 1000 AND attr_POOState = 'US-CO'")
        if gdf.empty:
            gdf = self._query(
                HISTORY_URL,
                "GISACRES > 1000 AND (STATE = 'CO' OR POOSTATE = 'US-CO') AND FIREYEAR = 2026",
            )
        out = self._out_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        if gdf.empty:
            out.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.OK,
                url=self.url,
                path=str(out),
                checksum=sha256_file(out),
                records=0,
                note="zero qualifying 2026 CO perimeters > 1000 acres (not an error)",
            )
            return out
        gdf.to_file(out, driver="GeoJSON")
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.OK,
            url=self.url,
            path=str(out),
            checksum=sha256_file(out),
            records=int(len(gdf)),
            note="eval/overlay only; excluded from training features",
        )
        return out

    def _query(self, url: str, where: str) -> gpd.GeoDataFrame:
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultRecordCount": "2000",
        }
        try:
            response = requests.get(url, params=params, timeout=90, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("NIFC query failed %s: %s", url, exc)
            raise SourceFetchError(self.name, url, str(exc)) from exc
        features = payload.get("features") or []
        if not features:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        return gpd.GeoDataFrame.from_features(payload, crs="EPSG:4326")

    def load(self) -> gpd.GeoDataFrame:
        path = self._out_path()
        if not path.exists():
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        return gpd.read_file(path)

    def status(self) -> SourceStatus:
        return self._last
