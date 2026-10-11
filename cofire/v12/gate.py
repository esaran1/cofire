"""Stage 1's online variants through the delayed-feedback gate.

The gate (`cofire/ship/leak_gate.py`) perturbs every score not observable at
issue time and requires the output at the probe row not to move. Here the
stream's outcomes are derived from its scores (an outcome is 1 when the score
exceeds a fixed level), so perturbing an unobservable row flips its outcome,
and the predictions being recalibrated are fixed. A variant passes only if no
outcome from issue week t - h + 1 or later reaches the forecast for week t.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from cofire.ship.leak_gate import GateResult, Stream, run_gate
from cofire.v12 import recal

LEVEL = 14.0


def method(variant: recal.Online, stream: Stream, delay: int) -> Callable[[np.ndarray], np.ndarray]:
    week = stream.week_of()
    cell = np.tile(np.arange(stream.cells), stream.weeks)
    p = recal.sigmoid(-1.5 + 0.4 * np.sin(cell + 0.3 * week))

    def run(scores: np.ndarray) -> np.ndarray:
        y = (scores > LEVEL).astype(float)
        return recal.run_online(variant, (0.0, 1.0), p, y, week, delay)

    return run


def check(name: str, variant: recal.Online, horizon: int, delay: int,
          stream: Stream | None = None) -> GateResult:
    s = stream or Stream(weeks=30, cells=6)
    return run_gate(name, method(variant, s, delay), s, horizon)


def check_all(horizons: tuple[int, ...] = (2, 4, 8)) -> list[GateResult]:
    """Every online variant at its real delay. All must pass."""
    out = []
    for name, v in recal.VARIANTS.items():
        if isinstance(v, recal.Online):
            for h in horizons:
                out.append(check(name, v, h, delay=h))
    return out
