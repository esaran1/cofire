"""The delayed-feedback gate: does a sequential method use the future?

A forecast issued in week w for horizon h may use an observation only if that
observation was known at issue time: its outcome week is w - h or earlier. The
look-3 interval tests broke this rule. Rows were streamed week by week, cell by
cell, and each interval was adjusted by the error of another cell in the same
week, which is not known for h weeks.

The gate tests information flow directly rather than inferring it from
coverage. For a probe row in week w it perturbs every score that was not
observable at issue time (any row in week w - h + 1 or later, which includes
the probe row itself and every other cell in its week) and reruns the method.
If the output at the probe row moves, the method used information it could not
have had. That is a definite result, not a statistical one, and it treats the
method as a black box, so it applies to anything that maps a score stream to
radii.

Everything here runs on synthetic streams, so it needs no data and runs in CI.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

Method = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class Stream:
    """A synthetic score stream ordered by issue week, then cell."""

    weeks: int
    cells: int
    seed: int = 7

    @property
    def n(self) -> int:
        return self.weeks * self.cells

    def scores(self) -> np.ndarray:
        # A shared weekly shock plus per-cell noise: the structure that makes
        # same-week information valuable, and so tempting to leak.
        rng = np.random.default_rng(self.seed)
        shock = np.repeat(rng.gamma(2.0, 6.0, self.weeks), self.cells)
        return np.abs(shock + rng.normal(0.0, 4.0, self.n))

    def week_of(self) -> np.ndarray:
        return np.repeat(np.arange(self.weeks), self.cells)


@dataclass
class GateResult:
    name: str
    horizon: int
    passed: bool
    probes: int
    leaking_probes: list[int] = field(default_factory=list)

    @property
    def first_leak(self) -> int | None:
        return self.leaking_probes[0] if self.leaking_probes else None


def _same(a: float, b: float) -> bool:
    if np.isinf(a) and np.isinf(b):
        return bool(np.sign(a) == np.sign(b))
    if np.isnan(a) and np.isnan(b):
        return True
    return bool(abs(a - b) <= 1e-9 * max(1.0, abs(a)))


def run_gate(
    name: str,
    method: Method,
    stream: Stream,
    horizon: int,
    probe_every: int = 3,
    bump: float = 37.0,
) -> GateResult:
    """Check every probe row's output is invariant to unobservable scores."""
    s = stream.scores()
    week = stream.week_of()
    base = np.asarray(method(s.copy()), dtype=float)
    probes = [i for i in range(0, stream.n, probe_every) if week[i] >= horizon]
    leaks: list[int] = []
    for i in probes:
        unknown = week >= week[i] - horizon + 1
        s2 = s.copy()
        s2[unknown] += bump
        out = np.asarray(method(s2), dtype=float)
        if not _same(float(base[i]), float(out[i])):
            leaks.append(i)
    return GateResult(name, horizon, not leaks, len(probes), leaks)


def lagged_running_quantile(lag_rows: int, q: float = 0.9) -> Method:
    """A toy method with a known answer, for demonstrating the gate.

    The radius at row i is the q-quantile of every score up to row i - lag_rows.
    With lag_rows = 1 it sees the previous row, which in a week-then-cell stream
    is another cell in the same week, so it must fail. With lag_rows equal to h
    weeks of rows it sees only what was known at issue time, so it must pass.
    """

    def method(s: np.ndarray) -> np.ndarray:
        out = np.full(s.size, np.inf)
        for i in range(s.size):
            end = i - lag_rows + 1
            if end >= 10:
                out[i] = float(np.quantile(s[:end], q))
        return out

    return method


# ---------------------------------------------------------------------------
# Adapters for every method in the repo that updates state sequentially.
# Each maps a score stream to the radius used at each row, exactly as the
# method would be run on real data.
# ---------------------------------------------------------------------------


def reference_pid(ahead: int) -> Method:
    """The vendored conformal PID controller, through the shipping wrapper."""

    def method(s: np.ndarray) -> np.ndarray:
        if not hasattr(np, "infty"):
            np.infty = np.inf  # type: ignore[attr-defined]  # vendored code predates NumPy 2
        from cofire.model.uncertainty.shipping_pid import run_reference_pid

        return np.asarray(run_reference_pid(s.tolist(), ahead=ahead).radii, dtype=float)

    return method


def inhouse_pid(arm: str) -> Method:
    """The in-house PID arms (pid_p, pid_pi, pid_full) and the other stream arms."""

    def method(s: np.ndarray) -> np.ndarray:
        from cofire.model.uncertainty.pid import run_arm

        radii, _ = run_arm(arm, s.tolist())
        return np.asarray(radii, dtype=float)

    return method


def per_cell_aci(horizon: int, cells: int) -> Method:
    """ConformalCalibrator with online ACI updates, as the v0.6 hindcast ran it.

    The residual pool comes from outside the stream, so only the online alpha
    update is under test.
    """

    def method(s: np.ndarray) -> np.ndarray:
        import pandas as pd

        from cofire.model.conformal import CellState, ConformalCalibrator, attach_intervals

        rng = np.random.default_rng(99)
        pool = sorted(float(v) for v in np.abs(rng.normal(0.0, 10.0, 200)))
        cal = ConformalCalibrator()
        for c in range(cells):
            cal.erc[(f"c{c}", horizon)] = CellState(qhat=pool[179], alpha=0.1, n_cal=200, resid_abs=pool)
        weeks = np.repeat(np.arange(s.size // cells), cells)
        frame = pd.DataFrame({
            "time": pd.Timestamp("2022-01-04") + pd.to_timedelta(weeks * 7, unit="D"),
            "cell_id": [f"c{c}" for c in np.tile(np.arange(cells), s.size // cells)],
            f"erc_pct_h{horizon}_hat": 0.0,
            f"erc_pct_h{horizon}": s,
        })
        out = attach_intervals(frame, cal, update_aci=True)
        half: np.ndarray = (
            (out[f"erc_pct_h{horizon}_hi"] - out[f"erc_pct_h{horizon}_lo"]) / 2
        ).to_numpy(dtype=float)
        return half

    return method


def reference_pid_fixed_step(ahead: int) -> Method:
    """The vendored controller with its proportional step size turned off.

    Diagnostic only, not a shipped configuration. The reference implementation
    scales its step size by the range of the most recent 100 scores at every
    step, ignoring `ahead`, so same-week information enters through the step
    size even when the update itself is lagged. Turning that option off is the
    only change, and it makes the lagged controller pass.
    """

    def method(s: np.ndarray) -> np.ndarray:
        if not hasattr(np, "infty"):
            np.infty = np.inf  # type: ignore[attr-defined]
        from cofire.model.uncertainty.reference_pid import quantile_integrator_log
        from cofire.model.uncertainty.shipping_pid import C_SAT, K_I, LR, T_BURNIN

        out = quantile_integrator_log(  # type: ignore[no-untyped-call]
            s, 0.1, lr=LR, Csat=C_SAT, KI=K_I, ahead=ahead, T_burnin=T_BURNIN, proportional_lr=False
        )
        return np.asarray(out["q"], dtype=float)

    return method


def registry(stream: Stream, horizon: int) -> list[tuple[str, Method, bool]]:
    """(name, method, ships) for every sequential method in the repo.

    `ships` is True only for a method whose output reaches a user. None does:
    since the look-3 correction the app draws no forecast band.
    """
    lag = horizon * stream.cells
    return [
        ("reference PID, ahead=1 (as run for look 3)", reference_pid(1), False),
        (f"reference PID, ahead={lag} (h-week delay)", reference_pid(lag), False),
        ("in-house PID, P only", inhouse_pid("pid_p"), False),
        ("in-house PID, PI", inhouse_pid("pid_pi"), False),
        ("in-house PID, full", inhouse_pid("pid_full"), False),
        ("ACI stream", inhouse_pid("aci"), False),
        ("split conformal stream", inhouse_pid("split"), False),
        ("per-cell ACI (ConformalCalibrator)", per_cell_aci(horizon, stream.cells), False),
        (f"reference PID, ahead={lag}, fixed step (diagnostic)", reference_pid_fixed_step(lag), False),
    ]
