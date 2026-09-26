"""The delayed-feedback gate, run in CI on synthetic streams.

A forecast issued in week w for horizon h may use an observation only if its
outcome week is w - h or earlier. The look-3 interval tests broke that rule
through same-week updates, and nothing in the suite could have caught it. This
suite now does, for any method that maps a score stream to radii.

The gate is demonstrated, not asserted: a toy method with a known answer must
fail under same-week feedback and pass under an h-week delay, or the gate
itself is broken. Then every sequential method in the repo is run through it,
and its recorded result is checked, so a change in any method's status fails
the build until the record is updated deliberately.
"""

from __future__ import annotations

import pytest
from cofire.ship.leak_gate import Stream, lagged_running_quantile, registry, run_gate

STREAM = Stream(weeks=24, cells=8)

# The recorded result of the gate for every sequential method, at h = 2.
# True means it passes. Only the diagnostic passes; see leak_gate.py.
EXPECTED_PASS = {
    "reference PID, ahead=1 (as run for look 3)": False,
    "reference PID, ahead=16 (h-week delay)": False,
    "in-house PID, P only": False,
    "in-house PID, PI": False,
    "in-house PID, full": False,
    "ACI stream": False,
    "split conformal stream": False,
    "per-cell ACI (ConformalCalibrator)": False,
    "reference PID, ahead=16, fixed step (diagnostic)": True,
}


@pytest.mark.parametrize("h", [2, 4, 8])
def test_known_answer_same_week_feedback_fails(h: int) -> None:
    """Seeing the previous row, another cell in the same week, must be caught."""
    stream = Stream(weeks=max(24, h + 12), cells=8)
    r = run_gate("toy, lag 1 row", lagged_running_quantile(1), stream, h)
    assert not r.passed
    assert len(r.leaking_probes) >= r.probes * 0.9


@pytest.mark.parametrize("h", [2, 4, 8])
def test_known_answer_h_week_delay_passes(h: int) -> None:
    """Seeing only rows from week w - h and earlier must pass at every probe."""
    stream = Stream(weeks=max(24, h + 12), cells=8)
    r = run_gate("toy, h-week delay", lagged_running_quantile(h * stream.cells), stream, h)
    assert r.passed, f"leaked at rows {r.leaking_probes[:5]}"


def test_a_delay_one_row_short_is_caught() -> None:
    """The gate is exact at the boundary: h weeks of rows minus one leaks."""
    h = 2
    r = run_gate("toy, one row short", lagged_running_quantile(h * STREAM.cells - 1), STREAM, h)
    assert not r.passed


@pytest.mark.parametrize(("name", "method", "ships"), registry(STREAM, 2), ids=lambda v: v if isinstance(v, str) else "")
def test_every_sequential_method_matches_its_recorded_result(name: str, method: object, ships: bool) -> None:
    r = run_gate(name, method, STREAM, 2)  # type: ignore[arg-type]
    assert name in EXPECTED_PASS, f"{name} is not in the recorded results"
    assert r.passed == EXPECTED_PASS[name], (
        f"{name}: gate {'passed' if r.passed else 'failed'} but the record says "
        f"{'pass' if EXPECTED_PASS[name] else 'fail'}. Update EXPECTED_PASS only "
        "after checking why the method changed."
    )
    # The permanent rule: nothing that reaches a user may use the future.
    if ships:
        assert r.passed, f"{name} ships but uses information unavailable at issue time"


def test_no_forecast_band_is_rendered_without_a_passing_method() -> None:
    """A band may only reach the app if the method behind it passes the gate.

    No shipping method passes, so no continuous horizon may render an interval.
    """
    from cofire.ship.rendering import INTERVAL, continuous_decisions

    shipped_passing = any(ships and EXPECTED_PASS.get(name, False) for name, _, ships in registry(STREAM, 2))
    if not shipped_passing:
        assert all(d.state != INTERVAL for d in continuous_decisions())
