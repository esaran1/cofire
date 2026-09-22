"""The library implementations must agree with the hand-rolled ones.

Where they disagree, the library wins and the disagreement is explained. These
tests are the check that the swap did not silently change a conclusion.
"""

from __future__ import annotations

import numpy as np
import pytest
from cofire.model.confirm import benjamini_hochberg, holm
from cofire.model.prob_metrics import ar1_neff, stratified_block_bootstrap
from cofire.model.stats_lib import (
    circular_block_bootstrap,
    multipletests_bh,
    multipletests_holm,
    neff_from_acf,
)


def _weeks(n: int = 104) -> np.ndarray:
    return np.datetime64("2023-01-03") + np.arange(n) * np.timedelta64(7, "D")


@pytest.mark.parametrize(
    "pvals",
    [
        [0.001, 0.02, 0.2, 0.5, 0.9],
        [0.04, 0.05, 0.06, 0.07],
        [0.5, 0.6, 0.7],
        [0.0001, 0.0002, 0.9],
    ],
)
def test_bh_matches_statsmodels(pvals: list[float]) -> None:
    assert benjamini_hochberg(pvals, q=0.10) == multipletests_bh(pvals, q=0.10)


@pytest.mark.parametrize(
    "pvals",
    [
        [0.001, 0.02, 0.2, 0.5, 0.9],
        [0.04, 0.05, 0.06, 0.07],
        [0.001, 0.07, 0.06],
        [0.5, 0.6],
    ],
)
def test_holm_matches_statsmodels(pvals: list[float]) -> None:
    assert holm(pvals, alpha=0.10) == multipletests_holm(pvals, alpha=0.10)


def test_the_estimability_rule_survives_the_library_swap() -> None:
    """A rare target must be refused by both bootstraps alike."""
    w = _weeks()
    rng = np.random.default_rng(0)
    y = np.zeros(w.size)
    y[rng.choice(w.size, size=3, replace=False)] = 1.0

    custom = stratified_block_bootstrap(lambda sel: float(len(sel)), w, y, n_boot=50)
    lib = circular_block_bootstrap(lambda sel: float(len(sel)), w, y, n_boot=50)
    assert custom.estimable is False and lib.estimable is False
    assert custom.n_positive_weeks == lib.n_positive_weeks == 3


def test_both_bootstraps_cover_the_point_estimate() -> None:
    """Different resampling schemes, same basic guarantee."""
    w = _weeks()
    rng = np.random.default_rng(1)
    y = (rng.random(w.size) < 0.35).astype(float)
    rate = dict(zip(w.tolist(), y.tolist(), strict=True))

    def stat(sel: np.ndarray) -> float:
        vals = [rate[s] for s in sel.tolist() if s in rate]
        return float(np.mean(vals)) if vals else float("nan")

    custom = stratified_block_bootstrap(stat, w, y, n_boot=300)
    lib = circular_block_bootstrap(stat, w, y, n_boot=300)
    assert custom.estimable and lib.estimable
    assert custom.lo <= custom.point <= custom.hi
    assert lib.lo <= lib.point <= lib.hi
    # The point estimate is the statistic on the full series, so it is identical
    # by construction; only the intervals may differ.
    assert custom.point == pytest.approx(lib.point)


def test_acf_neff_and_ar1_neff_agree_on_an_ar1_series() -> None:
    """Where the AR(1) assumption holds, the two should be close."""
    rng = np.random.default_rng(2)
    n = 400
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.6 * x[i - 1] + rng.normal()
    a, b = ar1_neff(x), neff_from_acf(x)
    assert 0.5 < a / b < 2.0, f"ar1 {a:.1f} against acf {b:.1f}"


def test_the_two_neff_routines_disagree_on_a_finite_memory_series() -> None:
    """They make different assumptions, and it shows where one is wrong.

    A 20-point moving average has autocorrelation that reaches zero at lag 20
    and stays there. The ACF estimator sums the observed correlations and stops
    at that boundary. `ar1_neff` fits a single lag-1 coefficient and implies a
    geometric tail that never terminates, so it charges for correlation the
    series does not have and reports the *smaller* effective sample.

    Measured here: ACF about 19.8 against AR(1) about 10.6. The ACF figure is
    the better estimate for this process, which is why it is what the pipeline
    now reports.
    """
    rng = np.random.default_rng(3)
    n = 400
    base = rng.normal(size=n)
    x = np.convolve(base, np.ones(20) / 20, mode="same")
    acf_n, ar1_n = neff_from_acf(x), ar1_neff(x)
    assert acf_n > ar1_n, f"acf {acf_n:.1f} against ar1 {ar1_n:.1f}"
    # Both must still register that this series is heavily correlated.
    assert acf_n < n / 5 and ar1_n < n / 5


def test_white_noise_keeps_most_of_its_sample_under_both() -> None:
    rng = np.random.default_rng(4)
    x = rng.normal(size=300)
    assert ar1_neff(x) > 150
    assert neff_from_acf(x) > 150
