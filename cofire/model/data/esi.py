"""ESI (Evaporative Stress Index) and the Rapid Change Index. HAND-REWRITE.

Product: ESI 4-week composite, SERVIR global ALEXI thermal-infrared product.
Keyless, weekly, 0.05 degree, 2001 to present.

Why windowed reads
------------------
Each global GeoTIFF is 86 MB. The server answers HTTP range requests, so GDAL's
/vsicurl/ driver fetches only the scanlines covering the domain: measured at
1.93 MB per file for the union of the Larimer and Pueblo bboxes, a 45x saving.
The files are striped rather than tiled, so a read still costs whole scanlines;
that is already priced into the budget.

Rapid Change Index
------------------
RCI follows the published construction (Otkin et al., "Flash drought" rapid
change index, using weekly ESI change anomalies): standardise each week-to-week
ESI change against its own climatological distribution, then accumulate
consecutive weeks whose standardised change carries the same sign. A long run of
same-sign drying accumulates into a large negative RCI, which is what makes it a
flash-drought indicator rather than a level indicator.

    dESI_t   = ESI_t - ESI_{t-1}
    z_t      = (dESI_t - mean(dESI)) / sd(dESI)     [training years only]
    RCI_t    = sum over the current same-sign run of z, weighted by run length

The standardisation moments are fit on the training window only, like every
other statistic in this project, so nothing downstream sees a later year.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.data.ledger import BudgetExceeded, get_ledger
from cofire.model.dates import tuesdays

LOGGER = logging.getLogger("cofire.data.esi")

BASE = "https://gis1.servirglobal.net/data/esi"
PRODUCT = "4WK"
# One global scanline is 7200 float32 px; the domain needs a contiguous row band.
BYTES_PER_FILE_ESTIMATE = 1_930_000

# GDAL settings that keep /vsicurl/ from listing directories or probing
# sidecars, both of which cost round trips and bytes we have not budgeted.
_GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


def _apply_gdal_env() -> None:
    for k, v in _GDAL_ENV.items():
        os.environ.setdefault(k, v)


def esi_url(d: date, product: str = PRODUCT) -> str:
    """ESI files are named by year and day-of-year of the composite end date."""
    return f"{BASE}/{product}/{d.year}/DFPPM_{product}_{d.year}{d.timetuple().tm_yday:03d}.tif"


def _nearest_available(target: date, cache: dict[int, list[str]]) -> str | None:
    """ESI weeks do not land on USDM Tuesdays, so map each Tuesday to the most
    recent ESI composite at or before it. Never look forward."""
    names = cache.get(target.year)
    if names is None:
        return None
    best, best_doy = None, -1
    tgt_doy = target.timetuple().tm_yday
    for n in names:
        try:
            doy = int(n[-7:-4])
        except ValueError:
            continue
        if doy <= tgt_doy and doy > best_doy:
            best, best_doy = n, doy
    return best


class EsiSource(DataSource):
    """Windowed ESI reads onto the gridMET grid, plus the Rapid Change Index."""

    name = "SERVIR ESI 4-week"
    url = BASE
    optional = False

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last: SourceStatus | None = None

    # ------------------------------------------------------------------ io

    def _out_path(self) -> Path:
        return self.settings.processed_dir / "esi" / "weekly.nc"

    def _listing(self, year: int) -> list[str]:
        """Filenames present for a year. One small HTML listing per year."""
        import requests

        from cofire.model.http import USER_AGENT

        try:
            r = requests.get(
                f"{BASE}/{PRODUCT}/{year}/", timeout=30, headers={"User-Agent": USER_AGENT}
            )
            if r.status_code >= 400:
                return []
            import re

            return sorted(set(re.findall(rf"DFPPM_{PRODUCT}_{year}\d{{3}}\.tif", r.text)))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("ESI listing for %s failed: %s", year, exc)
            return []

    def fetch(self, date_range: DateRange) -> Path:
        _apply_gdal_env()
        import rasterio
        from rasterio.windows import from_bounds

        out = self._out_path()
        if out.exists() and out.stat().st_size > 0:
            LOGGER.info("ESI cache hit at %s", out)
            self._last = SourceStatus(
                name=self.name, state=SourceState.OK, url=self.url, path=str(out), note="cache hit"
            )
            return out

        ledger = get_ledger()
        w, s, e, n = self.settings.bbox
        weeks = [d for d in tuesdays(date_range.start, date_range.end)]
        years = sorted({d.year for d in weeks})
        listings = {y: self._listing(y) for y in years}

        # Price the whole series before transferring anything.
        n_files = sum(1 for d in weeks if _nearest_available(d, listings))
        if not ledger.project_series(self.name, BYTES_PER_FILE_ESTIMATE, n_files):
            raise BudgetExceeded(
                f"{self.name}: {n_files} files x {BYTES_PER_FILE_ESTIMATE / 1e6:.2f} MB "
                f"exceeds the remaining {ledger.remaining_bytes / 1e6:.0f} MB"
            )

        frames: list[np.ndarray] = []
        times: list[pd.Timestamp] = []
        lat_axis = lon_axis = None
        fetched = failed = 0

        for d in weeks:
            fname = _nearest_available(d, listings)
            if not fname:
                continue
            url = f"/vsicurl/{BASE}/{PRODUCT}/{d.year}/{fname}"
            try:
                with rasterio.open(url) as ds:
                    win = from_bounds(w, s, e, n, ds.transform)
                    arr = ds.read(1, window=win, masked=True).astype("float32").filled(np.nan)
                    if lat_axis is None:
                        t = ds.window_transform(win)
                        lat_axis = t.f + t.e * (np.arange(arr.shape[0]) + 0.5)
                        lon_axis = t.c + t.a * (np.arange(arr.shape[1]) + 0.5)
                arr[arr < -100] = np.nan  # the product's nodata is -9999
                frames.append(arr)
                times.append(pd.Timestamp(d))
                fetched += 1
                # Bytes crossed the wire whether or not we keep them all.
                ledger.record(self.name, url, BYTES_PER_FILE_ESTIMATE, f"windowed {d.isoformat()}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                LOGGER.warning("ESI %s failed: %s", fname, exc)
                if failed > 10 and fetched == 0:
                    break

        if not frames:
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.UNAVAILABLE,
                url=self.url,
                note=f"no ESI grids retrieved ({failed} failures)",
            )
            raise RuntimeError("ESI unavailable")

        da = xr.DataArray(
            np.stack(frames),
            dims=("time", "lat", "lon"),
            coords={"time": pd.DatetimeIndex(times), "lat": lat_axis, "lon": lon_axis},
            name="esi_4wk",
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        da.to_dataset().to_netcdf(out)
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.OK if failed == 0 else SourceState.DEGRADED,
            url=self.url,
            path=str(out),
            records=fetched,
            note=f"windowed reads: {fetched} weeks, {failed} failures, "
            f"{fetched * BYTES_PER_FILE_ESTIMATE / 1e6:.0f} MB",
        )
        return out

    def load(self) -> xr.Dataset:
        return xr.open_dataset(self._out_path())

    def status(self) -> SourceStatus:
        return self._last or SourceStatus(
            name=self.name, state=SourceState.SKIPPED, url=self.url, note="not fetched"
        )


# ------------------------------------------------------------------- RCI


def standardised_change(esi: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    """z-scored week-over-week ESI change, moments fit on training weeks only.

    esi: (time, ...) array. train_mask: boolean over the time axis.
    """
    d = np.diff(esi, axis=0, prepend=esi[:1])
    tr = d[train_mask]
    mu = np.nanmean(tr, axis=0)
    sd = np.nanstd(tr, axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-6), sd, 1.0)
    out: np.ndarray = (d - mu) / sd
    return out


def rapid_change_index(z: np.ndarray) -> np.ndarray:
    """Accumulate consecutive same-sign standardised changes.

    RCI_t = sum over the current run of |z|, signed by the run, weighted by the
    run length. A long unbroken drying sequence therefore scores far more
    strongly than a single dry week of the same magnitude, which is the property
    that makes RCI a flash-drought indicator.
    """
    out = np.zeros_like(z, dtype="float32")
    run_sum = np.zeros(z.shape[1:], dtype="float32")
    run_len = np.zeros(z.shape[1:], dtype="float32")
    prev_sign = np.zeros(z.shape[1:], dtype="float32")

    for t in range(z.shape[0]):
        zt = np.nan_to_num(z[t], nan=0.0)
        sign = np.sign(zt)
        same = (sign == prev_sign) & (sign != 0)
        run_sum = np.where(same, run_sum + np.abs(zt), np.abs(zt))
        run_len = np.where(same, run_len + 1.0, 1.0)
        out[t] = sign * run_sum * run_len
        prev_sign = np.where(sign != 0, sign, prev_sign)
    return out
