"""gridMET daily via the Climatology Lab file server, spatially subset, weekly.

THREDDS NCSS (`thredds.northwestknowledge.net:8080`) is the historical
subsetting path but is often unreachable. Shipping fetch opens the yearly
NetCDF4 files at `https://www.northwestknowledge.net/metdata/data` with
HDF5 byte-range reads and clips to the configured bbox so CONUS cubes are
never stored. Weekly aggregation is local.

Processed one year and one variable at a time. Native grid (~1/24 degree,
~4 km) is clipped to the bbox (Larimer in subset mode).
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
import xarray as xr

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.http import SourceFetchError, download_file, sha256_file

LOGGER = logging.getLogger("cofire.data.gridmet")

# (folder, netcdf variable, weekly reducer)
GRIDMET_VARS: Final[dict[str, tuple[str, str, str]]] = {
    "pr": ("pr", "precipitation_amount", "sum"),
    "tmmx": ("tmmx", "air_temperature", "mean"),
    "tmmn": ("tmmn", "air_temperature", "mean"),
    "rmin": ("rmin", "relative_humidity", "mean"),
    "rmax": ("rmax", "relative_humidity", "mean"),
    "vs": ("vs", "wind_speed", "mean"),
    "vpd": ("vpd", "mean_vapor_pressure_deficit", "mean"),
    "erc": ("erc", "energy_release_component-g", "mean"),
    "bi": ("bi", "burning_index_g", "mean"),
    "fm100": ("fm100", "dead_fuel_moisture_100hr", "mean"),
    "fm1000": ("fm1000", "dead_fuel_moisture_1000hr", "mean"),
    "pet": ("pet", "potential_evapotranspiration", "sum"),
    "srad": ("srad", "surface_downwelling_shortwave_flux_in_air", "mean"),
}

FILE_BASE = "https://www.northwestknowledge.net/metdata/data"
NCSS_BASE = "http://thredds.northwestknowledge.net:8080/thredds/ncss/MET"
_WRITE_LOCK = threading.Lock()


def ncss_url(short: str, year: int, bbox: tuple[float, float, float, float], nc_var: str) -> str:
    west, south, east, north = bbox
    return (
        f"{NCSS_BASE}/{short}/{short}_{year}.nc"
        f"?var={nc_var}&west={west}&south={south}&east={east}&north={north}"
        f"&horizStride=1&accept=netcdf4"
    )


def file_url(short: str, year: int) -> str:
    return f"{FILE_BASE}/{short}_{year}.nc"


def _clip_to_bbox(da: xr.DataArray, bbox: tuple[float, float, float, float]) -> xr.DataArray:
    west, south, east, north = bbox
    if "crs" in da.dims:
        da = da.isel(crs=0)
    lat = da["lat"]
    if float(lat[0]) > float(lat[-1]):
        sub = da.sel(lon=slice(west, east), lat=slice(north, south))
    else:
        sub = da.sel(lon=slice(west, east), lat=slice(south, north))
    if int(sub.sizes.get("lat", 0)) == 0 or int(sub.sizes.get("lon", 0)) == 0:
        raise SourceFetchError("gridMET", FILE_BASE, f"empty spatial subset for bbox={bbox}")
    return sub


def _fetch_year_var(
    year: int,
    short: str,
    nc_var: str,
    bbox: tuple[float, float, float, float],
    dest: Path,
) -> str | None:
    """Write a bbox-clipped yearly cube. Return an error tag or None."""
    if dest.exists() and dest.stat().st_size > 0:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = file_url(short, year)
    full = dest.with_name(f".{short}_{year}.full.nc")
    try:
        download_file(url, full, source=f"gridMET:{short}:{year}", timeout=180)
        with xr.open_dataset(full, engine="h5netcdf") as ds:
            var = nc_var if nc_var in ds.data_vars else next(iter(ds.data_vars))
            sub = _clip_to_bbox(ds[var], bbox).load()
        out = sub.to_dataset(name=short)
        with _WRITE_LOCK:
            out.to_netcdf(dest, engine="h5netcdf")
        LOGGER.info("subset %s_%s -> %s (%s bytes)", short, year, dest, dest.stat().st_size)
        return None
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("gridMET %s_%s failed: %s", short, year, exc)
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink()
        return f"{short}_{year}"
    finally:
        if full.exists():
            full.unlink(missing_ok=True)


def _to_datetime_index(da_time: xr.DataArray) -> pd.DatetimeIndex:
    values = pd.to_datetime(da_time.values)
    if not isinstance(values, pd.DatetimeIndex):
        values = pd.DatetimeIndex(values)
    return values


class GridmetSource(DataSource):
    name = "gridMET"
    optional = False
    url = FILE_BASE

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last: SourceStatus = SourceStatus(
            name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note="not fetched"
        )

    def _year_var_path(self, year: int, short: str) -> Path:
        return self.settings.raw_dir / "gridmet" / f"{short}_{year}.nc"

    def _weekly_path(self, year: int) -> Path:
        return self.settings.processed_dir / "gridmet" / f"weekly_{year}.nc"

    def fetch(self, date_range: DateRange) -> Path:
        years = range(date_range.start.year, date_range.end.year + 1)
        bbox = self.settings.bbox
        jobs: list[tuple[int, str, str, Path]] = []
        fetched = 0
        for year in years:
            for short, (_folder, nc_var, _how) in GRIDMET_VARS.items():
                dest = self._year_var_path(year, short)
                if dest.exists() and dest.stat().st_size > 0:
                    fetched += 1
                    continue
                jobs.append((year, short, nc_var, dest))
        failed: list[str] = []
        workers = 3 if self.settings.dev_subset else 2
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [
                pool.submit(_fetch_year_var, year, short, nc_var, bbox, dest)
                for year, short, nc_var, dest in jobs
            ]
            for fut in as_completed(futs):
                tag = fut.result()
                if tag:
                    failed.append(tag)
                else:
                    fetched += 1
        weekly_root = self.settings.processed_dir / "gridmet"
        weekly_root.mkdir(parents=True, exist_ok=True)
        for year in years:
            self._aggregate_year(year)
        note = f"fetched={fetched} failed={failed[:8]} source=file-server-subset"
        state = SourceState.OK if not failed else (SourceState.DEGRADED if fetched else SourceState.UNAVAILABLE)
        checksum = None
        sample = self._weekly_path(date_range.end.year)
        if not sample.exists():
            sample = self._weekly_path(date_range.start.year)
        if sample.exists():
            checksum = sha256_file(sample)
        self._last = SourceStatus(
            name=self.name,
            state=state,
            url=FILE_BASE,
            path=str(weekly_root),
            checksum=checksum,
            note=note,
            extra={"failed": failed},
        )
        return weekly_root

    def _aggregate_year(self, year: int) -> Path:
        out = self._weekly_path(year)
        if out.exists() and out.stat().st_size > 0:
            return out
        arrays: dict[str, xr.DataArray] = {}
        for short, (_folder, nc_var, how) in GRIDMET_VARS.items():
            path = self._year_var_path(year, short)
            if not path.exists():
                continue
            ds = xr.open_dataset(path)
            time_name = "day" if "day" in ds.coords else "time"
            if nc_var not in ds:
                # Some NCSS extracts rename the variable to the short name.
                candidates = [v for v in ds.data_vars if v not in {"crs"}]
                if not candidates:
                    ds.close()
                    continue
                nc_var = str(candidates[0])
            da = ds[nc_var]
            da = da.rename({time_name: "time"}) if time_name != "time" else da
            if how == "sum":
                weekly = da.resample(time="W-TUE").sum()
            else:
                weekly = da.resample(time="W-TUE").mean()
            weekly = weekly.rename(short)
            arrays[short] = weekly
            ds.close()
        if not arrays:
            return out
        merged = xr.merge(list(arrays.values()), compat="override")
        merged.to_netcdf(out)
        LOGGER.info("wrote %s", out)
        return out

    def load(self) -> xr.Dataset:
        root = self.settings.processed_dir / "gridmet"
        files = sorted(root.glob("weekly_*.nc"))
        if not files:
            return xr.Dataset()
        return xr.open_mfdataset([str(p) for p in files], combine="by_coords")

    def load_year(self, year: int) -> xr.Dataset:
        path = self._weekly_path(year)
        if not path.exists():
            return xr.Dataset()
        return xr.open_dataset(path)

    def status(self) -> SourceStatus:
        return self._last


def grid_template(ds: xr.Dataset) -> pd.DataFrame:
    """One row per cell from a gridMET-shaped dataset."""
    if "lat" not in ds.coords or "lon" not in ds.coords:
        return pd.DataFrame(columns=["cell_id", "lat", "lon"])
    lats = ds["lat"].values
    lons = ds["lon"].values
    rows: list[dict[str, float | str]] = []
    for lat in lats:
        for lon in lons:
            lat_f = float(lat)
            lon_f = float(lon)
            rows.append({"cell_id": f"{lat_f:.4f}_{lon_f:.4f}", "lat": lat_f, "lon": lon_f})
    return pd.DataFrame(rows)


def cell_ids_from_coords(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat2, lon2 = np.meshgrid(lats, lons, indexing="ij")
    return np.char.add(np.char.add(np.char.mod("%.4f", lat2), "_"), np.char.mod("%.4f", lon2))
