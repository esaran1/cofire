"""ONI and PDO monthly indices. HAND-REWRITE.

Two text files, a few kilobytes each, carrying the interannual signal the
cell-level features cannot see. The cell features describe the current state of
one 4 km pixel; these describe the state of the Pacific, which is what actually
moves a whole season's drought odds in Colorado.

Why this is worth adding when 10 GB of CFSv2 was not: these cost kilobytes, and
they carry the one thing the oracle decomposition says is missing, which is the
*level* rather than the ranking.

Availability: both are published monthly with roughly a two-week lag, and both
are retrospectively revised. The revision matters, so `available_at` in
`availability.py` carries the guard week, and the join lags them accordingly.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import Settings, get_settings
from cofire.model.data import DateRange, SourceState, SourceStatus
from cofire.model.data.ledger import get_ledger

LOGGER = logging.getLogger("cofire.data.climate_indices")

ONI_URL = "https://psl.noaa.gov/data/correlation/oni.data"
PDO_URL = "https://psl.noaa.gov/data/correlation/pdo.data"
# Both files are a few kB. Measured with a HEAD before the first fetch.
BYTES_ESTIMATE = 12_000


def parse_psl_table(text: str) -> pd.DataFrame:
    """Parse the PSL monthly-table format into long form.

    The format is a header line giving the year range, then one row per year
    with twelve monthly values, then a trailing missing-value sentinel and some
    prose. Values equal to the sentinel become NaN.
    """
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame(columns=["time", "value"])

    missing = -99.99
    rows: list[tuple[pd.Timestamp, float]] = []
    for ln in lines:
        parts = ln.split()
        if len(parts) < 13:
            # Header, sentinel or trailing prose. The sentinel is a lone float.
            if len(parts) == 1:
                with contextlib.suppress(ValueError):
                    missing = float(parts[0])
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue
        if not (1800 <= year <= 2200):
            continue
        for month, raw in enumerate(parts[1:13], start=1):
            try:
                v = float(raw)
            except ValueError:
                continue
            rows.append((pd.Timestamp(year=year, month=month, day=1), v))

    df = pd.DataFrame(rows, columns=["time", "value"])
    if df.empty:
        return df
    df.loc[np.isclose(df["value"], missing, atol=1e-6), "value"] = np.nan
    return df.dropna(subset=["value"]).sort_values("time").reset_index(drop=True)


@dataclass
class ClimateIndexSource:
    """ONI and PDO, cached as one small parquet."""

    settings: Settings
    name: str = "NOAA PSL climate indices"

    def _out_path(self) -> Path:
        # Not subset-scoped: these are global indices, identical for every
        # domain. Scoping them per subset would refetch the same file.
        return self.settings.data_dir / "cache" / "climate_indices.parquet"

    def fetch(self, date_range: DateRange | None = None) -> Path:
        import requests

        from cofire.model.http import USER_AGENT

        out = self._out_path()
        if out.exists() and out.stat().st_size > 0:
            LOGGER.info("climate indices cache hit at %s", out)
            return out

        ledger = get_ledger()
        frames: list[pd.DataFrame] = []
        for label, url in (("oni", ONI_URL), ("pdo", PDO_URL)):
            ledger.check(url, self.name, assume_bytes=BYTES_ESTIMATE)
            r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            ledger.record(self.name, url, len(r.content), f"{label} monthly table (measured)")
            df = parse_psl_table(r.text)
            df["index_name"] = label
            frames.append(df)
            LOGGER.info("%s: %d monthly values, %s..%s", label, len(df),
                        df["time"].min().date() if len(df) else "-",
                        df["time"].max().date() if len(df) else "-")

        wide = (
            pd.concat(frames, ignore_index=True)
            .pivot(index="time", columns="index_name", values="value")
            .reset_index()
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        wide.to_parquet(out, index=False)
        return out

    def status(self) -> SourceStatus:
        out = self._out_path()
        ok = out.exists() and out.stat().st_size > 0
        return SourceStatus(
            name=self.name,
            state=SourceState.OK if ok else SourceState.UNAVAILABLE,
            url=ONI_URL,
            path=str(out) if ok else None,
            note="cached" if ok else "not fetched",
        )


def load_indices(settings: Settings | None = None) -> pd.DataFrame:
    """Monthly ONI and PDO, or an empty frame when not fetched."""
    settings = settings or get_settings()
    p = settings.data_dir / "cache" / "climate_indices.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["time", "oni", "pdo"])
    return pd.read_parquet(p)


def attach_monthly_indices(
    frame: pd.DataFrame, settings: Settings | None = None, lag_months: int = 1
) -> pd.DataFrame:
    """Join the most recent index value readable at each week.

    `lag_months` is the publication lag: the value for month M is not available
    until partway through M+1, so a week in month M reads month M-1. That is a
    deliberate under-use of the data rather than a guess at the exact release
    day, and it errs toward being too old rather than too new.
    """
    idx = load_indices(settings)
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"])
    if idx.empty:
        out["oni"] = np.nan
        out["pdo"] = np.nan
        return out

    idx = idx.copy()
    idx["time"] = pd.to_datetime(idx["time"])
    # Shift the index forward by the publication lag, then as-of join backwards.
    idx["readable_from"] = idx["time"] + pd.DateOffset(months=lag_months)
    idx = idx.sort_values("readable_from")
    merged = pd.merge_asof(
        out.sort_values("time"),
        idx[["readable_from", "oni", "pdo"]],
        left_on="time",
        right_on="readable_from",
        direction="backward",
    )
    merged = merged.drop(columns=["readable_from"])
    return merged.sort_index()


def fetch(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return ClimateIndexSource(settings).fetch(DateRange(start=date(2000, 1, 1), end=date.today()))
