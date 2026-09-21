"""Stage 1 predicts a level, on the right unit, under a fixed size cap."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from cofire.model.base_rate import (
    MAX_SLOW,
    BaseRateModel,
    domain_weeks,
    offset_logit_for_rows,
    select_predictors,
    two_stage_probability,
)


def _panel(n_weeks: int = 200, n_cells: int = 30, seed: int = 0) -> pd.DataFrame:
    """A panel whose event rate genuinely tracks a slow predictor."""
    rng = np.random.default_rng(seed)
    times = pd.date_range("2018-01-02", periods=n_weeks, freq="7D")
    rows = []
    for i, t in enumerate(times):
        oni = np.sin(i / 26.0) * 1.5           # a slow oscillation
        rate = 1.0 / (1.0 + np.exp(-(-2.0 + 1.2 * oni)))
        for c in range(n_cells):
            rows.append(
                {
                    "time": t,
                    "cell_id": f"c{c}",
                    "oni": oni,
                    "pdo": rng.normal(),        # pure noise, must not be chosen first
                    "y": float(rng.random() < rate),
                }
            )
    return pd.DataFrame(rows)


def test_domain_weeks_collapses_cells_to_one_row_per_week() -> None:
    """The unit matters: cells within a week are near duplicates."""
    df = _panel()
    dw = domain_weeks(df, "y")
    assert len(dw) == df["time"].nunique()
    assert "rate" in dw and dw["rate"].between(0, 1).all()


def test_the_fitted_model_tracks_a_real_slow_signal() -> None:
    df = _panel()
    dw = domain_weeks(df, "y")
    m = BaseRateModel(target="y").fit(dw, ("oni",))
    pred = m.predict_rate(dw)
    assert np.corrcoef(pred, dw["rate"])[0, 1] > 0.7, "should track the driving signal"


def test_selection_respects_the_fixed_cap() -> None:
    """The cap is fixed in advance, not chosen by the search."""
    df = _panel()
    dw = domain_weeks(df, "y")
    chosen = select_predictors(dw, "y", (2019, 2020), max_slow=MAX_SLOW)
    assert len(chosen) <= MAX_SLOW


def test_selection_prefers_the_informative_predictor_over_noise() -> None:
    df = _panel()
    dw = domain_weeks(df, "y")
    chosen = select_predictors(dw, "y", (2019, 2020), max_slow=2)
    assert not chosen or chosen[0] == "oni", f"picked {chosen} over the real driver"


def test_a_model_with_no_predictors_returns_the_training_level() -> None:
    """The degenerate case must still be a usable forecast."""
    df = _panel()
    dw = domain_weeks(df, "y")
    m = BaseRateModel(target="y")
    m.fallback_rate = 0.25
    out = m.predict_rate(dw)
    assert np.allclose(out, 0.25)


def test_two_stage_takes_its_level_from_stage_one() -> None:
    """The cell score contributes ranking, not level, or the two double-count."""
    stage1 = np.full(100, np.log(0.2 / 0.8))       # level 0.2
    cell = np.full(100, 0.9)                        # a confident but flat score
    out = two_stage_probability(stage1, cell)
    assert np.allclose(out, 0.2, atol=1e-6), "a flat cell score must not shift the level"


def test_two_stage_preserves_the_cell_ranking() -> None:
    stage1 = np.full(6, np.log(0.1 / 0.9))
    cell = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    out = two_stage_probability(stage1, cell)
    assert np.all(np.diff(out) > 0), "ranking must survive the combination"


def test_offset_broadcasts_weekly_logits_onto_cell_rows() -> None:
    df = _panel(n_weeks=10, n_cells=4)
    dw = domain_weeks(df, "y")
    m = BaseRateModel(target="y").fit(dw, ("oni",))
    z = offset_logit_for_rows(df, m, dw)
    assert z.shape[0] == len(df)
    # Every row in one week shares that week's level.
    first = df["time"] == df["time"].iloc[0]
    assert np.allclose(z[first.to_numpy()], z[first.to_numpy()][0])


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_non_finite_predictors_do_not_propagate(bad: float) -> None:
    """A missing index value must not turn the whole week's forecast into NaN."""
    df = _panel(n_weeks=40, n_cells=5)
    df.loc[df.index[:5], "oni"] = bad
    dw = domain_weeks(df, "y")
    m = BaseRateModel(target="y").fit(dw, ("oni",))
    out = m.predict_rate(dw)
    assert np.isfinite(out).all()


def test_deviation_weight_is_zero_when_the_ranking_is_worthless() -> None:
    """A cell score unrelated to the outcome must not be given weight.

    The first two-stage run added the raw cell logit at full weight, which has
    sd 1.88 and spans -7.9 to 2.9 on real data. That swamped the level it was
    meant to refine and drove the recovery to -18.
    """
    from cofire.model.base_rate import fit_deviation_weight

    rng = np.random.default_rng(0)
    n = 500
    z1 = np.full(n, np.log(0.1 / 0.9))
    noise = rng.uniform(0.01, 0.99, size=n)          # unrelated to y
    y = (rng.random(n) < 0.1).astype(float)
    w = fit_deviation_weight(z1, noise, y)
    assert 0.0 <= w < 0.2, f"a worthless ranking earned weight {w}"


def test_deviation_weight_is_positive_when_the_ranking_is_informative() -> None:
    from cofire.model.base_rate import fit_deviation_weight

    rng = np.random.default_rng(1)
    n = 2000
    z1 = np.full(n, np.log(0.2 / 0.8))
    signal = rng.uniform(0.02, 0.98, size=n)
    y = (rng.random(n) < signal).astype(float)        # y really follows the score
    w = fit_deviation_weight(z1, signal, y)
    assert w > 0.1, f"an informative ranking earned only {w}"


def test_deviation_weight_never_goes_negative() -> None:
    """An inverted ranking is a finding, not something to exploit."""
    from cofire.model.base_rate import fit_deviation_weight

    rng = np.random.default_rng(2)
    n = 1000
    z1 = np.full(n, np.log(0.3 / 0.7))
    score = rng.uniform(0.02, 0.98, size=n)
    y = (rng.random(n) < (1 - score)).astype(float)   # deliberately inverted
    assert fit_deviation_weight(z1, score, y) >= 0.0


def test_zero_weight_reduces_to_the_stage_one_level() -> None:
    from cofire.model.base_rate import two_stage_probability

    z1 = np.full(50, np.log(0.25 / 0.75))
    out = two_stage_probability(z1, np.linspace(0.05, 0.95, 50), weight=0.0)
    assert np.allclose(out, 0.25, atol=1e-6)
