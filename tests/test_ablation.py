"""The ablation must not report a leak as a result.

The first ablation run scored ROC-AUC 1.000 because nine future-dated columns
were being used as predictors. These tests pin the exclusions and the reporting
conventions that keep a result honest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cofire.model.ablation import (
    FUTURE_SUFFIX,
    feature_columns,
    lift_table,
)
from cofire.model.prob_models import ablation_sets, split_groups
from cofire.model.targets import constant_event_baseline


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2020-01-07", periods=10, freq="7D"),
            "cell_id": ["c0"] * 10,
            "lat": 40.0,
            "lon": -105.0,
            "erc": np.arange(10, dtype=float),
            "usdm": np.zeros(10),
            "esi_4wk": np.arange(10, dtype=float),
            "rci_1": np.arange(10, dtype=float),
            "usdm_h4": np.arange(10, dtype=float),      # future: a leak
            "erc_pct_h2": np.arange(10, dtype=float),   # future: a leak
            "fire_index_h8": np.arange(10, dtype=float),  # future: a leak
            "d_intensify1_h4": np.zeros(10),            # target
        }
    )


def test_future_dated_columns_are_excluded() -> None:
    """The exact leak: usdm_h4 is the target shifted, never an input."""
    cols = feature_columns(_frame())
    for leak in ("usdm_h4", "erc_pct_h2", "fire_index_h8"):
        assert leak not in cols, f"{leak} is a shift(-h) of the target"


def test_ordinary_columns_survive_the_exclusion() -> None:
    """The rule must not take the real predictors with it."""
    cols = feature_columns(_frame())
    for keep in ("erc", "usdm", "esi_4wk", "rci_1"):
        assert keep in cols


def test_future_suffix_matches_only_a_trailing_horizon() -> None:
    assert FUTURE_SUFFIX.search("usdm_h4")
    assert FUTURE_SUFFIX.search("erc_pct_h12")
    assert not FUTURE_SUFFIX.search("fm100")      # a number, not a horizon
    assert not FUTURE_SUFFIX.search("rci_1")
    assert not FUTURE_SUFFIX.search("esi_4wk")


def test_targets_and_identifiers_are_excluded() -> None:
    cols = feature_columns(_frame())
    for gone in ("time", "cell_id", "lat", "lon", "d_intensify1_h4"):
        assert gone not in cols


def test_ablation_sets_are_cumulative_and_ordered() -> None:
    """Each row must price exactly one addition."""
    groups = split_groups(["pr", "erc", "esi_4wk", "rci_1"])
    sets = ablation_sets(groups)
    assert set(sets) == {"gridmet", "+esi", "+rci"}
    assert set(sets["gridmet"]) < set(sets["+esi"]) < set(sets["+rci"])
    assert "esi_4wk" in sets["+esi"] and "rci_1" not in sets["+esi"]


def test_constant_baseline_is_the_training_rate_not_the_validation_rate() -> None:
    """Using the validation rate would leak the answer into the baseline."""
    train = pd.DataFrame({"d_x": [1.0, 1.0, 0.0, 0.0]})       # 0.5
    valid = pd.DataFrame({"d_x": [0.0] * 10})                  # 0.0
    out = constant_event_baseline(train, "d_x", valid)
    assert len(out) == len(valid)
    assert np.allclose(out, 0.5), "the constant must come from training only"


def test_lift_is_the_change_from_the_previous_feature_set() -> None:
    rows = [
        {"domain": "d", "target": "t", "horizon": 4, "arm": "lightgbm",
         "feature_set": "gridmet", "bss_vs_markov": 0.10, "bss_vs_markov_lo": 0.0,
         "bss_vs_markov_hi": 0.2, "roc_auc": 0.6, "brier": 0.1},
        {"domain": "d", "target": "t", "horizon": 4, "arm": "lightgbm",
         "feature_set": "+esi", "bss_vs_markov": 0.15, "bss_vs_markov_lo": 0.05,
         "bss_vs_markov_hi": 0.25, "roc_auc": 0.62, "brier": 0.09},
    ]
    lift = lift_table(rows)
    first = lift[lift["feature_set"] == "gridmet"].iloc[0]
    second = lift[lift["feature_set"] == "+esi"].iloc[0]
    assert np.isnan(first["lift_over_previous"]), "the base set has nothing to lift over"
    assert second["lift_over_previous"] == pytest.approx(0.05)
