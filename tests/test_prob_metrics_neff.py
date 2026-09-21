"""Effective sample size must reflect the data, not the calendar.

`block_bootstrap` previously passed the week *labels* to `ar1_neff`. Week labels
are evenly spaced, so their AR(1) coefficient is ~1 and n_eff collapsed toward
1.5 for any input whatsoever. The number appeared in every reported row and was
meaningless. These tests pin that it now tracks the statistic.
"""

from __future__ import annotations

import numpy as np
from cofire.model.prob_metrics import ar1_neff, block_bootstrap


def test_evenly_spaced_labels_would_collapse_neff() -> None:
    """The shape of the old bug, kept visible so it is not reintroduced."""
    labels = np.arange(104, dtype=float)
    assert ar1_neff(labels) < 3, "evenly spaced labels are near-perfectly autocorrelated"


def test_neff_is_large_for_independent_weeks() -> None:
    """A statistic that varies independently week to week keeps most of its n."""
    rng = np.random.default_rng(0)
    weeks = np.arange("2020-01-07", "2022-01-04", 7, dtype="datetime64[D]")
    vals = {w: float(rng.normal()) for w in weeks}

    res = block_bootstrap(
        lambda sel: float(np.mean([vals[w] for w in sel])), weeks, n_boot=50
    )
    assert res.n_weeks == len(weeks)
    assert res.n_eff > 0.5 * len(weeks), f"independent weeks should keep most of n, got {res.n_eff}"


def test_neff_shrinks_when_the_statistic_is_autocorrelated() -> None:
    """A slow-drifting statistic has fewer independent observations than weeks."""
    rng = np.random.default_rng(1)
    weeks = np.arange("2020-01-07", "2022-01-04", 7, dtype="datetime64[D]")
    x, prev = {}, 0.0
    for w in weeks:
        prev = 0.9 * prev + rng.normal()
        x[w] = prev

    res = block_bootstrap(lambda sel: float(np.mean([x[w] for w in sel])), weeks, n_boot=50)
    assert res.n_eff < 0.5 * len(weeks), f"autocorrelated weeks should shrink n, got {res.n_eff}"


def test_datetime_weeks_do_not_raise() -> None:
    """The dtype path that broke np.isin: tolist() on datetime64 yields ints."""
    weeks = np.arange("2020-01-07", "2020-07-07", 7, dtype="datetime64[D]")
    res = block_bootstrap(lambda sel: float(len(sel)), weeks, n_boot=20)
    assert res.n_weeks == len(weeks)
    assert np.isfinite(res.point)
