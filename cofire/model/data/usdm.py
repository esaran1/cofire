"""US Drought Monitor weekly categories rasterized onto the gridMET grid.

Primary: yearly shapefile zip from droughtmonitor.unl.edu.
Fallback: UNL county-area statistics assigned uniformly to cells in the county
(real observations, coarser spatial support — marked degraded, never fabricated).
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
import xarray as xr
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.dates import tuesdays
from cofire.model.http import USER_AGENT, SourceFetchError, download_file, sha256_file

LOGGER = logging.getLogger("cofire.data.usdm")

YEARLY_URL = "https://droughtmonitor.unl.edu/data/shapefiles_m/{year}_USDM_M.zip"
WEEKLY_URL = "https://droughtmonitor.unl.edu/data/shapefiles_m/{stem}_M.zip"
COUNTY_API = (
    "https://usdmdataservices.unl.edu/api/CountyStatistics/"
    "GetDroughtSeverityStatisticsByAreaPercent"
)


def _week_stems(d: date) -> list[str]:
    iso = d.strftime("%Y%m%d")
    return [f"USDM_{iso}", f"usdm_{iso}"]


class UsdmSource(DataSource):
    name = "US Drought Monitor"
    optional = False
    url = "https://droughtmonitor.unl.edu/data/shapefiles_m/"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note="not fetched")

    def _raster_path(self) -> Path:
        return self.settings.processed_dir / "usdm" / "weekly.nc"

    def fetch(self, date_range: DateRange) -> Path:
        years = range(date_range.start.year, date_range.end.year + 1)
        raw = self.settings.raw_dir / "usdm"
        raw.mkdir(parents=True, exist_ok=True)
        got_zip = False
        for year in years:
            dest = raw / f"{year}_USDM_M.zip"
            if dest.exists() and dest.stat().st_size > 0:
                got_zip = True
                continue
            url = YEARLY_URL.format(year=year)
            try:
                download_file(url, dest, source=f"USDM:{year}")
                got_zip = True
            except SourceFetchError as exc:
                LOGGER.warning("%s", exc)
        grid_path = self.settings.processed_dir / "gridmet"
        weekly_files = sorted(grid_path.glob("weekly_*.nc"))
        if not weekly_files:
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.UNAVAILABLE,
                url=self.url,
                note="gridMET weekly cube missing; rasterize skipped",
            )
            return self._raster_path()
        template = xr.open_dataset(weekly_files[0])
        try:
            if got_zip:
                self._rasterize_zips(raw, template, date_range)
            else:
                self._county_fallback(template, date_range)
        finally:
            template.close()
        path = self._raster_path()
        if path.exists():
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.OK if got_zip else SourceState.DEGRADED,
                url=self.url,
                path=str(path),
                checksum=sha256_file(path),
                note="yearly shapefiles rasterized" if got_zip else "county-area statistics fallback",
            )
        return path

    def _rasterize_zips(self, raw: Path, template: xr.Dataset, date_range: DateRange) -> None:
        lats = template["lat"].values
        lons = template["lon"].values
        weeks = tuesdays(date_range.start, date_range.end)
        cube = np.zeros((len(weeks), len(lats), len(lons)), dtype=np.int8)
        west, south, east, north = self.settings.bbox
        clip = box(west, south, east, north)
        pixel_h = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 0.0416667
        pixel_w = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 0.0416667
        # gridMET lat is north-to-south.
        transform = from_origin(float(lons.min()) - pixel_w / 2, float(lats.max()) + pixel_h / 2, pixel_w, pixel_h)
        shape = (len(lats), len(lons))
        found = 0
        for year in range(date_range.start.year, date_range.end.year + 1):
            zpath = raw / f"{year}_USDM_M.zip"
            if not zpath.exists():
                continue
            try:
                with zipfile.ZipFile(zpath) as zf:
                    names = zf.namelist()
                    for week_i, week in enumerate(weeks):
                        if week.year != year:
                            continue
                        member = self._match_week_member(names, week)
                        if member is None:
                            continue
                        try:
                            if member.lower().endswith(".zip"):
                                inner_bytes = io.BytesIO(zf.read(member))
                                with zipfile.ZipFile(inner_bytes) as inner:
                                    shp_names = [n for n in inner.namelist() if n.lower().endswith(".shp")]
                                    if not shp_names:
                                        continue
                                    gdf = self._read_shp_from_zip(inner, shp_names[0])
                            else:
                                gdf = self._read_shp_from_zip(zf, member)
                        except (zipfile.BadZipFile, OSError) as exc:
                            LOGGER.warning("USDM week %s unreadable: %s", week, exc)
                            continue
                        if gdf.empty:
                            continue
                        gdf = gdf.to_crs(epsg=4326)
                        gdf = gdf[gdf.intersects(clip)]
                        if gdf.empty:
                            continue
                        dm_col = self._dm_column(gdf)
                        gdf = gdf.sort_values(dm_col)
                        geoms = [
                            (mapping(geom), int(cat))
                            for geom, cat in zip(gdf.geometry, gdf[dm_col], strict=False)
                            if geom is not None and not geom.is_empty
                        ]
                        if not geoms:
                            continue
                        raster = rasterize(
                            geoms,
                            out_shape=shape,
                            transform=transform,
                            fill=0,
                            dtype="int16",
                            all_touched=False,
                        )
                        cube[week_i] = np.clip(raster, 0, 4).astype(np.int8)
                        found += 1
            except (zipfile.BadZipFile, OSError) as exc:
                LOGGER.warning("USDM zip %s unreadable: %s", zpath, exc)
        ds = xr.Dataset(
            {"usdm": (("time", "lat", "lon"), cube)},
            coords={
                "time": pd.to_datetime(weeks),
                "lat": lats,
                "lon": lons,
            },
        )
        ds["usdm"].attrs["long_name"] = "USDM category D0-D4; None mapped to 0"
        out = self._raster_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(out)
        LOGGER.info("USDM raster weeks with polygons=%s -> %s", found, out)

    def _county_fallback(self, template: xr.Dataset, date_range: DateRange) -> None:
        fips = self.settings.county_fips or "08069"
        params = {
            "aoi": fips,
            "startdate": date_range.start.strftime("%m/%d/%Y"),
            "enddate": date_range.end.strftime("%m/%d/%Y"),
            "statisticsType": "1",
        }
        try:
            response = requests.get(
                COUNTY_API,
                params=params,
                timeout=60,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            response.raise_for_status()
            rows = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SourceFetchError("USDM-county", COUNTY_API, str(exc)) from exc
        weeks = tuesdays(date_range.start, date_range.end)
        by_date: dict[date, int] = {}
        for row in rows if isinstance(rows, list) else []:
            raw_date = str(row.get("MapDate") or row.get("ValidStart") or "")
            parsed = _parse_usdm_date(raw_date)
            if parsed is None:
                continue
            cat = _dominant_category(row)
            by_date[parsed] = cat
        lats = template["lat"].values
        lons = template["lon"].values
        cube = np.zeros((len(weeks), len(lats), len(lons)), dtype=np.int8)
        for i, week in enumerate(weeks):
            cube[i, :, :] = by_date.get(week, 0)
        ds = xr.Dataset(
            {"usdm": (("time", "lat", "lon"), cube)},
            coords={"time": pd.to_datetime(weeks), "lat": lats, "lon": lons},
        )
        ds["usdm"].attrs["note"] = "county-level USDM assigned to every cell in the county"
        out = self._raster_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(out)
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.DEGRADED,
            url=COUNTY_API,
            path=str(out),
            checksum=sha256_file(out),
            note="county-area statistics fallback; spatial resolution is county, not grid",
        )

    def load(self) -> xr.Dataset:
        path = self._raster_path()
        if not path.exists():
            return xr.Dataset()
        return xr.open_dataset(path)

    def status(self) -> SourceStatus:
        return self._last

    @staticmethod
    def _dm_column(gdf: gpd.GeoDataFrame) -> str:
        for col in ("DM", "dm", "DMValue", "USDM"):
            if col in gdf.columns:
                return col
        raise SourceFetchError("USDM", "", "shapefile missing DM category column")

    @staticmethod
    def _match_week_member(names: list[str], week: date) -> str | None:
        key = week.strftime("%Y%m%d")
        lower = {n.lower(): n for n in names}
        for n_lower, orig in lower.items():
            if key in n_lower and (n_lower.endswith(".zip") or n_lower.endswith(".shp")):
                return orig
        return None

    @staticmethod
    def _match_week_shp(names: list[str], week: date) -> str | None:
        return UsdmSource._match_week_member(names, week)

    @staticmethod
    def _read_shp_from_zip(zf: zipfile.ZipFile, shp_name: str) -> gpd.GeoDataFrame:
        """Read a shapefile that lives inside a zip by extracting siblings to a buffer dir."""
        stem = shp_name.rsplit(".", 1)[0]
        prefix = stem.split("/")[-1] if "/" in stem else stem
        members = [n for n in zf.namelist() if prefix.lower() in n.lower()]
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as inner:
            for member in members:
                inner.writestr(Path(member).name, zf.read(member))
        bio.seek(0)
        return gpd.read_file(bio)


def _parse_usdm_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y", "%-m/%-d/%Y"):
        try:
            return datetime.strptime(raw[:10] if "-" in raw or "/" in raw else raw[:8], fmt.replace("%-m", "%m").replace("%-d", "%d")).date()
        except ValueError:
            continue
    return None


def _dominant_category(row: dict[str, object]) -> int:
    """Highest USDM category with at least 25% area; else the max-area bin. None/D0 → 0."""
    mapping_keys = [
        ("D4", 4),
        ("D3", 3),
        ("D2", 2),
        ("D1", 1),
        ("D0", 0),
        ("None", 0),
    ]
    best_cat = 0
    best_area = -1.0
    for key, cat in mapping_keys:
        val = row.get(key) or row.get(f"{key}Pct") or row.get(key.lower())
        try:
            area = float(str(val).replace("%", "") or 0)
        except ValueError:
            area = 0.0
        if area >= 25.0 and cat >= best_cat:
            best_cat = cat
            best_area = area
        elif area > best_area and best_area < 25.0:
            best_area = area
            best_cat = cat
    return int(np.clip(best_cat, 0, 4))


# Keep rasterio imported so mypy sees the dependency used for rasterize transform.
_ = rasterio.__version__
