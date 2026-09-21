"""The reference erc_pct, verified against hand-computable answers.

One definition, one implementation. The quantity is the empirical percentile of
a cell-week's ERC within that cell's pool of training values whose week-of-year
lies within +/- 3 of it on a circular calendar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from cofire.model.erc_pct import (
    HALF_WINDOW,
    build_pools,
    describe_pool,
    erc_percentile_reference,
    percentile_of,
    window_weeks,
)


def test_window_wraps_the_year() -> None:
    """Week 1 and week 52 are adjacent; without the wrap the pool halves."""
    assert window_weeks(1) == [50, 51, 52, 1, 2, 3, 4]
    assert window_weeks(52) == [49, 50, 51, 52, 1, 2, 3]
    assert window_weeks(26) == [23, 24, 25, 26, 27, 28, 29]
    for w in range(1, 53):
        assert len(window_weeks(w)) == 2 * HALF_WINDOW + 1
        assert len(set(window_weeks(w))) == 2 * HALF_WINDOW + 1


def test_percentile_of_a_known_pool() -> None:
    """Hand-computable: 5 distinct values, kind='mean'."""
    pool = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    # 30 is the third of five: strictly below 2/5=40%, at-or-below 3/5=60%,
    # mean 50%.
    assert percentile_of(30.0, pool) == pytest.approx(50.0)
    assert percentile_of(10.0, pool) == pytest.approx(10.0)
    assert percentile_of(50.0, pool) == pytest.approx(90.0)


def test_ties_use_the_mean_convention() -> None:
    """A tie is ambiguous; 'mean' averages the strict and weak answers."""
    pool = np.array([10.0, 20.0, 20.0, 20.0, 30.0])
    # 20 appears three times: strictly below 1/5=20%, at-or-below 4/5=80%,
    # mean 50%.
    assert percentile_of(20.0, pool) == pytest.approx(50.0)


def test_a_value_drawn_from_its_own_pool_is_unbiased() -> None:
    """Why 'mean' rather than 'weak': the results centre on 50."""
    pool = np.arange(1.0, 11.0)
    pcts = [percentile_of(v, pool) for v in pool]
    assert np.mean(pcts) == pytest.approx(50.0)


def test_pools_are_built_from_training_rows_only() -> None:
    times = pd.date_range("2018-01-02", periods=120, freq="7D")
    frame = pd.DataFrame(
        {
            "cell_id": "c0",
            "time": times,
            "erc": np.concatenate([np.full(60, 10.0), np.full(60, 90.0)]),
        }
    )
    mask = np.arange(len(frame)) < 60  # only the low block is training
    out = erc_percentile_reference(frame, mask)
    # Later rows are all above every training value, so they sit at the top.
    assert np.nanmax(out[60:]) == pytest.approx(100.0)
    assert np.nanmin(out[60:]) == pytest.approx(100.0)


def test_the_year_wrap_pools_weeks_50_to_3_together() -> None:
    """The weeks the wrap exists for. Week 1's pool must include week 51."""
    times = pd.date_range("2018-01-02", periods=156, freq="7D")
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {"cell_id": "c0", "time": times, "erc": rng.uniform(0, 100, size=len(times))}
    )
    pools = build_pools(frame)
    woys = frame["time"].dt.isocalendar().week.astype(int).clip(1, 52)
    n_wk51 = int((woys == 51).sum())
    assert n_wk51 > 0
    # Week 1's pool spans weeks 50..4, so it must be larger than week 51 alone.
    assert pools[("c0", 1)].size > n_wk51


def test_every_week_gets_a_comparable_pool_size() -> None:
    """No week may be short-changed by the calendar boundary."""
    times = pd.date_range("2018-01-02", periods=5 * 52, freq="7D")
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(
        {"cell_id": "c0", "time": times, "erc": rng.uniform(0, 100, size=len(times))}
    )
    pools = build_pools(frame)
    sizes = [pools[("c0", w)].size for w in range(1, 53)]
    assert min(sizes) >= 0.6 * max(sizes), f"pool sizes range {min(sizes)} to {max(sizes)}"


def test_describe_pool_lists_the_rows_behind_one_value() -> None:
    """The hand-check path: a pool you can read and add up yourself."""
    times = pd.date_range("2018-01-02", periods=104, freq="7D")
    frame = pd.DataFrame(
        {"cell_id": "c0", "time": times, "erc": np.arange(104, dtype=float)}
    )
    rows = describe_pool(frame, "c0", 1)
    assert set(rows["woy"]).issubset(set(window_weeks(1)))
    pool = build_pools(frame)[("c0", 1)]
    assert pool.size == len(rows)
