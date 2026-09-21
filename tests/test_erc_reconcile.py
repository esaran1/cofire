"""A newly fetched source-year must match an overlapping year, cell for cell.

The gate exists because a hand-written DODS parser produced a domain mean of
21.4 against the store's 43.6 for the same year, domain and variable, while
returning values in a physically plausible 0 to 96 range. Plausible and wrong is
the failure mode; only a cell-for-cell comparison catches it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr
from cofire.model.data.erc_extension import reconcile


def _cube(seed: int = 0, offset: float = 0.0, shift: int = 0) -> xr.DataArray:
    rng = np.random.default_rng(seed)
    days = pd.date_range("2018-01-01", periods=60)
    lat = np.linspace(41.0, 40.3, 8)
    lon = np.linspace(-106.2, -105.0, 10)
    vals = rng.uniform(0, 100, size=(60, 8, 10)) + offset
    if shift:
        vals = np.roll(vals, shift, axis=0)
    return xr.DataArray(
        vals, dims=("day", "lat", "lon"), coords={"day": days, "lat": lat, "lon": lon}
    )


def test_identical_arrays_reconcile() -> None:
    a = _cube()
    r = reconcile(a, a.copy())
    assert r.ok
    assert r.max_abs_diff == 0.0
    assert r.n_compared == 60 * 8 * 10


def test_a_constant_offset_fails_the_gate() -> None:
    """The shape of the original bug: plausible values, wrong by a factor."""
    a = _cube()
    r = reconcile(a, a + 1.0)
    assert not r.ok
    assert abs(r.max_abs_diff - 1.0) < 1e-9
    assert "first mismatch at" in r.first_mismatch


def test_a_time_shifted_array_fails_the_gate() -> None:
    """An indexing error that preserves the value distribution exactly.

    Marginal statistics are identical here, so anything comparing means would
    pass. Only a cell-for-cell check catches it.
    """
    a = _cube()
    b = _cube(shift=3)
    assert np.isclose(float(a.mean()), float(b.mean()))
    r = reconcile(a, b)
    assert not r.ok, "a rolled array must not reconcile"


def test_tolerance_admits_float_noise_but_not_real_error() -> None:
    a = _cube()
    assert reconcile(a, a + 1e-9).ok
    assert not reconcile(a, a + 1e-3).ok


def test_no_overlap_is_reported_rather_than_passing() -> None:
    """An empty intersection must never read as a match."""
    a = _cube()
    b = a.assign_coords(lat=a.lat.values + 50.0)
    r = reconcile(a, b)
    assert not r.ok
    assert "no overlapping" in r.first_mismatch


def test_the_gate_reports_where_the_mismatch_is() -> None:
    a = _cube()
    b = a.copy()
    b[10, 3, 4] = float(b[10, 3, 4]) + 25.0
    r = reconcile(a, b)
    assert not r.ok
    assert "day=" in r.first_mismatch and "lat=" in r.first_mismatch
