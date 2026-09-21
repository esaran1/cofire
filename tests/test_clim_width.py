"""A percentile target has a near-uniform marginal, so its 5-95 width is ~90.

This is the check that would have caught the original error. The first
climatological width grouped on a single week of year, which holds about three
training values per cell, so the 5th and 95th percentiles collapsed to the
minimum and maximum and reported 33 to 37 for a quantity that must be near 90.
The width ratio built on it was wrong by a factor of about 2.5.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from cofire.model.shipping import climatological_median, climatological_width


def _uniform_percentile_panel(
    n_cells: int = 12, n_weeks: int = 260, seed: int = 0
) -> pd.DataFrame:
    """A panel whose target is uniform on 0 to 100, as a percentile must be."""
    rng = np.random.default_rng(seed)
    times = pd.date_range("2018-01-02", periods=n_weeks, freq="7D")
    rows = []
    for c in range(n_cells):
        for t in times:
            v = float(rng.uniform(0, 100))
            rows.append({"cell_id": f"c{c}", "time": t, "erc_pct_h4": v, "erc_pct": v})
    return pd.DataFrame(rows)


def test_climatological_width_of_a_uniform_percentile_is_near_ninety() -> None:
    """The invariant. A uniform 0-100 marginal has a 5-95 width of 90."""
    df = _uniform_percentile_panel()
    w = climatological_width(df, 4, df)
    mean_w = float(np.mean(w))
    assert 80.0 <= mean_w <= 95.0, (
        f"climatological width came out {mean_w:.1f}; a week-of-year percentile "
        "target must have a 5-95 width near 90"
    )


def test_width_is_not_collapsed_by_thin_single_week_groups() -> None:
    """Pooling the circular window is what keeps the order statistics usable.

    With a single week per group there are about three values and the estimate
    collapses. The pooled window gives enough to estimate a 5th and 95th
    percentile at all.
    """
    df = _uniform_percentile_panel(n_cells=6, n_weeks=156)
    pooled = float(np.mean(climatological_width(df, 4, df)))

    single = df.copy()
    single["woy"] = pd.to_datetime(single["time"]).dt.isocalendar().week.astype(int)
    q = single.groupby(["cell_id", "woy"])["erc_pct_h4"].quantile([0.05, 0.95]).unstack()
    naive = float((q[0.95] - q[0.05]).mean())
    assert pooled > naive + 10, f"pooled {pooled:.1f} should clearly exceed naive {naive:.1f}"


def test_climatological_median_of_a_uniform_percentile_is_near_fifty() -> None:
    df = _uniform_percentile_panel()
    m = float(np.mean(climatological_median(df, 4, df)))
    assert 40.0 <= m <= 60.0, f"median came out {m:.1f}"


def test_a_narrow_cell_keeps_a_narrow_interval() -> None:
    """The estimator must still track a genuinely low-variance cell."""
    rng = np.random.default_rng(1)
    times = pd.date_range("2018-01-02", periods=260, freq="7D")
    rows = []
    for t in times:
        rows.append({"cell_id": "wide", "time": t, "erc_pct_h4": float(rng.uniform(0, 100))})
        rows.append({"cell_id": "narrow", "time": t, "erc_pct_h4": float(rng.uniform(45, 55))})
    df = pd.DataFrame(rows)
    w = climatological_width(df, 4, df)
    wide = float(np.mean(w[df["cell_id"].to_numpy() == "wide"]))
    narrow = float(np.mean(w[df["cell_id"].to_numpy() == "narrow"]))
    assert narrow < 20 < wide, f"narrow {narrow:.1f}, wide {wide:.1f}"
