"""SPI against a reference implementation; no leakage from frozen TrainingStats."""

from __future__ import annotations

import numpy as np
import pandas as pd
from cofire.model.explain import assert_exhaustive
from cofire.model.features import (
    FEATURE_COLUMNS,
    TrainingStats,
    _fit_gamma,
    add_calendar,
    add_lags_and_rolls,
    fit_training_stats,
    spi_from_params,
    transform,
)
from scipy import stats


def reference_spi(x: float, series: np.ndarray) -> float:
    params = _fit_gamma(series)
    return spi_from_params(x, params)


def test_spi_matches_reference_on_synthetic_gamma() -> None:
    rng = np.random.default_rng(2026)
    series = rng.gamma(shape=2.0, scale=10.0, size=400)
    series[:40] = 0.0
    x = float(np.median(series[series > 0]))
    ours = spi_from_params(x, _fit_gamma(series))
    # Reference: mixed CDF then Φ^{-1}, same as McKee 1993.
    p0 = float(np.mean(series <= 0))
    pos = series[series > 0]
    shape, loc, scale = stats.gamma.fit(pos, floc=0)
    h = p0 + (1 - p0) * float(stats.gamma.cdf(x, shape, loc=loc, scale=scale))
    h = min(max(h, 1e-6), 1 - 1e-6)
    ref = float(stats.norm.ppf(h))
    assert abs(ours - ref) < 1e-6


def test_training_stats_do_not_use_future_rows() -> None:
    rng = np.random.default_rng(0)
    times = pd.date_range("2019-01-01", periods=200, freq="W-TUE")
    rows = []
    for cell in ("a", "b"):
        pr = rng.gamma(2, 8, size=len(times))
        erc = 20 + 10 * np.sin(np.arange(len(times)) / 8) + rng.normal(0, 2, len(times))
        for t, p, e in zip(times, pr, erc, strict=True):
            rows.append(
                {
                    "cell_id": cell,
                    "time": t,
                    "lat": 40.5,
                    "lon": -105.0,
                    "pr": p,
                    "pet": p * 0.8,
                    "erc": e,
                    "bi": e * 0.9,
                    "fm100": 10,
                    "fm1000": 12,
                    "tmmx": 290,
                    "usdm": 1,
                }
            )
    frame = add_lags_and_rolls(add_calendar(pd.DataFrame(rows)))
    train_end = pd.Timestamp("2021-12-28")
    stats_a = fit_training_stats(frame, train_end)
    # Mutating post-train rows must not change frozen stats.
    frame.loc[pd.to_datetime(frame["time"]) > train_end, "erc"] = 999
    stats_b = fit_training_stats(frame, train_end)
    cell = "a"
    woy = 10
    np.testing.assert_allclose(stats_a.erc_by_woy[cell][woy], stats_b.erc_by_woy[cell][woy])
    out = transform(frame, stats_a)
    future = out.loc[pd.to_datetime(out["time"]) > train_end]
    assert future["erc_pct"].notna().any()
    # Percentiles of the mutated 999 using frozen hist must still be in [0, 100].
    assert future["erc_pct"].max() <= 100.0 + 1e-6


def test_nan_handling_does_not_raise() -> None:
    frame = pd.DataFrame(
        {
            "cell_id": ["c"],
            "time": [pd.Timestamp("2020-06-02")],
            "lat": [40.5],
            "lon": [-105.0],
            "pr": [np.nan],
            "pet": [np.nan],
            "erc": [np.nan],
            "bi": [np.nan],
            "fm100": [np.nan],
            "fm1000": [np.nan],
            "tmmx": [np.nan],
            "usdm": [np.nan],
            "month": [6],
            "woy": [22],
            "doy_sin": [0.0],
            "doy_cos": [1.0],
        }
    )
    out = transform(frame, TrainingStats())
    assert len(out) == 1


def test_feature_columns_nonempty() -> None:
    assert "spi_90" in FEATURE_COLUMNS
    assert_exhaustive()
