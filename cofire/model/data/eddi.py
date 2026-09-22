"""EDDI (Evaporative Demand Drought Index), NOAA PSL. HAND-REWRITE.

Product: EDDI CONUS archive, ESRI ASCII grids, keyless, daily files at several
accumulation windows, 1980 to present.

Native resolution is 0.125 degrees, roughly 12 km, against gridMET's 4 km. It is
upsampled onto the gridMET grid and recorded as coarser support in docs/DATA.md.
Upsampling does not create information; three gridMET cells inside one EDDI cell
carry the same value, and that is stated rather than hidden.

Budget note: the archive offers no subsetting endpoint, no compression, and no
tiled format, so each file costs its full 1.77 MB whatever the domain. That
fixed cost is why only one accumulation window is fetched. The window chosen,
04wk, matches the ESI 4-week compositing period, so the two new sources describe
the same timescale from the water-supply and evaporative-demand sides.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.data.ledger import BudgetExceeded, get_ledger
from cofire.model.dates import tuesdays

LOGGER = logging.getLogger("cofire.data.eddi")

BASE = "https://downloads.psl.noaa.gov/Projects/EDDI/CONUS_archive/data"
WINDOW = "04wk"
BYTES_PER_FILE = 1_767_229


def eddi_url(d: date, window: str = WINDOW) -> str:
    return f"{BASE}/{d.year}/EDDI_ETrs_{window}_{d.strftime('%Y%m%d')}.asc"


def parse_ascii_grid(text: str) -> tuple[np.ndarray, dict[str, float]]:
    """Parse an ESRI ASCII grid into an array plus its header.

    Rows run north to south, which is the opposite of the ascending-latitude
    convention used elsewhere in this project, so the caller must flip.
    """
    lines = text.splitlines()
    hdr: dict[str, float] = {}
    i = 0
    for i, line in enumerate(lines):  # noqa: B007
        parts = line.split()
        if len(parts) != 2:
            break
        try:
            hdr[parts[0].lower()] = float(parts[1])
        except ValueError:
            break
    body = "\n".join(lines[i:])
    arr = np.fromstring(body, sep=" ", dtype="float32")
    ncols, nrows = int(hdr["ncols"]), int(hdr["nrows"])
    arr = arr[: ncols * nrows].reshape(nrows, ncols)
    nodata = hdr.get("nodata_value", -9999.0)
    arr[np.isclose(arr, nodata)] = np.nan
    return arr, hdr


def grid_axes(hdr: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """Cell-centre axes, latitude ascending."""
    ncols, nrows = int(hdr["ncols"]), int(hdr["nrows"])
    cs = hdr["cellsize"]
    lon = hdr["xllcorner"] + cs * (np.arange(ncols) + 0.5)
    lat = hdr["yllcorner"] + cs * (np.arange(nrows) + 0.5)
    return lat, lon


class EddiSource(DataSource):
    name = "NOAA EDDI 4-week"
    url = BASE
    optional = False

    def __init__(self, settings: Settings | None = None, window: str = WINDOW) -> None:
        self.settings = settings or get_settings()
        self.window = window
        self._last: SourceStatus | None = None

    def _out_path(self) -> Path:
        return self.settings.processed_dir / "eddi" / f"weekly_{self.window}.nc"

    def fetch(self, date_range: DateRange) -> Path:
        import requests

        from cofire.model.http import USER_AGENT

        out = self._out_path()
        if out.exists() and out.stat().st_size > 0:
            LOGGER.info("EDDI cache hit at %s", out)
            self._last = SourceStatus(
                name=self.name, state=SourceState.OK, url=self.url, path=str(out), note="cache hit"
            )
            return out

        ledger = get_ledger()
        weeks = list(tuesdays(date_range.start, date_range.end))
        if not ledger.project_series(self.name, BYTES_PER_FILE, len(weeks)):
            raise BudgetExceeded(
                f"{self.name}: {len(weeks)} files x {BYTES_PER_FILE / 1e6:.2f} MB "
                f"exceeds the remaining {ledger.remaining_bytes / 1e6:.0f} MB"
            )

        w, s, e, n = self.settings.bbox
        frames: list[np.ndarray] = []
        times: list[pd.Timestamp] = []
        lat_sub = lon_sub = None
        fetched = failed = 0

        for d in weeks:
            url = eddi_url(d, self.window)
            try:
                r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
                if r.status_code >= 400:
                    failed += 1
                    continue
                # Bytes crossed the wire; clipping afterwards does not refund them.
                ledger.record(self.name, url, len(r.content), f"{d.isoformat()} full CONUS")
                arr, hdr = parse_ascii_grid(r.text)
                lat, lon = grid_axes(hdr)
                arr = arr[::-1]  # ASCII grids run north to south
                if lat_sub is None:
                    yi = np.where((lat >= s) & (lat <= n))[0]
                    xi = np.where((lon >= w) & (lon <= e))[0]
                    if yi.size == 0 or xi.size == 0:
                        raise ValueError("domain falls outside the EDDI CONUS grid")
                    lat_sub, lon_sub = lat[yi], lon[xi]
                    _yi, _xi = yi, xi
                frames.append(arr[np.ix_(_yi, _xi)])
                times.append(pd.Timestamp(d))
                fetched += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                LOGGER.warning("EDDI %s failed: %s", d, exc)
                if failed > 10 and fetched == 0:
                    break

        if not frames:
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.UNAVAILABLE,
                url=self.url,
                note=f"no EDDI grids retrieved ({failed} failures)",
            )
            raise RuntimeError("EDDI unavailable")

        da = xr.DataArray(
            np.stack(frames),
            dims=("time", "lat", "lon"),
            coords={"time": pd.DatetimeIndex(times), "lat": lat_sub, "lon": lon_sub},
            name=f"eddi_{self.window}",
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        da.to_dataset().to_netcdf(out)
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.OK if failed == 0 else SourceState.DEGRADED,
            url=self.url,
            path=str(out),
            records=fetched,
            note=f"{fetched} weeks, {failed} failures, 0.125 deg native upsampled to 4 km",
        )
        return out

    def load(self) -> xr.Dataset:
        return xr.open_dataset(self._out_path())

    def status(self) -> SourceStatus:
        return self._last or SourceStatus(
            name=self.name, state=SourceState.SKIPPED, url=self.url, note="not fetched"
        )
