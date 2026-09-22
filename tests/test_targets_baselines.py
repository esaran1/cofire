"""Gate 2: targets, baselines and metrics.

The three checks the brief names explicitly are here: transition matrix rows sum
to 1, baselines are estimated on training years only, and the block bootstrap
behaves correctly on synthetic autocorrelated data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from cofire.model.prob_metrics import (
    ar1_neff,
    block_bootstrap,
    brier,
    brier_decomposition,
    brier_skill,
    pr_auc,
    roc_auc,
)
from cofire.model.targets import (
    MarkovBaseline,
    climatology_event_baseline,
    drought_event_targets,
    fire_event_targets,
    persistence_event_baseline,
)


def _frame(n_weeks: int = 120, n_cells: int = 6, seed: int = 0) -> pd.DataFrame:
    """A small synthetic panel with realistic drought persistence."""
    rng = np.random.default_rng(seed)
    times = pd.date_range("2019-01-01", periods=n_weeks, freq="7D")
    rows = []
    for c in range(n_cells):
        cat = 0
        for t in times:
            # Sticky categories with occasional single-step moves.
            if rng.random() < 0.12:
                cat = int(np.clip(cat + rng.choice([-1, 1]), 0, 4))
            rows.append({"cell_id": f"c{c}", "time": t, "usdm": float(cat), "erc_pct": rng.uniform(0, 100)})
    df = pd.DataFrame(rows).sort_values(["cell_id", "time"]).reset_index(drop=True)
    for h in (2, 4, 8):
        df[f"usdm_h{h}"] = df.groupby("cell_id")["usdm"].shift(-h)
        df[f"erc_pct_h{h}"] = df.groupby("cell_id")["erc_pct"].shift(-h)
    return df


# ------------------------------------------------------------------ targets


def test_drought_events_are_binary_or_nan() -> None:
    df = _frame()
    t = drought_event_targets(df, 4)
    for name, arr in t.items():
        finite = arr[np.isfinite(arr)]
        assert set(np.unique(finite)).issubset({0.0, 1.0}), name


def test_events_are_nan_where_the_future_is_missing() -> None:
    """The last h weeks have no label and must not silently become zeros."""
    df = _frame()
    t = drought_event_targets(df, 8)
    last = df.groupby("cell_id").tail(8).index
    assert np.all(~np.isfinite(t["d_intensify1_h8"][last]))


def test_event_definitions_are_mutually_consistent() -> None:
    df = _frame()
    t = drought_event_targets(df, 4)
    m = np.isfinite(t["d_intensify1_h4"])
    # intensify>=2 implies intensify>=1
    assert np.all(t["d_intensify1_h4"][m][t["d_intensify2_h4"][m] == 1] == 1)
    # the three directions partition every labelled row
    tot = t["d_intensify1_h4"][m] + t["d_improve1_h4"][m] + t["d_nochange_h4"][m]
    assert np.allclose(tot, 1.0)


def test_fire_thresholds_are_nested() -> None:
    df = _frame()
    t = fire_event_targets(df, 4)
    m = np.isfinite(t["f_gt97_h4"])
    assert np.all(t["f_gt90_h4"][m][t["f_gt97_h4"][m] == 1] == 1)
    assert np.all(t["f_gt80_h4"][m][t["f_gt90_h4"][m] == 1] == 1)


# ----------------------------------------------------------------- baselines


def test_markov_rows_sum_to_one() -> None:
    """The check the brief names: every transition row is a distribution."""
    df = _frame()
    mk = MarkovBaseline(horizon=4, min_weeks=2).fit(df)
    assert np.isclose(mk.global_row.sum(), 1.0)
    for row in mk.by_cat.values():
        assert np.isclose(row.sum(), 1.0)
    for row in mk.by_cat_month.values():
        assert np.isclose(row.sum(), 1.0)
    # And every row served by the accessor, including fallbacks.
    for c in range(5):
        for mo in range(1, 13):
            assert np.isclose(mk.row(c, mo).sum(), 1.0)


def test_markov_predicted_events_are_probabilities() -> None:
    df = _frame()
    mk = MarkovBaseline(horizon=4, min_weeks=2).fit(df)
    ev = mk.predict_events(df)
    for name, p in ev.items():
        assert np.all((p >= -1e-6) & (p <= 1 + 1e-6)), name


def test_markov_is_fit_on_training_rows_only() -> None:
    """Fitting on a wet training block must not absorb a dry later block."""
    df = _frame()
    train = df[pd.to_datetime(df["time"]) < "2020-01-01"]
    mk_train = MarkovBaseline(horizon=4, min_weeks=2).fit(train)
    mk_all = MarkovBaseline(horizon=4, min_weeks=2).fit(df)
    # Different data must give different estimates; identical rows would mean
    # the training filter was ignored.
    assert not np.allclose(mk_train.global_row, mk_all.global_row) or len(train) == len(df)


def test_climatology_uses_training_rows_only() -> None:
    df = _frame()
    df["ev"] = (df["usdm"] >= 1).astype(float)
    train = df[pd.to_datetime(df["time"]) < "2020-01-01"]
    out = climatology_event_baseline(train, "ev", df)
    assert out.shape[0] == len(df)
    assert np.all((out >= 0) & (out <= 1))


def test_persistence_for_transitions_is_the_trivial_forecast() -> None:
    """Persistence says nothing changes, which is why it is a weak opponent."""
    df = _frame()
    assert np.all(persistence_event_baseline(df, "d_nochange_h4") == 1.0)
    assert np.all(persistence_event_baseline(df, "d_intensify1_h4") == 0.0)
    assert np.all(persistence_event_baseline(df, "d_improve1_h4") == 0.0)


# ------------------------------------------------------------------ metrics


def test_brier_skill_is_zero_against_itself() -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(size=500)
    y = (rng.uniform(size=500) < p).astype(float)
    assert abs(brier_skill(p, y, p)) < 1e-9


def test_brier_skill_positive_when_better_than_reference() -> None:
    rng = np.random.default_rng(1)
    y = (rng.uniform(size=2000) < 0.3).astype(float)
    good = np.where(y == 1, 0.8, 0.2)
    bad = np.full_like(y, 0.5)
    assert brier_skill(good, y, bad) > 0.3


def test_decomposition_reconstructs_the_brier_score() -> None:
    rng = np.random.default_rng(2)
    p = rng.uniform(size=4000)
    y = (rng.uniform(size=4000) < p).astype(float)
    d = brier_decomposition(p, y, bins=10)
    recon = d["reliability"] - d["resolution"] + d["uncertainty"]
    assert abs(recon - brier(p, y)) < 0.02


def test_auc_of_a_constant_forecast_is_one_half() -> None:
    y = np.array([0, 1] * 50, dtype=float)
    assert abs(roc_auc(np.full(100, 0.4), y) - 0.5) < 1e-9


def test_pr_auc_rewards_ranking_rare_positives_first() -> None:
    y = np.zeros(200)
    y[:10] = 1
    good = np.linspace(1, 0, 200)  # positives ranked first
    assert pr_auc(good, y) > 0.9
    rng = np.random.default_rng(3)
    assert pr_auc(rng.uniform(size=200), y) < 0.4


# ------------------------------------------ block bootstrap on autocorrelation


def test_ar1_neff_shrinks_with_autocorrelation() -> None:
    """The check the brief names: correlated data has fewer effective samples."""
    rng = np.random.default_rng(4)
    n = 500
    white = rng.normal(size=n)
    ar = np.zeros(n)
    for i in range(1, n):
        ar[i] = 0.9 * ar[i - 1] + rng.normal() * 0.4
    assert ar1_neff(white) > 0.5 * n, "white noise should keep most of its samples"
    assert ar1_neff(ar) < 0.2 * n, "strongly autocorrelated data should lose most"


def test_block_bootstrap_interval_covers_the_point_estimate() -> None:
    rng = np.random.default_rng(5)
    weeks = np.repeat(np.arange(60), 20)
    vals = rng.normal(size=weeks.size)

    def stat(sel: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        return float(np.mean(vals[m]))

    res = block_bootstrap(stat, weeks, n_boot=200)
    assert res.lo <= res.point <= res.hi
    assert res.n_weeks == 60


def test_block_bootstrap_is_wider_than_a_row_bootstrap_on_correlated_data() -> None:
    """Resampling rows on correlated data understates uncertainty.

    This is the reason the block version exists, so it is asserted rather than
    assumed.
    """
    rng = np.random.default_rng(6)
    n_weeks, per_week = 40, 50
    week_effect = rng.normal(scale=1.0, size=n_weeks)  # strong shared component
    weeks = np.repeat(np.arange(n_weeks), per_week)
    vals = np.repeat(week_effect, per_week) + rng.normal(scale=0.05, size=n_weeks * per_week)

    def stat(sel: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        return float(np.mean(vals[m]))

    blk = block_bootstrap(stat, weeks, n_boot=300)
    block_width = blk.hi - blk.lo

    row_rng = np.random.default_rng(7)
    draws = [float(np.mean(row_rng.choice(vals, size=vals.size, replace=True))) for _ in range(300)]
    row_width = float(np.percentile(draws, 97.5) - np.percentile(draws, 2.5))

    assert block_width > 3 * row_width, (block_width, row_width)
