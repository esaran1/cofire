"""USGS 3DEP elevation aggregated to gridMET cells: mean and roughness (std)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
import requests
import xarray as xr
from rasterio.warp import Resampling, reproject

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.http import USER_AGENT, SourceFetchError, sha256_file

LOGGER = logging.getLogger("cofire.data.elevation")

EXPORT_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"


class ElevationSource(DataSource):
    name = "USGS 3DEP"
    optional = False
    url = EXPORT_URL

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note="not fetched")

    def _raw_path(self) -> Path:
        # Downloaded with the bbox baked in, so scope it per subset (same trap as
        # the gridMET raw cache).
        name = "3dep.tif"
        if self.settings.dev_subset and self.settings.subset_name != "larimer":
            name = f"3dep_{self.settings.subset_name}.tif"
        return self.settings.raw_dir / "elevation" / name

    def _out_path(self) -> Path:
        return self.settings.processed_dir / "elevation" / "grid.nc"

    def fetch(self, date_range: DateRange) -> Path:
        del date_range
        west, south, east, north = self.settings.bbox
        width = max(int((east - west) / 0.0009), 64)
        height = max(int((north - south) / 0.0009), 64)
        params = {
            "bbox": f"{west},{south},{east},{north}",
            "bboxSR": "4326",
            "size": f"{width},{height}",
            "imageSR": "4326",
            "format": "tiff",
            "pixelType": "F32",
            "interpolation": "RSP_BilinearInterpolation",
            "f": "image",
        }
        dest = self._raw_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            try:
                response = requests.get(EXPORT_URL, params=params, timeout=120, headers={"User-Agent": USER_AGENT})
                response.raise_for_status()
                ctype = response.headers.get("Content-Type", "")
                magic = response.content[:2]
                if "tiff" not in ctype and magic not in {b"II", b"MM"}:
                    raise SourceFetchError(self.name, EXPORT_URL, f"unexpected content-type {ctype}")
                dest.write_bytes(response.content)
            except (requests.RequestException, SourceFetchError) as exc:
                LOGGER.warning("%s", exc)
                self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note=str(exc))
                return self._out_path()
        try:
            self._aggregate()
            path = self._out_path()
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.OK,
                url=self.url,
                path=str(path),
                checksum=sha256_file(path),
                note="mean and roughness on gridMET cells",
            )
            return path
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("elevation aggregate failed: %s", exc)
            self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note=str(exc))
            return self._out_path()

    def _aggregate(self) -> None:
        grid_files = sorted((self.settings.processed_dir / "gridmet").glob("weekly_*.nc"))
        if not grid_files:
            raise RuntimeError("gridMET weekly cube missing")
        template = xr.open_dataset(grid_files[0])
        lats = template["lat"].values
        lons = template["lon"].values
        template.close()
        with rasterio.open(self._raw_path()) as src:
            dem = src.read(1).astype(np.float32)
            dem_transform = src.transform
            dem_crs = src.crs
        # Reproject DEM onto a finer grid covering the template, then reduce.
        pixel_h = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 0.0416667
        pixel_w = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 0.0416667
        factor = 8
        dst_h = len(lats) * factor
        dst_w = len(lons) * factor
        west = float(lons.min()) - pixel_w / 2
        north = float(lats.max()) + pixel_h / 2
        from rasterio.transform import from_origin

        dst_transform = from_origin(west, north, pixel_w / factor, pixel_h / factor)
        resampled = np.full((dst_h, dst_w), np.nan, dtype=np.float32)
        reproject(
            source=dem,
            destination=resampled,
            src_transform=dem_transform,
            src_crs=dem_crs or "EPSG:4326",
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            resampling=Resampling.bilinear,
        )
        mean = np.zeros((len(lats), len(lons)), dtype=np.float32)
        rough = np.zeros((len(lats), len(lons)), dtype=np.float32)
        for yi in range(len(lats)):
            for xi in range(len(lons)):
                block = resampled[yi * factor : (yi + 1) * factor, xi * factor : (xi + 1) * factor]
                valid = block[np.isfinite(block)]
                if valid.size == 0:
                    mean[yi, xi] = np.nan
                    rough[yi, xi] = np.nan
                else:
                    mean[yi, xi] = float(valid.mean())
                    rough[yi, xi] = float(valid.std())
        ds = xr.Dataset(
            {"elev_mean": (("lat", "lon"), mean), "elev_roughness": (("lat", "lon"), rough)},
            coords={"lat": lats, "lon": lons},
        )
        out = self._out_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(out)

    def load(self) -> xr.Dataset:
        path = self._out_path()
        if not path.exists():
            return xr.Dataset()
        return xr.open_dataset(path)

    def status(self) -> SourceStatus:
        return self._last
