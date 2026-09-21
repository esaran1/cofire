"""A rare-event bootstrap must not report a number it cannot support.

Larimer `d_intensify2_h2` has 3 positive domain-weeks out of 104. Its
unstratified interval came back as [+0.002, +0.954], which is the bootstrap
saying it has nothing to work with rather than saying the effect is real.
"""

from __future__ import annotations

import numpy as np
from cofire.model.prob_metrics import (
    MIN_POSITIVE_WEEKS,
    positive_weeks,
    stratified_block_bootstrap,
)


def _weeks(n: int = 104) -> np.ndarray:
    start = np.datetime64("2023-01-03")
    return start + np.arange(n) * np.timedelta64(7, "D")


def _outcomes(weeks: np.ndarray, n_positive: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.zeros(weeks.size)
    y[rng.choice(weeks.size, size=n_positive, replace=False)] = 1.0
    return y


def test_a_target_with_too_few_positive_weeks_is_not_estimable() -> None:
    """The exact case: 3 positives out of 104."""
    w = _weeks()
    y = _outcomes(w, 3)
    res = stratified_block_bootstrap(lambda sel: float(len(sel)), w, y)
    assert res.estimable is False
    assert res.n_positive_weeks == 3
    assert np.isnan(res.lo) and np.isnan(res.hi)
    assert "positive weeks" in res.reason


def test_a_target_with_enough_positive_weeks_is_estimable() -> None:
    w = _weeks()
    y = _outcomes(w, MIN_POSITIVE_WEEKS + 8)
    # A statistic that is well defined on a resample with repeats: the mean
    # outcome over the selected weeks.
    rate = dict(zip(w.tolist(), y.tolist(), strict=True))

    def stat(sel: np.ndarray) -> float:
        vals = [rate[s] for s in sel.tolist() if s in rate]
        return float(np.mean(vals)) if vals else float("nan")

    res = stratified_block_bootstrap(stat, w, y)
    assert res.estimable is True
    assert np.isfinite(res.lo) and np.isfinite(res.hi)
    assert res.lo <= res.point <= res.hi


def test_every_replicate_keeps_the_original_positive_week_count() -> None:
    """The point of stratifying: no replicate may be an empty draw."""
    w = _weeks()
    y = _outcomes(w, 20)
    pos = set(positive_weeks(y, w).tolist())
    seen: list[int] = []

    def stat(sel: np.ndarray) -> float:
        # Only full-size draws are replicates; the single-week calls at the end
        # are the effective-sample-size pass, not resamples.
        if sel.size == w.size:
            seen.append(sum(1 for s in sel.tolist() if s in pos))
        return 0.0

    stratified_block_bootstrap(stat, w, y, n_boot=50)
    # The first full-size call is the point estimate on the unique weeks; the
    # rest are replicates, each carrying the original number of positive weeks.
    assert len(seen) >= 50, f"expected 50 replicates, saw {len(seen)}"
    assert all(c == 20 for c in seen), f"replicates lost positives: {set(seen)}"


def test_the_threshold_is_on_weeks_not_rows() -> None:
    """One week of many positive cells is still one week of evidence."""
    w = np.repeat(_weeks(8), 500)          # 8 weeks, 500 cells each
    y = np.zeros(w.size)
    y[w == w[0]] = 1.0                     # 500 positive rows, all in ONE week
    res = stratified_block_bootstrap(lambda sel: float(len(sel)), w, y)
    assert res.n_positive_weeks == 1
    assert res.estimable is False


def test_point_estimate_is_still_reported_when_not_estimable() -> None:
    """The number is not hidden; only the interval is withheld."""
    w = _weeks()
    y = _outcomes(w, 2)
    res = stratified_block_bootstrap(lambda sel: 0.42, w, y)
    assert res.point == 0.42
    assert res.estimable is False
