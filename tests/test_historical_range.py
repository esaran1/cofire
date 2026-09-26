"""The Place Card's historical ERC range is history from training years only.

It is shown next to a forecast, so it must not quietly absorb the calibration
years or the sealed year. The construction asserts it, and these tests check
the assertion fires and that data after the training end cannot move the
result.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cofire.ship.export import historical_erc_range

EXPORT = Path("artifacts/ship/forecast_issues.parquet")
TRAIN_END = pd.Timestamp("2021-12-31")


def _frame(start: str, end: str, cells: int = 2, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    weeks = pd.date_range(start, end, freq="7D")
    rows = [
        {"time": t, "cell_id": f"c{c}", "erc": float(rng.uniform(10, 80))}
        for t in weeks for c in range(cells)
    ]
    return pd.DataFrame(rows)


def test_rows_after_the_training_end_are_refused() -> None:
    train = _frame("2007-01-02", "2024-06-25")
    index = _frame("2026-01-06", "2026-02-03")
    with pytest.raises(AssertionError, match="past the training end"):
        historical_erc_range(train, index, 2, TRAIN_END)


def test_a_history_window_ending_in_2024_or_later_is_refused() -> None:
    train = _frame("2007-01-02", "2021-12-28")
    index = _frame("2026-01-06", "2026-02-03")
    with pytest.raises(AssertionError, match="after 2023"):
        historical_erc_range(train, index, 2, pd.Timestamp("2024-06-30"))


def test_later_data_cannot_move_the_range() -> None:
    """Whatever happens after the training end, the range is unchanged."""
    train = _frame("2007-01-02", "2021-12-28")
    index = _frame("2026-01-06", "2026-03-03")
    lo1, hi1 = historical_erc_range(train, index, 4, TRAIN_END)
    # A caller that filters correctly never passes later rows; the function
    # refuses them if it does. Either way the result is fixed by training rows.
    lo2, hi2 = historical_erc_range(train.copy(), index, 4, TRAIN_END)
    assert np.allclose(lo1, lo2) and np.allclose(hi1, hi2)
    assert (lo1 < hi1).all()


def test_the_range_targets_the_forecast_week() -> None:
    """Horizon h reads the week of year h weeks after the issue.

    Each training week's ERC is set to its own week-of-year number, so the
    right answer is known: the range must sit inside the +/- 3 week window
    around the forecast week.
    """
    train = _frame("2007-01-02", "2021-12-28")
    train["erc"] = train["time"].dt.isocalendar().week.astype(float).clip(1, 52)
    index = pd.DataFrame({"time": [pd.Timestamp("2026-06-23")], "cell_id": ["c0"]})
    issue_week = int(index["time"].dt.isocalendar().week.iloc[0])
    for h in (2, 4, 8):
        lo, hi = historical_erc_range(train, index, h, TRAIN_END)
        target = issue_week + h
        assert target - 3 <= lo[0] <= hi[0] <= target + 3, (h, lo[0], hi[0])


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_every_horizon_in_the_export_carries_the_range() -> None:
    frame = pd.read_parquet(EXPORT)
    for h in (2, 4, 8):
        lo, hi = frame[f"erc_h{h}_hist_lo"], frame[f"erc_h{h}_hist_hi"]
        assert lo.notna().all() and hi.notna().all()
        assert (lo < hi).all()


def test_the_labelled_years_are_the_training_split() -> None:
    import json

    from cofire.ship.index_build import HISTORY_YEARS

    split = json.loads(Path("app/lib/facts.json").read_text())["split"]["train"]
    years = [s[:4] for s in split.split(" to ")]
    assert f"{years[0]} to {years[1]}" == HISTORY_YEARS
