"""Look 3 must refuse to run unless it is authorised and the freeze holds.

The holdout is the only data in the project that has never been optimised
against, and its value depends entirely on how few times it is examined. Every
guard here exists so that a look cannot happen by accident: not by re-running a
pipeline, not by a stale environment variable, and not by a configuration change
that resets a counter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cofire.model.look3 import (
    COND_COVERAGE_TARGET,
    COND_COVERAGE_TOL,
    LAST_ISSUE,
    MISS_RUN_BOUND,
    RELIABILITY_MAX,
    ROLL13_FLOOR,
    Criterion,
)


def test_refuses_without_authorisation(monkeypatch: pytest.MonkeyPatch) -> None:
    from cofire.model.look3 import run

    monkeypatch.delenv("COFIRE_ALLOW_LOOK", raising=False)
    with pytest.raises(SystemExit, match="COFIRE_ALLOW_LOOK=3"):
        run()


def test_refuses_on_the_wrong_look_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authorisation names the look being taken, so it cannot carry over."""
    from cofire.model.look3 import run

    monkeypatch.setenv("COFIRE_ALLOW_LOOK", "2")
    with pytest.raises(SystemExit, match="COFIRE_ALLOW_LOOK=3"):
        run()
    monkeypatch.setenv("COFIRE_ALLOW_LOOK", "4")
    with pytest.raises(SystemExit, match="COFIRE_ALLOW_LOOK=3"):
        run()


def test_refuses_when_preconditions_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Authorised but unfrozen must still not look."""
    import cofire.model.look3 as l3

    monkeypatch.setenv("COFIRE_ALLOW_LOOK", "3")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PREREGISTRATION_LOOK3.md").write_text(
        "**Config hash** sha256 `deadbeef`\n"
    )
    with pytest.raises(SystemExit, match="preconditions"):
        l3.run()


def test_criteria_match_the_preregistration() -> None:
    """The constants in code and the thresholds in the document are one thing.

    If these drift, the script tests something the document did not
    preregister, which is the failure the document exists to prevent.
    """
    doc = Path("docs/PREREGISTRATION_LOOK3.md").read_text()
    assert "≥ 0.70" in doc and ROLL13_FLOOR == 0.70
    assert "within 0.05 of 0.90" in doc
    assert COND_COVERAGE_TOL == 0.05
    assert COND_COVERAGE_TARGET == 0.90
    assert f"≤ {MISS_RUN_BOUND} consecutive cell-weeks" in doc
    assert f"≤ {RELIABILITY_MAX}" in doc


def test_the_holdout_window_stops_at_the_last_issue() -> None:
    assert LAST_ISSUE.year == 2026
    assert LAST_ISSUE.month == 9 and LAST_ISSUE.day == 22


def test_criterion_records_its_own_verdict() -> None:
    c = Criterion("2 min rolling", "larimer h2", 0.83, ">= 0.7", True)
    assert c.passed and c.observed == 0.83


def test_the_feature_builder_excludes_the_holdout() -> None:
    """The routine builder must not reach 2026, or the seal is decorative."""
    import inspect

    from cofire.model import features_a

    src = inspect.getsource(features_a.build_template)
    assert "calibrate_end" in src, "the template must stop at the calibration split"
    assert "2026" not in src
