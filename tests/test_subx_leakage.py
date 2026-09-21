"""The SubX climatology must never see the year it is used to evaluate."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from cofire.model.data.subx import (
    assert_no_self_contribution,
    coverage_note,
    fold_climatology,
    lead_climatology,
)


def _frame(years: tuple[int, ...] = (2018, 2019, 2020)) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for y in years:
        for issue in pd.date_range(f"{y}-01-01", f"{y}-12-25", freq="7D"):
            for lead in (0.5, 7.5, 14.5, 21.5):
                rows.append(
                    {
                        "issue": issue,
                        "lead": lead,
                        "pr": float(rng.normal(loc=y - 2018, scale=0.1)),
                        "is_forecast": 1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_held_out_year_contributes_nothing_to_its_own_climatology() -> None:
    f = _frame()
    _clim, used = fold_climatology(f, "pr", exclude_year=2020)
    assert_no_self_contribution(used, 2020)
    assert set(pd.to_datetime(used["issue"]).dt.year.unique()) == {2018, 2019}


def test_the_assertion_fires_when_the_year_leaks() -> None:
    """The guard must be a real check, not a comment."""
    f = _frame()
    with pytest.raises(AssertionError, match="contributed to its own"):
        assert_no_self_contribution(f, 2020)


def test_each_fold_gets_a_different_climatology() -> None:
    """A refit per fold must actually differ, or it is not being refit.

    The fixture shifts the mean by year, so excluding a different year has to
    move the climatology.
    """
    f = _frame()
    c20, _ = fold_climatology(f, "pr", exclude_year=2020)
    c18, _ = fold_climatology(f, "pr", exclude_year=2018)
    merged = c20.merge(c18, on=["lead", "woy"], suffixes=("_a", "_b"))
    assert not np.allclose(merged["pr_clim_a"], merged["pr_clim_b"]), "folds share a climatology"


def test_climatology_is_lead_dependent() -> None:
    """Bias varies by lead, so one number for all leads would be wrong."""
    f = _frame()
    clim = lead_climatology(f, "pr", hindcast_only=False)
    assert clim["lead"].nunique() > 1


def test_coverage_note_states_the_hindcast_gap() -> None:
    """The limitation travels with every run output rather than being implied."""
    note = coverage_note()
    assert "no hindcast coverage" in note
    assert "2017-09-30" in note
    assert "subx_is_forecast" in note
