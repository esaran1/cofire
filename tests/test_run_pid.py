"""The PID runner must not open the holdout, and must not mislabel a domain."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from cofire.model.uncertainty.run_pid import (
    _assert_is_domain,
    _assert_no_holdout,
    adoption_verdict,
    scores_for,
    transition_weeks,
)


def test_holdout_year_is_refused() -> None:
    """The look counter stays at 2. 2026 must stop the run, not warn."""
    bad = pd.DataFrame({"time": pd.to_datetime(["2023-01-03", "2026-01-06"])})
    with pytest.raises(SystemExit, match="sealed holdout"):
        _assert_no_holdout(bad, "test")


def test_clean_splits_pass_the_holdout_guard() -> None:
    ok = pd.DataFrame({"time": pd.to_datetime(["2023-01-03", "2025-12-30"])})
    _assert_no_holdout(ok, "test")  # must not raise


def test_one_domains_predictions_cannot_be_reported_as_another() -> None:
    """The bug that made both domains report identical numbers."""
    pueblo = pd.DataFrame({"lat": [37.8, 38.2, 38.4], "lon": [-104.6, -104.8, -105.0]})
    _assert_is_domain(pueblo, "pueblo")  # correct label passes
    with pytest.raises(SystemExit, match="different domain"):
        _assert_is_domain(pueblo, "larimer")


def test_adoption_requires_both_domains() -> None:
    """One domain passing is the rule untested, not the rule met."""
    one = pd.DataFrame(
        [
            {"domain": "pueblo", "arm": "aci", "mean_abs_cov_dev": 0.20, "mean_width": 100.0},
            {"domain": "pueblo", "arm": "pid_full", "mean_abs_cov_dev": 0.05, "mean_width": 90.0},
        ]
    )
    v = adoption_verdict(one)
    assert v["adopted"] is False
    assert "larimer" in str(v.get("note", ""))


def test_adoption_rejects_coverage_bought_by_width() -> None:
    """Widening is free to any method, so it cannot count as an improvement."""
    rows = []
    for dom in ("larimer", "pueblo"):
        rows += [
            {"domain": dom, "arm": "aci", "mean_abs_cov_dev": 0.20, "mean_width": 100.0},
            # Deviation improves a lot, but width grows 50%.
            {"domain": dom, "arm": "pid_full", "mean_abs_cov_dev": 0.02, "mean_width": 150.0},
        ]
    v = adoption_verdict(pd.DataFrame(rows))
    assert v["adopted"] is False, "width inflation must not buy adoption"


def test_adoption_accepts_a_genuine_improvement_on_both_domains() -> None:
    rows = []
    for dom in ("larimer", "pueblo"):
        rows += [
            {"domain": dom, "arm": "aci", "mean_abs_cov_dev": 0.20, "mean_width": 100.0},
            {"domain": dom, "arm": "pid_full", "mean_abs_cov_dev": 0.05, "mean_width": 102.0},
        ]
    v = adoption_verdict(pd.DataFrame(rows))
    assert v["adopted"] is True


def test_scores_are_ordered_by_time() -> None:
    """These controllers are sequential; storage order would measure nothing."""
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-03-07", "2023-01-03", "2023-02-07"]),
            "cell_id": ["c0"] * 3,
            "erc_pct_h4": [10.0, 20.0, 30.0],
            "erc_pct_h4_hat": [0.0, 0.0, 0.0],
        }
    )
    out = scores_for(frame, 4)
    assert list(out["time"]) == sorted(out["time"])
    assert np.allclose(out["score"], [20.0, 30.0, 10.0])


def test_transition_weeks_come_from_observations_not_predictions() -> None:
    """Defined on the observed series, so it cannot be tuned to flatter an arm."""
    src = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-10", "2023-01-17"]),
            "usdm": [1.0, 1.0, 2.0],
        }
    )
    weeks = transition_weeks(src, src)
    assert pd.Timestamp("2023-01-17") in weeks
    assert pd.Timestamp("2023-01-10") not in weeks
