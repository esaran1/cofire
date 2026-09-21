"""The single reference implementation of `erc_pct`.

Definition, stated once and implemented once:

    For cell c and week w, `erc_pct` is the empirical percentile of that week's
    ERC value within the pool of cell c's weekly ERC values over the training
    years, restricted to weeks whose week-of-year lies within +/- 3 of w's on a
    circular calendar.

Every consumer calls this. Fitting and transformation sharing one
implementation is the point: the original ACI failure came from an evaluation
path and a calibration path computing the same quantity differently, and the
`erc_pct` disagreement found during the record extension is the same shape of
fault.

Ties use `kind="mean"`. A percentile of a value against a pool containing that
value is ambiguous at the tie, and `"weak"` reports the fraction at or below
while `"strict"` reports the fraction strictly below. `"mean"` is their average,
which is the convention that makes the percentile of a value drawn from its own
pool unbiased: for a pool of n distinct values the n results are evenly spaced
about 50, whereas `"weak"` skews them upward by 100/(2n).
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

LOGGER = logging.getLogger("cofire.erc_pct")

HALF_WINDOW = 3
TIE_KIND = "mean"


def window_weeks(woy: int, half_window: int = HALF_WINDOW) -> list[int]:
    """Weeks of year within `half_window` of `woy`, wrapping at 52.

    Week 1 and week 52 are adjacent. Without the wrap the pool for weeks 50 to
    3 is half the size of every other week's, which is exactly where a
    percentile is least well estimated.
    """
    return [((int(woy) - 1 + d) % 52) + 1 for d in range(-half_window, half_window + 1)]


def build_pools(
    train: pd.DataFrame,
    value_col: str = "erc",
    half_window: int = HALF_WINDOW,
) -> dict[tuple[str, int], np.ndarray]:
    """Per (cell, week-of-year) training pools, keyed for lookup.

    Built once from the training rows only. The caller is responsible for
    passing training rows; this function does not filter by date, so that the
    training window is decided in one place rather than assumed here.
    """
    df = train[["cell_id", "time", value_col]].copy()
    df["time"] = pd.to_datetime(df["time"])
    df["woy"] = df["time"].dt.isocalendar().week.astype(int).clip(1, 52)
    df["_v"] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=["_v"])

    by_cell_week: dict[tuple[str, int], list[float]] = {}
    for (cell, woy), g in df.groupby(["cell_id", "woy"]):
        by_cell_week[(str(cell), int(woy))] = g["_v"].to_numpy(dtype=float).tolist()

    pools: dict[tuple[str, int], np.ndarray] = {}
    cells = {c for c, _ in by_cell_week}
    for cell in cells:
        for woy in range(1, 53):
            vals: list[float] = []
            for w in window_weeks(woy, half_window):
                vals.extend(by_cell_week.get((cell, w), []))
            if vals:
                pools[(cell, woy)] = np.sort(np.asarray(vals, dtype=float))
    return pools


def percentile_of(value: float, pool: np.ndarray | None) -> float:
    """Empirical percentile of `value` within `pool`. One formula, one place."""
    if pool is None or pool.size == 0 or not np.isfinite(value):
        return float("nan")
    return float(stats.percentileofscore(pool, value, kind=TIE_KIND))


def erc_percentile_reference(
    frame: pd.DataFrame,
    train_mask: np.ndarray | pd.Series,
    value_col: str = "erc",
    half_window: int = HALF_WINDOW,
) -> np.ndarray:
    """`erc_pct` for every row of `frame`, pools fitted on `train_mask` rows.

    `train_mask` selects the rows that define the pools. Every row is scored,
    including rows outside the training window, which is how a percentile
    against a frozen training distribution is meant to work.
    """
    mask = np.asarray(train_mask, dtype=bool)
    pools = build_pools(frame[mask], value_col=value_col, half_window=half_window)

    t = pd.to_datetime(frame["time"])
    woy = t.dt.isocalendar().week.astype(int).clip(1, 52).to_numpy()
    cells = frame["cell_id"].astype(str).to_numpy()
    vals = pd.to_numeric(frame[value_col], errors="coerce").to_numpy(dtype=float)

    out = np.full(len(frame), np.nan, dtype=float)
    for i in range(len(frame)):
        out[i] = percentile_of(vals[i], pools.get((cells[i], int(woy[i]))))
    return out


def describe_pool(
    train: pd.DataFrame,
    cell_id: str,
    woy: int,
    value_col: str = "erc",
    half_window: int = HALF_WINDOW,
) -> pd.DataFrame:
    """The rows that form one pool, for hand-checking a single value."""
    df = train[train["cell_id"].astype(str) == str(cell_id)].copy()
    df["time"] = pd.to_datetime(df["time"])
    df["woy"] = df["time"].dt.isocalendar().week.astype(int).clip(1, 52)
    keep = df[df["woy"].isin(window_weeks(woy, half_window))]
    return keep[["time", "woy", value_col]].sort_values("time").reset_index(drop=True)
