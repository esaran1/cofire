"""Conformal PID control. HAND-REWRITE.

Implements the controller family of Angelopoulos, Candes and Tibshirani (2023),
"Conformal PID Control for Time Series Prediction", as the comparison arm
against adaptive conformal inference.

The framing that makes this worth doing: ACI is a pure *integral* controller on
the miss rate. It accumulates past errors and responds to them, but it carries
no term that reacts to the current error directly and no term that anticipates
where the score is heading. On a stream with slow regime change it therefore
tends to lag a drift and then overshoot the correction. Adding a proportional
term and a scorecaster is the standard control-theoretic answer.

Everything here follows `docs/PREREGISTRATION_V1.md`, whose hash was recorded in
STATUS.md before this file existed. In particular the gains are taken from the
reference construction and are **not** searched: searching them against the
evaluation window would be tuning against the test.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from cofire.model.config import COVERAGE_TARGET

LOGGER = logging.getLogger("cofire.uncertainty.pid")

# Reference gains. Fixed in the pre-registration, never searched.
K_P = 0.1
K_I = 0.01
INTEGRATOR_WINDOW = 100
# The saturation function keeps the integrator from winding up without bound
# when a long run of misses cannot be corrected by widening alone.
SATURATION = 10.0


def _saturate(x: float, limit: float = SATURATION) -> float:
    """Bounded, odd, and linear near zero: x / (1 + |x| / limit)."""
    return float(x / (1.0 + abs(x) / limit))


@dataclass
class PIDState:
    """One controller instance, stepped once per observation."""

    coverage_target: float = COVERAGE_TARGET
    k_p: float = K_P
    k_i: float = K_I
    window: int = INTEGRATOR_WINDOW
    use_p: bool = True
    use_i: bool = True
    use_scorecaster: bool = False

    # Running state
    q: float = 0.0
    errors: list[float] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)

    @property
    def alpha_target(self) -> float:
        """The miss-rate target, not the coverage target.

        Kept as a property because conflating the two is exactly the bug that
        broke ACI previously: feeding 0.90 where 0.10 belongs makes a 90% miss
        rate the only stationary point.
        """
        return 1.0 - self.coverage_target

    def _scorecast(self) -> float:
        """A one-step-ahead guess at the next score.

        Deliberately simple: the median of the recent score window. The paper
        allows an arbitrary forecaster here, but anything fit on this data would
        need its own held-out split to be honest, and the point of the arm is to
        test whether *anticipation* helps at all, not to tune a sub-model.
        """
        if len(self.scores) < 10:
            return 0.0
        recent = np.asarray(self.scores[-self.window :], dtype=float)
        return float(np.median(recent))

    def step(self, score: float) -> float:
        """Observe one conformity score, return the radius to use next.

        `score` is the conformity score of the observation just seen, on the
        same scale as the residual. The returned `q` is the radius for the next
        prediction, so the controller never sees the observation it is being
        asked to cover.
        """
        self.scores.append(float(score))
        # err > 0 means the interval missed, since the score exceeded the radius.
        missed = 1.0 if score > self.q else 0.0
        err = missed - self.alpha_target
        self.errors.append(err)

        update = 0.0
        if self.use_p:
            update += self.k_p * err
        if self.use_i:
            recent = self.errors[-self.window :]
            update += self.k_i * _saturate(float(np.sum(recent)))
        if self.use_scorecaster:
            # Pull the radius toward where the scores are sitting, scaled by the
            # same proportional gain so the arms stay comparable.
            update += self.k_p * (self._scorecast() - self.q) * 0.1

        self.q = float(max(0.0, self.q + update))
        return self.q


def run_controller(
    scores: Sequence[float],
    *,
    use_p: bool = True,
    use_i: bool = True,
    use_scorecaster: bool = False,
    coverage_target: float = COVERAGE_TARGET,
    q0: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Step a controller over a score stream.

    Returns (radii, covered). `radii[t]` is the radius *used* at step t, chosen
    before seeing `scores[t]`, so the evaluation is honest: at every step the
    controller is judged on an observation it has not yet been told about.
    """
    s = np.asarray(scores, dtype=float)
    st = PIDState(
        coverage_target=coverage_target,
        use_p=use_p,
        use_i=use_i,
        use_scorecaster=use_scorecaster,
    )
    # Warm start at an empirical quantile so the first weeks are not absurd.
    finite = s[np.isfinite(s)]
    st.q = float(q0) if q0 is not None else (
        float(np.quantile(finite[: max(10, len(finite) // 10)], coverage_target))
        if finite.size
        else 0.0
    )

    radii = np.empty(s.size, dtype=float)
    covered = np.zeros(s.size, dtype=bool)
    for t, sc in enumerate(s):
        radii[t] = st.q            # chosen before this observation is seen
        if np.isfinite(sc):
            covered[t] = sc <= st.q
            st.step(float(sc))
    return radii, covered


def split_conformal_stream(
    scores: Sequence[float], coverage_target: float = COVERAGE_TARGET, n_cal: int = 100
) -> tuple[np.ndarray, np.ndarray]:
    """Frozen split conformal: fit the radius once, never adapt.

    The control arm. If this holds coverage as well as the adaptive methods,
    then adaptivity is not buying anything on this stream, which is a reportable
    finding rather than a disappointing one.
    """
    s = np.asarray(scores, dtype=float)
    cal = s[:n_cal]
    cal = cal[np.isfinite(cal)]
    if cal.size == 0:
        return np.zeros(s.size), np.zeros(s.size, dtype=bool)
    n = cal.size
    level = min(1.0, np.ceil((n + 1) * coverage_target) / n)
    q = float(np.quantile(cal, level))
    radii = np.full(s.size, q, dtype=float)
    covered = np.isfinite(s) & (s <= q)
    return radii, covered


def aci_stream(
    scores: Sequence[float],
    coverage_target: float = COVERAGE_TARGET,
    lr: float = 0.01,
    n_cal: int = 100,
) -> tuple[np.ndarray, np.ndarray]:
    """Adaptive conformal inference over the same stream, for comparison.

    Re-quantiles the calibration pool at the current alpha rather than linearly
    rescaling a frozen radius. The linear rescale was one of the two bugs behind
    the earlier conformal collapse.
    """
    s = np.asarray(scores, dtype=float)
    pool = s[:n_cal]
    pool = np.sort(pool[np.isfinite(pool)])
    if pool.size == 0:
        return np.zeros(s.size), np.zeros(s.size, dtype=bool)

    alpha = 1.0 - coverage_target
    radii = np.empty(s.size, dtype=float)
    covered = np.zeros(s.size, dtype=bool)
    n = pool.size
    for t, sc in enumerate(s):
        level = min(1.0, np.ceil((n + 1) * (1.0 - alpha)) / n)
        idx = min(n - 1, max(0, int(np.ceil(level * n) - 1)))
        q = float(pool[idx])
        radii[t] = q
        if np.isfinite(sc):
            hit = sc <= q
            covered[t] = hit
            # Miss-rate target, not coverage target. See conformal.aci_update.
            alpha = float(np.clip(alpha + lr * ((1.0 - coverage_target) - (0.0 if hit else 1.0)), 0.01, 0.5))
    return radii, covered


ARMS = ("split", "aci", "pid_p", "pid_pi", "pid_full")


def run_arm(arm: str, scores: Sequence[float], **kw: object) -> tuple[np.ndarray, np.ndarray]:
    """Dispatch one pre-registered arm by name."""
    if arm == "split":
        return split_conformal_stream(scores)
    if arm == "aci":
        return aci_stream(scores)
    if arm == "pid_p":
        return run_controller(scores, use_p=True, use_i=False)
    if arm == "pid_pi":
        return run_controller(scores, use_p=True, use_i=True)
    if arm == "pid_full":
        return run_controller(scores, use_p=True, use_i=True, use_scorecaster=True)
    raise KeyError(f"unknown arm {arm!r}; expected one of {ARMS}")
