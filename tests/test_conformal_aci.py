"""Regression tests for the ACI defects found in v0.5.

See artifacts/uncertainty/diagnosis.md. Two defects made intervals shrink under
misses: the update targeted coverage where it needed the miss rate, and a frozen
qhat was rescaled linearly instead of re-quantiled. These tests fail on the old
code and pass on the fix.
"""

from __future__ import annotations

import numpy as np
from cofire.model.conformal import CellState, ConformalCalibrator, aci_update


def _pool(n: int = 4000, seed: int = 0) -> CellState:
    rng = np.random.default_rng(seed)
    resid = np.sort(np.abs(rng.normal(size=n)))
    return CellState(
        qhat=float(np.quantile(resid, 0.9)),
        alpha=0.10,
        resid_abs=[float(v) for v in resid],
    )


def test_miss_widens_interval() -> None:
    """Sign check: a miss must move alpha so the interval gets wider."""
    state = _pool()
    before = state.qhat_at(state.alpha)
    state.alpha = aci_update(state.alpha, missed=True, target=0.90)
    after = state.qhat_at(state.alpha)
    assert after > before, f"miss narrowed the interval ({before:.4f} -> {after:.4f})"


def test_hit_narrows_interval() -> None:
    state = _pool()
    before = state.qhat_at(state.alpha)
    state.alpha = aci_update(state.alpha, missed=False, target=0.90)
    after = state.qhat_at(state.alpha)
    assert after <= before


def test_aci_fixed_point_is_the_miss_rate() -> None:
    """Equilibrium must sit at a 10% miss rate, not a 90% one.

    The old code's only stationary point was p_miss=0.90 (10% coverage).
    """
    lr, target = 0.01, 0.90
    up = aci_update(0.10, missed=False, target=target, lr=lr) - 0.10
    down = aci_update(0.10, missed=True, target=target, lr=lr) - 0.10
    # E[delta] = p*down + (1-p)*up = 0  ->  p = up / (up - down)
    p_miss = up / (up - down)
    assert abs(p_miss - 0.10) < 1e-9, f"equilibrium miss rate is {p_miss:.3f}, want 0.10"


def test_stationary_stream_holds_nominal_coverage() -> None:
    """No shift at all: coverage must sit near 0.90, not decay.

    On the old code this converged to ~0.26.
    """
    state = _pool()
    rng = np.random.default_rng(1)
    alpha, hits = 0.10, []
    for _ in range(800):
        half = state.qhat_at(alpha)
        miss = abs(rng.normal()) > half
        hits.append(not miss)
        alpha = aci_update(alpha, miss, target=0.90)
    late = float(np.mean(hits[-300:]))
    assert 0.85 <= late <= 0.95, f"stationary coverage {late:.3f} off target"


def test_width_grows_within_n_steps_after_step_change() -> None:
    """Injected step change in residual magnitude must widen the interval."""
    state = _pool()
    rng = np.random.default_rng(2)
    alpha = 0.10
    width_at = []
    for t in range(600):
        half = state.qhat_at(alpha)
        width_at.append(2 * half)
        scale = 3.0 if t >= 300 else 1.0
        miss = abs(rng.normal() * scale) > half
        alpha = aci_update(alpha, miss, target=0.90)
    pre = width_at[299]
    within_n = max(width_at[300:350])
    assert within_n > pre, f"width did not grow after the step ({pre:.3f} -> {within_n:.3f})"


def test_mild_shift_recovers_coverage_to_within_3_points() -> None:
    """After a mild step change, mean coverage must come back within 3 points.

    Averaged over seeds: a single seed lands in 0.860-0.895 (alpha pins at the
    0.01 floor, so a frozen pool cannot fully absorb even a 1.5x shift -- see
    diagnosis.md). The mean is the stable quantity, so that is what is asserted.
    """
    late = []
    for seed in range(8):
        pool = _pool()
        rng = np.random.default_rng(seed)
        alpha, hits = 0.10, []
        for t in range(900):
            half = pool.qhat_at(alpha)
            scale = 1.5 if t >= 300 else 1.0
            miss = abs(rng.normal() * scale) > half
            hits.append(not miss)
            alpha = aci_update(alpha, miss, target=0.90)
        late.append(float(np.mean(hits[-200:])))
    mean_late = float(np.mean(late))
    assert mean_late >= 0.87, f"mean coverage did not recover: {mean_late:.3f}"
    # And it must be far above the broken code's ~0.26 on every seed.
    assert min(late) > 0.80, f"a seed collapsed: {min(late):.3f}"


def test_alpha_state_is_non_constant_across_a_run() -> None:
    """Alpha must actually evolve, i.e. state is carried, not reinitialised."""
    state = _pool()
    rng = np.random.default_rng(4)
    alpha, seen = 0.10, []
    for _ in range(200):
        half = state.qhat_at(alpha)
        miss = abs(rng.normal()) > half
        alpha = aci_update(alpha, miss, target=0.90)
        seen.append(alpha)
    assert len(set(np.round(seen, 6))) > 1, "alpha never changed; state is not carried"


def test_requantile_beats_linear_rescale_at_high_alpha() -> None:
    """Defect 2: (0.10/alpha) rescaling is not the quantile ratio."""
    state = _pool()
    alpha = 0.40
    true_q = state.qhat_at(alpha)
    linear = state.qhat * (0.10 / alpha)
    assert linear < true_q, "linear proxy should understate the interval at high alpha"
    assert abs(linear - true_q) / true_q > 0.15, "expected a materially different width"


def test_observe_carries_state_per_cell() -> None:
    """Per-cell state persists across observe() calls and cells stay independent."""
    cal = ConformalCalibrator()
    cal.erc[("a", 4)] = _pool()
    cal.erc[("b", 4)] = _pool()
    start = cal.erc[("a", 4)].alpha
    for _ in range(10):
        lo, hi, _, _ = cal.interval("a", 4, point=0.0, kind="erc")
        cal.observe("a", 4, y=1e6, lo=lo, hi=hi, kind="erc")  # always a miss
    assert cal.erc[("a", 4)].alpha < start, "repeated misses did not lower alpha"
    assert cal.erc[("b", 4)].alpha == start, "untouched cell's state changed"
