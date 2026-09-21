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
# Measured over the wire, not inferred. The ESI GeoTIFFs are uncompressed
# float32 in single-row strips (7200 x 1 = 28.8 KB), so a windowed read pulls
# whole rows but only the rows the bbox touches, plus the header GDAL reads
# first. Measured by issuing the exact byte ranges and counting what came back:
#
#     larimer  rows 980..995   16 strips 460_800 B + 65_536 header = 0.526 MB
#     pueblo   rows 1029..1045 17 strips 489_600 B + 65_536 header = 0.555 MB
#
# The larger domain is used so the projection is conservative. The original
# 1_930_000 was a guess that overcharged the ledger 3.5x and falsely blocked the
# Larimer 12WK series. An earlier correction to 460_800 was closer but omitted
# the header. See DECISIONS.md.
BYTES_PER_FILE_ESTIMATE = 555_136

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
    """Windowed ESI reads onto the gridMET grid, plus the Rapid Change Index.

    `product` selects 4WK or 12WK. `stride` samples every Nth week: a 12-week
    composite changes little week to week, so fetching it biweekly and
    interpolating costs half the bytes. The interpolation is validated against
    a full-rate series before it is trusted (see tests/test_esi_interp.py), and
    it is behind a flag so the ablation can run with and without it.
    """

    optional = False

    def __init__(
        self,
        settings: Settings | None = None,
        product: str = PRODUCT,
        stride: int = 1,
    ) -> None:
        self.settings = settings or get_settings()
        self.product = product
        self.stride = max(1, int(stride))
        self.name = f"SERVIR ESI {product}"
        self.url = f"{BASE}/{product}"
        self._last: SourceStatus | None = None

    # ------------------------------------------------------------------ io

    def _out_path(self, start_year: int | None = None) -> Path:
        """Cache path. The start year is part of the key.

        Without it an extended fetch silently returns the shorter cached series:
        a 2010-onward backfill hit the 2018 cache and reported success having
        transferred nothing. The default keeps the existing 2018 files valid.
        """
        stem = "weekly" if self.product == "4WK" else f"weekly_{self.product.lower()}"
        if self.stride > 1:
            stem += f"_stride{self.stride}"
        if start_year is not None and start_year != 2018:
            stem += f"_from{start_year}"
        return self.settings.processed_dir / "esi" / f"{stem}.nc"

    def _listing(self, year: int) -> list[str]:
        """Filenames present for a year. One small HTML listing per year."""
        import requests

        from cofire.model.http import USER_AGENT

        try:
            r = requests.get(
                f"{BASE}/{self.product}/{year}/", timeout=30, headers={"User-Agent": USER_AGENT}
            )
            if r.status_code >= 400:
                return []
            import re

            return sorted(set(re.findall(rf"DFPPM_{self.product}_{year}\d{{3}}\.tif", r.text)))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("ESI listing for %s failed: %s", year, exc)
            return []

    def fetch(self, date_range: DateRange) -> Path:
        _apply_gdal_env()
        import rasterio
        from rasterio.windows import from_bounds

        out = self._out_path(date_range.start.year)
        if out.exists() and out.stat().st_size > 0:
            LOGGER.info("ESI cache hit at %s", out)
            self._last = SourceStatus(
                name=self.name, state=SourceState.OK, url=self.url, path=str(out), note="cache hit"
            )
            return out

        ledger = get_ledger()
        w, s, e, n = self.settings.bbox
        weeks = list(tuesdays(date_range.start, date_range.end))[:: self.stride]
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
            url = f"/vsicurl/{BASE}/{self.product}/{d.year}/{fname}"
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
                # Bytes crossed the wire whether or not we keep them all. Charge
                # what GDAL actually transferred where it will tell us; fall back
                # to the estimate otherwise, and say which in the note so the
                # ledger total is never mistaken for a measurement.
                measured = _transferred_bytes()
                ledger.record(
                    self.name,
                    url,
                    measured if measured is not None else BYTES_PER_FILE_ESTIMATE,
                    f"windowed {d.isoformat()} "
                    f"({'measured' if measured is not None else 'estimated'})",
                )
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
            name=f"esi_{self.product.lower()}",
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        da.to_dataset().to_netcdf(out)
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.OK if failed == 0 else SourceState.DEGRADED,
            url=self.url,
            path=str(out),
            records=fetched,
            note=f"windowed reads: {fetched} samples (stride {self.stride}), "
            f"{failed} failures, {fetched * BYTES_PER_FILE_ESTIMATE / 1e6:.0f} MB",
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


def _transferred_bytes() -> int | None:
    """Bytes GDAL moved over the wire since the last call, if it will say.

    GDAL exposes a network-usage counter from 3.2 onward. It is monotonic per
    process, so we difference it. Returns None when the build does not carry the
    counter, which is why the ledger records a fallback rather than a zero: an
    unmeasurable transfer must never look free.
    """
    global _LAST_NET_USAGE
    try:
        from osgeo import gdal  # type: ignore[import-not-found]
    except ImportError:
        return None
    fn = getattr(gdal, "GetNetworkStatsAsSerializedJSON", None)
    if fn is None:
        return None
    try:
        import json

        total = int(json.loads(fn()).get("bytes_downloaded", 0))
    except Exception:  # noqa: BLE001
        return None
    delta = total - _LAST_NET_USAGE
    _LAST_NET_USAGE = total
    return delta if delta >= 0 else None


_LAST_NET_USAGE = 0


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


# ------------------------------------------------------- biweekly interpolation


def interpolate_to_weekly(
    da: xr.DataArray, target_times: pd.DatetimeIndex, enabled: bool = True
) -> xr.DataArray:
    """Linearly interpolate a strided series onto weekly issue dates.

    A 12-week composite is near-constant week to week, so sampling biweekly and
    interpolating costs half the bytes for a small error. That claim is not
    taken on faith: `tests/test_esi_interp.py` reconstructs a biweekly-sampled
    series and asserts the reconstruction matches the full-rate series within a
    stated tolerance on real fetched data.

    `enabled=False` returns nearest-previous values instead, which is the
    honest no-interpolation arm for the ablation: it uses only values that were
    actually fetched and never invents an intermediate week.
    """
    if not enabled:
        return da.reindex(time=target_times, method="ffill")
    return da.interp(time=target_times, method="linear", kwargs={"fill_value": "extrapolate"})


def interpolation_error(full: xr.DataArray, stride: int = 2) -> dict[str, float]:
    """Sample `full` at `stride`, interpolate back, and measure the damage.

    Reported on the weeks that were dropped, because the kept weeks are exact by
    construction and including them would flatter the result.
    """
    times = pd.DatetimeIndex(full.time.values)
    kept = times[::stride]
    dropped = times.difference(kept)
    if dropped.empty:
        return {"n_dropped": 0.0, "mae": float("nan"), "p95_abs": float("nan"), "max_abs": float("nan")}
    recon = full.sel(time=kept).interp(
        time=dropped, method="linear", kwargs={"fill_value": "extrapolate"}
    )
    truth = full.sel(time=dropped)
    err = np.abs(recon.values - truth.values)
    err = err[np.isfinite(err)]
    if err.size == 0:
        return {"n_dropped": float(len(dropped)), "mae": float("nan"), "p95_abs": float("nan"), "max_abs": float("nan")}
    spread = float(np.nanstd(full.values))
    return {
        "n_dropped": float(len(dropped)),
        "mae": float(np.mean(err)),
        "p95_abs": float(np.percentile(err, 95)),
        "max_abs": float(np.max(err)),
        "series_sd": spread,
        "mae_over_sd": float(np.mean(err) / spread) if spread > 0 else float("nan"),
    }
