"""Folds, the look-counter guard and shared helpers for every v1.2 stage.

Everything here follows docs/PREREGISTRATION_V12.md: held-out years 2012, 2013,
2020 to 2025; training years 2007 to 2025 without the held-out year; an h-week
embargo before every excluded year; `erc_pct` recomputed from each training set.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

FOLDS = (2012, 2013, 2020, 2021, 2022, 2023, 2024, 2025)
YEARS = tuple(range(2007, 2026))
RECORD_END = pd.Timestamp("2025-12-31")
HOLDOUT_YEAR = 2026
LOOKS = 3
DATA = Path("data/v12")
OUT = Path("artifacts/v12")
SEED = 2026


def assert_looks() -> None:
    """The 2026 look counter reads exactly 3."""
    from cofire.model.freeze import look_count

    n = look_count(HOLDOUT_YEAR)
    if n != LOOKS:
        raise RuntimeError(f"2026 look counter reads {n}, expected {LOOKS}")


@contextlib.contextmanager
def sealed() -> Iterator[None]:
    """Assert the look counter before and after a stage."""
    assert_looks()
    yield
    assert_looks()


def record(domain: str) -> pd.DataFrame:
    """The domain's configuration A store, 2007 to 2025 only."""
    from cofire.ship import build_v11

    f = build_v11.load(domain)
    f = f[f["time"] <= RECORD_END].reset_index(drop=True)
    if pd.to_datetime(f["time"]).dt.year.max() >= HOLDOUT_YEAR:
        raise RuntimeError("a 2026 row reached a v1.2 stage")
    return f


def embargo_many(train: pd.DataFrame, years: tuple[int, ...], h: int) -> pd.DataFrame:
    """Drop rows whose h-week label lands in any excluded year."""
    t = pd.to_datetime(train["time"])
    lab = t + pd.Timedelta(weeks=h)
    bad = np.zeros(len(train), dtype=bool)
    for y in years:
        start = pd.Timestamp(f"{y}-01-01")
        bad |= (t < start).to_numpy() & (lab >= start).to_numpy() & (lab.dt.year == y).to_numpy()
    return train[~bad]


def frame_without(period: pd.DataFrame, excluded: tuple[int, ...]) -> pd.DataFrame:
    """Targets with `erc_pct` pools from the years not excluded."""
    from cofire.model.erc_pct import erc_percentile_reference
    from cofire.ship import fit_v11

    yr = pd.to_datetime(period["time"]).dt.year
    pct = erc_percentile_reference(period, (~yr.isin(excluded)).to_numpy())
    return fit_v11.with_targets(period, pct)
