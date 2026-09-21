"""The shipping uncertainty path: reference conformal PID.

A thin wrapper over the vendored authors' implementation, so the vendored file
stays byte-identical to upstream and everything project-specific lives here.

Gains are the paper's defaults and are not searched. Searching them against the
evaluation window would be tuning against the test, which is the same rule the
Phase 4 pre-registration set and it has not changed.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402

from cofire.model.config import COVERAGE_TARGET  # noqa: E402

LOGGER = logging.getLogger("cofire.uncertainty.shipping_pid")

# Paper defaults. Csat is the saturation scale, KI the integrator gain.
LR = 0.1
C_SAT = 2.0
K_I = 1.0
T_BURNIN = 100


@dataclass
class PidRun:
    radii: np.ndarray
    covered: np.ndarray
    coverage: float
    mean_width: float
    longest_miss_run: int


def longest_miss_run(covered: np.ndarray) -> int:
    """The operational number: how long the forecast can be wrong in a row.

    Average coverage can look healthy while the misses arrive in one long
    block, which is exactly what ACI did at h8 with a 1780-step run.
    """
    best = cur = 0
    for c in covered:
        cur = 0 if c else cur + 1
        best = max(best, cur)
    return int(best)


def run_reference_pid(
    scores: Sequence[float],
    coverage_target: float = COVERAGE_TARGET,
    ahead: int = 1,
) -> PidRun:
    """Quantile plus integrator with log saturation, the paper's PI method."""
    from cofire.model.uncertainty.reference_pid import quantile_integrator_log

    s = np.asarray(scores, dtype=float)
    alpha = 1.0 - coverage_target
    # Vendored upstream code is untyped by design.
    out = quantile_integrator_log(  # type: ignore[no-untyped-call]
        s, alpha, lr=LR, Csat=C_SAT, KI=K_I, ahead=ahead,
        T_burnin=T_BURNIN, proportional_lr=True,
    )
    q = np.asarray(out["q"], dtype=float)
    covered = s <= q
    return PidRun(
        radii=q,
        covered=covered,
        coverage=float(np.mean(covered)),
        mean_width=float(2.0 * np.mean(q)),
        longest_miss_run=longest_miss_run(covered),
    )
