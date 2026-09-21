"""The paired real-minus-shuffled test must find skill only where skill exists.

The fault this closes: two models that are both functions of the same input
differ in Brier on shuffled labels through probability spread alone. Seven fire
targets passed a raw BSS interval and six of them reproduced the same effect on
shuffled targets, which means the interval was measuring spread, not skill.
"""

from __future__ import annotations

import numpy as np
import pytest
from cofire.model.prob_metrics import brier
from cofire.model.stats_lib import (
    bootstrap_pvalue,
    paired_real_minus_shuffled,
    shuffle_within_blocks,
)


def _weeks(n: int) -> np.ndarray:
    return np.arange(n, dtype=float)


def test_shuffle_preserves_block_totals() -> None:
    rng = np.random.default_rng(0)
    weeks = _weeks(60)
    y = rng.binomial(1, 0.3, size=60).astype(float)
    out = shuffle_within_blocks(y, weeks, 6, rng)
    for start in range(0, 60, 6):
        assert y[start : start + 6].sum() == out[start : start + 6].sum()


def test_shuffle_preserves_marginal_rate() -> None:
    rng = np.random.default_rng(1)
    weeks = _weeks(120)
    y = rng.binomial(1, 0.25, size=120).astype(float)
    out = shuffle_within_blocks(y, weeks, 5, rng)
    assert out.sum() == y.sum()


def test_real_skill_gives_positive_difference() -> None:
    """A prediction that tracks the target must clear its own shuffled control."""
    rng = np.random.default_rng(2)
    n = 300
    weeks = _weeks(n)
    y = rng.binomial(1, 0.3, size=n).astype(float)
    # Genuinely informative: the prediction leans the right way on every row.
    pred = np.where(y > 0.5, 0.75, 0.25)
    base = np.full(n, y.mean())

    def stat(sel: np.ndarray, yy: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        b = brier(base[m], yy[m])
        return float("nan") if b <= 1e-12 else 1.0 - brier(pred[m], yy[m]) / b

    res = paired_real_minus_shuffled(stat, weeks, y, n_boot=120, n_shuffles=8)
    assert res.estimable
    assert res.lo > 0, f"real skill should clear the control, got [{res.lo}, {res.hi}]"


def test_spread_alone_does_not_pass() -> None:
    """A prediction with spread but no association must not clear its control.

    This is the exact structural artefact the rule exists for. `pred` has a
    wide spread and `base` does not, so the two differ in Brier on shuffled
    labels through spread alone. The construction below gives `pred` exactly
    zero sample correlation with `y` rather than merely drawing it
    independently: in 300 rows an independent draw still correlates by chance
    at around r=0.1, which is real association on those rows and which the
    paired test correctly reports. Sorting the values within each outcome
    class removes the association without touching the marginal spread.
    """
    rng = np.random.default_rng(3)
    n = 300
    weeks = _weeks(n)
    y = rng.binomial(1, 0.3, size=n).astype(float)
    pred = rng.uniform(0.05, 0.6, size=n)
    # Same value assigned to every row, in an order that carries no signal:
    # each outcome class receives the same distribution of predictions.
    order = np.argsort(pred)
    pred = pred[order][np.argsort(np.argsort(np.tile(np.arange(n // 2 + 1), 2)[:n]))]
    pos, neg = y > 0.5, y <= 0.5
    pred[pos] = np.linspace(0.05, 0.6, int(pos.sum()))
    pred[neg] = np.linspace(0.05, 0.6, int(neg.sum()))
    base = np.full(n, 0.3)

    def stat(sel: np.ndarray, yy: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        b = brier(base[m], yy[m])
        return float("nan") if b <= 1e-12 else 1.0 - brier(pred[m], yy[m]) / b

    res = paired_real_minus_shuffled(stat, weeks, y, n_boot=120, n_shuffles=8)
    assert res.estimable
    assert res.lo <= 0, f"spread alone must not clear the control, got [{res.lo}, {res.hi}]"


def test_rare_event_is_not_estimable() -> None:
    weeks = _weeks(200)
    y = np.zeros(200)
    y[:4] = 1.0

    def stat(sel: np.ndarray, yy: np.ndarray) -> float:
        return 0.0

    res = paired_real_minus_shuffled(stat, weeks, y, n_boot=50, n_shuffles=4)
    assert not res.estimable
    assert "positive weeks" in res.reason


def test_pvalue_tracks_the_interval() -> None:
    """A CI clear of zero gives a small p-value; one straddling it does not."""
    rng = np.random.default_rng(4)
    n = 300
    weeks = _weeks(n)
    y = rng.binomial(1, 0.3, size=n).astype(float)
    pred = np.where(y > 0.5, 0.75, 0.25)
    base = np.full(n, y.mean())

    def stat(sel: np.ndarray, yy: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        b = brier(base[m], yy[m])
        return float("nan") if b <= 1e-12 else 1.0 - brier(pred[m], yy[m]) / b

    res = paired_real_minus_shuffled(stat, weeks, y, n_boot=120, n_shuffles=8)
    p = bootstrap_pvalue(res)
    assert 0.0 <= p <= 1.0
    assert p < 0.05


def test_pvalue_is_nan_when_not_estimable() -> None:
    weeks = _weeks(200)
    y = np.zeros(200)
    y[:3] = 1.0
    res = paired_real_minus_shuffled(
        lambda sel, yy: 0.0, weeks, y, n_boot=50, n_shuffles=4
    )
    assert np.isnan(bootstrap_pvalue(res))


def test_deterministic_under_seed() -> None:
    rng = np.random.default_rng(5)
    n = 200
    weeks = _weeks(n)
    y = rng.binomial(1, 0.3, size=n).astype(float)
    pred = np.where(y > 0.5, 0.7, 0.3)
    base = np.full(n, y.mean())

    def stat(sel: np.ndarray, yy: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        b = brier(base[m], yy[m])
        return float("nan") if b <= 1e-12 else 1.0 - brier(pred[m], yy[m]) / b

    a = paired_real_minus_shuffled(stat, weeks, y, n_boot=80, n_shuffles=5)
    b = paired_real_minus_shuffled(stat, weeks, y, n_boot=80, n_shuffles=5)
    assert a.point == pytest.approx(b.point)
    assert a.lo == pytest.approx(b.lo)


def test_week_sums_reproduce_the_brier_exactly() -> None:
    rng = np.random.default_rng(10)
    n = 400
    weeks = np.repeat(np.arange(50), 8).astype(float)
    p = rng.uniform(0, 1, n)
    y = rng.binomial(1, 0.3, n).astype(float)
    from cofire.model.stats_lib import brier_week_sums

    uniq, sums, counts = brier_week_sums(p, y, weeks)
    assert sums.sum() / counts.sum() == pytest.approx(brier(p, y))


def test_week_selection_preserves_multiplicity() -> None:
    """A week drawn twice must count twice.

    `np.isin(weeks, sel)` is a membership test and silently collapses a
    repeated draw to one, which reweights every bootstrap replicate. Indexing
    by position does not.
    """
    from cofire.model.stats_lib import brier_week_sums, bss_from_sums

    weeks = np.repeat(np.arange(6), 5).astype(float)
    n = weeks.size
    rng = np.random.default_rng(11)
    y = rng.binomial(1, 0.4, n).astype(float)
    pred = rng.uniform(0, 1, n)
    ref = np.full(n, y.mean())
    _u, ms, cs = brier_week_sums(pred, y, weeks)
    _u2, rs, _ = brier_week_sums(ref, y, weeks)

    once = bss_from_sums(np.array([0, 1]), ms, rs, cs)
    twice = bss_from_sums(np.array([0, 0, 1, 1]), ms, rs, cs)
    # Doubling every week is the same selection proportionally.
    assert once == pytest.approx(twice)
    # But doubling only one week is not.
    lopsided = bss_from_sums(np.array([0, 0, 1]), ms, rs, cs)
    assert lopsided != pytest.approx(once)


def test_fast_path_agrees_with_the_general_one() -> None:
    """The specialised BSS version must match the general implementation."""
    from cofire.model.stats_lib import paired_bss_shuffled

    rng = np.random.default_rng(12)
    n = 600
    weeks = np.repeat(np.arange(120), 5).astype(float)
    y = rng.binomial(1, 0.3, n).astype(float)
    pred = np.where(y > 0.5, 0.7, 0.3)
    ref = np.full(n, y.mean())

    def stat(sel: np.ndarray, yy: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        b = brier(ref[m], yy[m])
        return float("nan") if b <= 1e-12 else 1.0 - brier(pred[m], yy[m]) / b

    slow = paired_real_minus_shuffled(stat, weeks, y, n_boot=100, n_shuffles=6, seed=7)
    fast = paired_bss_shuffled(pred, ref, y, weeks, n_boot=100, n_shuffles=6, seed=7)
    # Same seed, same shuffles, same blocks: the point estimates are identical.
    assert fast.point == pytest.approx(slow.point, abs=1e-9)
    assert fast.n_positive_weeks == slow.n_positive_weeks
    # Both must reach the same verdict.
    assert (fast.lo > 0) == (slow.lo > 0)


def test_fast_path_rejects_spread_alone() -> None:
    from cofire.model.stats_lib import paired_bss_shuffled

    rng = np.random.default_rng(13)
    n = 600
    weeks = np.repeat(np.arange(120), 5).astype(float)
    y = rng.binomial(1, 0.3, n).astype(float)
    # Same predictive distribution in both outcome classes, in random order:
    # spread without association, and without smuggling in an order effect.
    pred = np.empty(n)
    pos, neg = y > 0.5, y <= 0.5
    pred[pos] = rng.permutation(np.linspace(0.05, 0.6, int(pos.sum())))
    pred[neg] = rng.permutation(np.linspace(0.05, 0.6, int(neg.sum())))
    ref = np.full(n, 0.3)
    res = paired_bss_shuffled(pred, ref, y, weeks, n_boot=200, n_shuffles=12)
    assert res.estimable
    assert res.lo <= 0
