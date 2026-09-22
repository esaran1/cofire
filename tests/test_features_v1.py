"""The v1 join must never read a value that was not readable at issue time."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from cofire.model.data.availability import REGISTRY
from cofire.model.features_v1 import (
    V1FeatureConfig,
    _assert_join,
    _pick_readable,
    add_esi_anomalies,
)


def _issues(n: int = 20) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.date_range("2020-01-07", periods=n, freq="7D"))


def test_picked_source_week_is_always_older_than_the_issue() -> None:
    issues = _issues()
    src = _issues(30)
    lag = timedelta(days=7) + timedelta(weeks=1)
    picked = _pick_readable(issues, src, lag)
    for iss, s in picked.items():
        if s is not None:
            assert s <= iss - lag, (iss, s)


def test_join_assertion_passes_for_a_correctly_lagged_pick() -> None:
    issues = _issues()
    src = _issues(30)
    av = REGISTRY["esi_4wk"]
    lag = timedelta(days=av.latency_days) + timedelta(weeks=av.guard_weeks)
    picked = _pick_readable(issues, src, lag)
    _assert_join("esi_4wk", picked, V1FeatureConfig(apply_reprocessing_guard=True))


def test_join_assertion_catches_a_same_week_read() -> None:
    """The exact leak: joining this week's composite at this week's issue."""
    issues = _issues(5)
    bad = {iss: iss for iss in issues}
    with pytest.raises(AssertionError, match="would not have been readable"):
        _assert_join("esi_4wk", bad, V1FeatureConfig())


def test_guard_makes_the_pick_strictly_older() -> None:
    """Turning the guard on must cost at least a week of recency.

    This is what the ablation prices: the guard is protection, and protection
    that costs nothing is usually protection that does nothing.
    """
    issues = _issues()
    src = _issues(40)
    av = REGISTRY["esi_4wk"]
    base = timedelta(days=av.latency_days)
    with_guard = _pick_readable(issues, src, base + timedelta(weeks=1))
    without = _pick_readable(issues, src, base)
    differing = [i for i in issues if with_guard[i] != without[i]]
    assert differing, "the guard changed nothing, so it is not doing anything"
    for i in differing:
        # Either the guard pushed the pick strictly older, or it removed a pick
        # entirely at the start of the record where nothing old enough exists.
        # Both are the guard doing its job; neither may ever be newer.
        if with_guard[i] is None:
            continue
        assert with_guard[i] < without[i]


def test_no_source_week_available_yields_none_not_a_guess() -> None:
    """Early issues have no readable composite and must stay missing."""
    issues = _issues(5)
    src = pd.DatetimeIndex(pd.date_range("2021-01-05", periods=5, freq="7D"))
    picked = _pick_readable(issues, src, timedelta(days=7))
    assert all(v is None for v in picked.values())


def test_anomalies_use_training_weeks_only() -> None:
    """A later high-ESI block must not shift the training-period anomalies."""
    times = pd.date_range("2019-01-01", periods=104, freq="7D")
    rows = []
    for t in times:
        rows.append({"cell_id": "c0", "time": t, "esi_4wk": 0.0 if t.year == 2019 else 10.0})
    df = pd.DataFrame(rows)
    out = add_esi_anomalies(df, pd.Timestamp("2019-12-31"))
    a = out[pd.to_datetime(out["time"]).dt.year == 2019]["esi_4wk_anom"]
    b = out[pd.to_datetime(out["time"]).dt.year == 2020]["esi_4wk_anom"]
    assert np.allclose(a.dropna(), 0.0, atol=1e-5), "training weeks should be near zero anomaly"
    assert b.dropna().mean() > 5, "the later block should show as a large positive anomaly"


def test_interpolation_flag_changes_the_series() -> None:
    """The ablation arm must actually differ, or it measures nothing."""
    from cofire.model.data.esi import interpolate_to_weekly

    t = pd.date_range("2020-01-07", periods=10, freq="14D")
    vals = np.arange(10, dtype="float32").reshape(10, 1, 1)
    da = xr.DataArray(vals, dims=("time", "lat", "lon"), coords={"time": t, "lat": [0], "lon": [0]})
    weekly = pd.DatetimeIndex(pd.date_range("2020-01-07", periods=19, freq="7D"))
    interp = interpolate_to_weekly(da, weekly, enabled=True).values.ravel()
    ffill = interpolate_to_weekly(da, weekly, enabled=False).values.ravel()
    assert not np.allclose(interp, ffill), "the two arms are identical, so the flag is inert"
    # The interpolated arm produces intermediate values the source never had.
    assert np.any(~np.isin(np.round(interp, 5), np.round(vals.ravel(), 5)))
