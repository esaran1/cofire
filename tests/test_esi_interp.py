"""Biweekly sampling plus interpolation must reproduce the weekly series.

The Gate 1 amendment requires this to be an executable check with a stated
tolerance, not an assumption. The tolerance is set in units of the series' own
standard deviation, because an absolute ESI error is meaningless without knowing
how much the series moves.

Tolerance: reconstruction MAE on the dropped weeks must be under 20% of the
series standard deviation. Rationale: a feature reconstructed with a fifth of
the series' own variability as error still carries most of its information, and
the ablation runs with and without interpolation so the cost is measured rather
than assumed. Measured on real fetched data, the 12-week composite scores 0.166
and the faster-moving 4-week composite scores 0.229, which is why 12WK is the
product sampled biweekly and 4WK is fetched at full rate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from cofire.model.data.esi import interpolate_to_weekly, interpolation_error

TOLERANCE_MAE_OVER_SD = 0.20

PROBE_12WK = Path("data/processed_pueblo/esi/weekly_12wk.nc")
FULL_4WK = Path("data/processed_pueblo/esi/weekly.nc")


def _synthetic(n: int = 60, smooth: float = 0.9, seed: int = 0) -> xr.DataArray:
    """A smooth autocorrelated series, standing in for a long composite."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2020-01-07", periods=n, freq="7D")
    vals = np.zeros((n, 2, 2), dtype="float32")
    for i in range(1, n):
        vals[i] = smooth * vals[i - 1] + rng.normal(scale=0.3, size=(2, 2))
    return xr.DataArray(vals, dims=("time", "lat", "lon"), coords={"time": t, "lat": [0, 1], "lon": [0, 1]})


def test_interpolation_recovers_a_smooth_series() -> None:
    """On a smooth series the reconstruction must be well inside tolerance.

    smooth=0.98 matches the week-to-week persistence of a real 12-week
    composite; the real-data test below is the one that actually gates.
    """
    da = _synthetic(smooth=0.98)
    err = interpolation_error(da, stride=2)
    assert err["mae_over_sd"] < TOLERANCE_MAE_OVER_SD, err


def test_interpolation_error_grows_when_the_series_is_rough() -> None:
    """The metric must actually detect roughness, or it proves nothing."""
    smooth_err = interpolation_error(_synthetic(smooth=0.97), stride=2)["mae_over_sd"]
    rough_err = interpolation_error(_synthetic(smooth=0.0), stride=2)["mae_over_sd"]
    assert rough_err > smooth_err * 1.5, (smooth_err, rough_err)


def test_kept_weeks_are_exact_and_are_excluded_from_the_error() -> None:
    """Error is reported on dropped weeks only; kept weeks are exact."""
    da = _synthetic()
    times = pd.DatetimeIndex(da.time.values)
    kept = times[::2]
    recon = interpolate_to_weekly(da.sel(time=kept), times, enabled=True)
    assert np.allclose(recon.sel(time=kept).values, da.sel(time=kept).values, atol=1e-5)
    err = interpolation_error(da, stride=2)
    assert err["n_dropped"] == len(times) - len(kept)


def test_disabled_flag_never_invents_an_intermediate_value() -> None:
    """The no-interpolation arm must carry forward, not interpolate.

    This is the arm the ablation uses to measure what interpolation costs.
    """
    da = _synthetic()
    times = pd.DatetimeIndex(da.time.values)
    kept = times[::2]
    ff = interpolate_to_weekly(da.sel(time=kept), times, enabled=False)
    # Every reconstructed value must equal some value that was actually fetched.
    fetched = set(np.round(da.sel(time=kept).values.ravel(), 5).tolist())
    got = set(np.round(ff.values.ravel(), 5).tolist())
    assert got.issubset(fetched)


@pytest.mark.skipif(not PROBE_12WK.exists(), reason="12WK probe not fetched")
def test_real_12wk_interpolation_is_within_tolerance() -> None:
    """The gate the amendment names, on real fetched data.

    If this fails, the documented fallback is weekly ESI 12WK with EDDI trimmed.
    """
    da = xr.open_dataset(PROBE_12WK)["esi_12wk"]
    err = interpolation_error(da, stride=2)
    assert err["mae_over_sd"] < TOLERANCE_MAE_OVER_SD, (
        f"12WK biweekly interpolation MAE is {err['mae_over_sd']:.3f} of the series SD, "
        f"over the {TOLERANCE_MAE_OVER_SD} tolerance; fall back to weekly 12WK"
    )


@pytest.mark.skipif(not FULL_4WK.exists(), reason="4WK series not fetched")
def test_4wk_is_rougher_than_12wk_which_is_why_it_is_not_strided() -> None:
    """Records the measurement that drove the sampling decision."""
    four = interpolation_error(xr.open_dataset(FULL_4WK)["esi_4wk"], stride=2)
    assert four["mae_over_sd"] > 0.20, (
        "4WK was expected to exceed the tolerance, which is why it is fetched weekly"
    )
