"""Conformal PID: the controller must never see what it is judged on.

The earlier conformal collapse came from two bugs that unit tests would have
caught: a target inversion and a linear rescale of a frozen radius. These tests
pin the equivalent properties for the PID arms.
"""

from __future__ import annotations

import numpy as np
import pytest
from cofire.model.uncertainty.pid import (
    ARMS,
    PIDState,
    _saturate,
    aci_stream,
    run_arm,
    run_controller,
    split_conformal_stream,
)


def _stream(n: int = 600, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.abs(rng.normal(size=n))


def test_alpha_target_is_the_miss_rate_not_the_coverage_rate() -> None:
    """The exact inversion that broke ACI: 0.90 where 0.10 belongs."""
    st = PIDState(coverage_target=0.90)
    assert st.alpha_target == pytest.approx(0.10)


def test_radius_is_chosen_before_the_observation_is_seen() -> None:
    """A radius that reacted to its own observation would be self-fulfilling.

    Feed a stream whose last value is enormous. If the controller peeked, the
    final radius would jump to cover it and `covered[-1]` would be True.
    """
    s = np.concatenate([_stream(300), [1e6]])
    radii, covered = run_controller(s)
    assert not covered[-1], "the controller covered a spike it should not have seen"
    assert radii[-1] < 1e5, "the radius reacted to the observation it was judging"


def test_coverage_lands_near_nominal_on_a_stationary_stream() -> None:
    """On i.i.d. scores every arm should hold roughly 0.90."""
    s = _stream(1500, seed=1)
    for arm in ARMS:
        _, covered = run_arm(arm, s)
        cov = float(covered[200:].mean())
        assert 0.80 < cov < 0.97, f"{arm} held {cov:.3f} on a stationary stream"


def test_adaptive_arms_respond_to_a_level_shift_and_split_does_not() -> None:
    """The point of adaptivity: a frozen radius should lose coverage, PID recover."""
    rng = np.random.default_rng(2)
    calm = np.abs(rng.normal(size=400))
    wild = np.abs(rng.normal(scale=4.0, size=400))
    s = np.concatenate([calm, wild])

    _, cov_split = split_conformal_stream(s)
    _, cov_pid = run_controller(s, use_p=True, use_i=True)
    late = slice(450, None)
    assert cov_split[late].mean() < 0.80, "frozen split should lose coverage after the shift"
    assert cov_pid[late].mean() > cov_split[late].mean(), "PID should recover some coverage"


def test_integrator_is_saturated_so_it_cannot_wind_up() -> None:
    assert abs(_saturate(1e9)) <= 10.0 + 1e-6
    assert _saturate(-1e9) == pytest.approx(-_saturate(1e9))
    assert _saturate(0.5) == pytest.approx(0.5, abs=0.03)  # near-linear at small input


def test_radius_never_goes_negative() -> None:
    """A negative radius is an empty interval, which is never a valid forecast."""
    rng = np.random.default_rng(3)
    s = np.abs(rng.normal(scale=0.001, size=500))  # tiny scores push q down hard
    radii, _ = run_controller(s)
    assert (radii >= 0).all()


def test_arms_are_distinguishable() -> None:
    """If P, PI and full produce identical output, the ablation measures nothing."""
    s = np.concatenate([_stream(300, 4), np.abs(np.random.default_rng(5).normal(scale=3, size=300))])
    out = {a: run_arm(a, s)[0] for a in ("pid_p", "pid_pi", "pid_full")}
    assert not np.allclose(out["pid_p"], out["pid_pi"]), "adding I changed nothing"
    assert not np.allclose(out["pid_pi"], out["pid_full"]), "adding the scorecaster changed nothing"


def test_aci_does_not_ratchet_alpha_into_collapse() -> None:
    """The historical failure: coverage decaying toward 1 - target."""
    s = _stream(2000, seed=6)
    _, covered = aci_stream(s)
    assert covered[1000:].mean() > 0.80, "ACI coverage collapsed, the target is inverted again"


def test_unknown_arm_raises_rather_than_silently_defaulting() -> None:
    with pytest.raises(KeyError):
        run_arm("pid_magic", _stream(50))
