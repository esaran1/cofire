"""SubX CFSv2 subseasonal forecasts from the IRI Data Library. HAND-REWRITE.

The only forecast-weather source found that covers the training window. The
hindcast runs 1999-01-01 to 2017-09-30 and the forecast series picks up at
2017-10-15 and continues to the present, so together they span the record.

Ingested as resumable monthly chunks. Each month is one request of roughly
700 KB taking about two minutes, so a year is a stage of about 25 minutes and
the whole record is staged well under the 60-minute rule per run.

Two things this is careful about.

**Anomalies use the model's own lead-dependent climatology.** A raw SubX
forecast carries the model's biases, which vary by lead time. Standard S2S
practice is to subtract the model's own hindcast climatology at the matching
lead and day of year, so what reaches the feature store is a departure from
what the model usually says at that lead, not a departure from observed
weather. The hindcast-period climatology is applied unchanged to the forecast
period, which is the convention: recomputing it on the forecast period would
leak.

**Hindcast and forecast are not the same instrument.** Ensemble size and model
configuration differ between the two series, so a `subx_is_forecast` indicator
travels with the data rather than pretending the join is seamless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import Settings, get_settings
from cofire.model.data.ledger import get_ledger

LOGGER = logging.getLogger("cofire.data.subx")

BASE = "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.SubX/.NCEP/.CFSv2"
# The two series and the issue-date range each covers. Verified by requesting
# S/first and S/last: hindcast 1999-01-01..2017-09-30, forecast 2017-10-15..now.
SERIES = {"hindcast": (date(1999, 1, 1), date(2017, 9, 30)),
          "forecast": (date(2017, 10, 15), date(2026, 9, 20))}
VARIABLES = ("pr", "tas")
# Weeks 1 to 4.
LEAD_MAX_DAYS = 28
# Union of both domains, padded to the SubX 1-degree grid.
BBOX = (-107.0, 37.0, -104.0, 41.0)
# Measured: 698 KB for one month of one variable over this box at leads 0-28.
BYTES_PER_MONTH = 700_000

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def month_url(series: str, var: str, year: int, month: int) -> str:
    """One month of issues, subset server-side to the Colorado box."""
    first = date(year, month, 1)
    last = date(year + (month == 12), (month % 12) + 1, 1) - pd.Timedelta(days=1).to_pytimedelta()
    w, s, e, n = BBOX
    return (
        f"{BASE}/.{series}/.{var}"
        f"/X/{w}/{e}/RANGEEDGES"
        f"/Y/{s}/{n}/RANGEEDGES"
        f"/L/0/{LEAD_MAX_DAYS}/RANGE"
        f"/S/%28{first.day}%20{_MONTHS[first.month - 1]}%20{first.year}%29"
        f"/%28{last.day}%20{_MONTHS[last.month - 1]}%20{last.year}%29/RANGEEDGES"
        "/data.nc"
    )


def _is_netcdf(path: Path) -> bool:
    """The IRI server returns HTTP 200 with an HTML error page for a bad path.

    A malformed request once produced 1488 bytes, status 200, that turned out to
    be "Error 404: Bad Request". Byte count alone would pass it, so every
    payload is checked for the NetCDF magic number before it is recorded.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(4)
    except OSError:
        return False
    return head[:3] == b"CDF" or head == b"\x89HDF"


@dataclass
class SubxSource:
    """Resumable monthly ingest of one SubX variable."""

    settings: Settings
    var: str = "pr"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"SubX CFSv2 {self.var}"

    def _chunk_dir(self) -> Path:
        # Not subset-scoped: one Colorado box serves both domains, so scoping
        # per subset would fetch the same bytes twice.
        return self.settings.data_dir / "cache" / "subx" / self.var

    def _chunk_path(self, series: str, year: int, month: int) -> Path:
        return self._chunk_dir() / f"{series}_{year}{month:02d}.nc"

    def pending(self, start: date, end: date) -> list[tuple[str, int, int]]:
        """Months not yet on disk, so an interrupted run resumes where it left."""
        todo: list[tuple[str, int, int]] = []
        for series, (s_start, s_end) in SERIES.items():
            lo = max(start, s_start)
            hi = min(end, s_end)
            if lo > hi:
                continue
            cur = date(lo.year, lo.month, 1)
            while cur <= hi:
                p = self._chunk_path(series, cur.year, cur.month)
                if not (p.exists() and p.stat().st_size > 0):
                    todo.append((series, cur.year, cur.month))
                cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
        return todo

    def fetch_month(self, series: str, year: int, month: int, timeout: int = 300) -> bool:
        import requests

        from cofire.model.http import USER_AGENT

        out = self._chunk_path(series, year, month)
        if out.exists() and out.stat().st_size > 0:
            return True
        out.parent.mkdir(parents=True, exist_ok=True)
        url = month_url(series, self.var, year, month)
        ledger = get_ledger()
        ledger.check(url, self.name, assume_bytes=BYTES_PER_MONTH)
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as exc:
            LOGGER.warning("%s %s %d-%02d: %s", self.name, series, year, month, exc)
            return False
        if r.status_code >= 400 or not r.content:
            LOGGER.warning("%s %s %d-%02d: HTTP %s", self.name, series, year, month, r.status_code)
            return False
        tmp = out.with_suffix(".part")
        tmp.write_bytes(r.content)
        if not _is_netcdf(tmp):
            LOGGER.warning(
                "%s %s %d-%02d: %d bytes that are not NetCDF, discarding",
                self.name, series, year, month, len(r.content),
            )
            tmp.unlink(missing_ok=True)
            return False
        tmp.rename(out)
        ledger.record(self.name, url, len(r.content), f"{series} {year}-{month:02d} (measured)")
        return True

    def run(self, start: date, end: date, budget_seconds: int = 3000) -> dict[str, int]:
        """Fetch pending months until the time budget is spent.

        Bounded by wall clock rather than by count, so a stage always fits the
        60-minute rule regardless of how slow the server is that day.
        """
        import time

        todo = self.pending(start, end)
        t0 = time.time()
        done = failed = 0
        for series, year, month in todo:
            if time.time() - t0 > budget_seconds:
                LOGGER.info("%s: time budget reached, %d months still pending", self.name, len(todo) - done - failed)
                break
            if self.fetch_month(series, year, month):
                done += 1
            else:
                failed += 1
            if (done + failed) % 10 == 0:
                LOGGER.info("%s: %d done, %d failed, %d pending", self.name, done, failed, len(todo) - done - failed)
        return {"done": done, "failed": failed, "pending": len(self.pending(start, end))}


def load_chunks(settings: Settings | None = None, var: str = "pr") -> pd.DataFrame:
    """Every cached month as a long frame of (issue, lead, value) domain means.

    Reduced to a domain mean per issue and lead on load. The SubX grid is one
    degree against gridMET's four kilometres, so a per-cell join would assert
    spatial detail the source does not have.
    """
    import xarray as xr

    settings = settings or get_settings()
    root = settings.data_dir / "cache" / "subx" / var
    if not root.exists():
        return pd.DataFrame(columns=["issue", "lead", var, "is_forecast"])
    rows: list[pd.DataFrame] = []
    for p in sorted(root.glob("*.nc")):
        try:
            ds = xr.open_dataset(p, decode_times=False)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("subx chunk %s unreadable: %s", p.name, exc)
            continue
        if var not in ds.data_vars:
            continue
        da = ds[var]
        dims = [d for d in da.dims if d in ("X", "Y", "M")]
        mean = da.mean(dim=dims, skipna=True)
        s_vals = pd.Timestamp("1960-01-01") + pd.to_timedelta(ds["S"].values, unit="D")
        lead = ds["L"].values
        arr = np.asarray(mean.transpose("S", "L").values, dtype=float)
        frame = pd.DataFrame(arr, index=pd.DatetimeIndex(s_vals), columns=np.round(lead, 3))
        long = frame.stack().rename(var).reset_index()
        long.columns = ["issue", "lead", var]
        long["is_forecast"] = float(p.name.startswith("forecast"))
        rows.append(long)
    if not rows:
        return pd.DataFrame(columns=["issue", "lead", var, "is_forecast"])
    return pd.concat(rows, ignore_index=True)


def lead_climatology(frame: pd.DataFrame, var: str, hindcast_only: bool = True) -> pd.DataFrame:
    """The model's own mean by lead and week of year, from the hindcast period.

    Applied unchanged to the forecast period. Recomputing it there would use the
    evaluation period to define its own reference.
    """
    src = frame[frame["is_forecast"] == 0.0] if hindcast_only else frame
    if src.empty:
        return pd.DataFrame(columns=["lead", "woy", f"{var}_clim"])
    s = src.copy()
    s["woy"] = pd.to_datetime(s["issue"]).dt.isocalendar().week.astype(int).clip(1, 52)
    out = s.groupby(["lead", "woy"])[var].mean().reset_index()
    return out.rename(columns={var: f"{var}_clim"})


def anomalies(frame: pd.DataFrame, var: str) -> pd.DataFrame:
    """Departure from the model's own lead-dependent climatology."""
    if frame.empty:
        return frame
    clim = lead_climatology(frame, var)
    out = frame.copy()
    out["woy"] = pd.to_datetime(out["issue"]).dt.isocalendar().week.astype(int).clip(1, 52)
    out = out.merge(clim, on=["lead", "woy"], how="left")
    out[f"{var}_anom"] = out[var] - out[f"{var}_clim"]
    return out.drop(columns=["woy"])
