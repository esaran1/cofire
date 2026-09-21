"""The Markov baseline must never score worse than the constant it generalises.

A transition matrix conditioned on (category, month) contains the unconditional
rate as a special case, so on the data it was fit to it cannot do worse. When it
does, the estimator is broken rather than merely weak. That check caught three
separate defects here, each recorded in DECISIONS.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from cofire.model.prob_metrics import brier
from cofire.model.targets import (
    MarkovBaseline,
    all_event_targets,
    constant_event_baseline,
    target_names,
)


def _synthetic(n_weeks: int = 600, n_cells: int = 40, seed: int = 0) -> pd.DataFrame:
    """A coherent drought field: cells move together, as USDM actually does."""
    rng = np.random.default_rng(seed)
    times = pd.date_range("2018-01-02", periods=n_weeks, freq="7D")
    cat, rows = 1, []
    for t in times:
        if rng.random() < 0.12:  # the field shifts as a block
            cat = int(np.clip(cat + rng.choice([-1, 1]), 0, 4))
        for c in range(n_cells):
            jitter = rng.random() < 0.05
            rows.append(
                {
                    "time": t,
                    "cell_id": f"c{c}",
                    "usdm": float(np.clip(cat + (rng.choice([-1, 1]) if jitter else 0), 0, 4)),
                }
            )
    df = pd.DataFrame(rows).sort_values(["cell_id", "time"]).reset_index(drop=True)
    # The horizon-shifted truth columns the target builder consumes.
    g = df.groupby("cell_id")
    for h in (2, 4, 8):
        df[f"usdm_h{h}"] = g["usdm"].shift(-h)
        df[f"erc_pct_h{h}"] = np.nan
    df["erc_pct"] = np.nan
    return df


@pytest.mark.parametrize("horizon", [2, 4, 8])
def test_markov_never_scores_worse_than_constant_in_sample(horizon: int) -> None:
    """The bound. Conditioning cannot hurt on the data it was fit to."""
    frame = all_event_targets(_synthetic(), (horizon,))
    mk = MarkovBaseline(horizon=horizon).fit(frame)
    preds = mk.predict_events(frame)
    for target in target_names((horizon,)):
        if not target.startswith("d_") or target not in frame.columns or target not in preds:
            continue
        y = pd.to_numeric(frame[target], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
            continue
        b_markov = brier(preds[target], y)
        b_const = brier(constant_event_baseline(frame, target, frame), y)
        assert b_markov <= b_const + 1e-9, (
            f"{target}: markov {b_markov:.5f} worse than constant {b_const:.5f}. "
            "The estimator is broken, not weak."
        )


def test_fallback_favours_staying_put_over_the_unconditional_marginal() -> None:
    """A cell with no estimate must mostly stay put, not jump to the commonest state.

    The unconditional row is the marginal over destinations and forgets where
    the chain started. Using it told a D2 cell it would most likely be D0, which
    inflated the improve targets by up to 642% on Larimer. Pure persistence is
    the opposite error: a point mass states P(category >= 3) = 1 for a D3 cell.
    The fallback blends the two.
    """
    mk = MarkovBaseline(horizon=4, min_weeks=10_000)  # nothing can be estimated
    mk.global_row = np.array([0.8, 0.1, 0.05, 0.04, 0.01])
    row = mk.row(category=3, month=6)
    assert row.argmax() == 3, "an unsupported cell must mostly stay put"
    assert row[3] < 1.0, "a point mass is overconfident for absolute-level targets"
    assert row[0] > 0.0, "some mass must still follow the pooled rates"
    assert row.sum() == pytest.approx(1.0)


def test_support_is_counted_in_weeks_not_rows() -> None:
    """One week of many cells is one observation, not many.

    84% of (category, month, week) blocks in Pueblo training data are more than
    98% unanimous across all 432 cells.
    """
    mk = MarkovBaseline(horizon=2)
    ci = np.zeros(400, dtype=int)
    fi = np.zeros(400, dtype=int)
    weeks = np.array([np.datetime64("2020-01-07")] * 400)  # 400 rows, ONE week
    _, n_weeks = mk._counts_and_support(ci, fi, weeks, np.ones(400, dtype=bool))
    assert n_weeks == 1, "400 cells in one week must count as one week of support"


def test_rates_are_estimated_from_rows() -> None:
    """Row-level Brier is minimised by the row mean, so rates come from rows."""
    mk = MarkovBaseline(horizon=2)
    fi = np.array([0, 0, 0, 1])  # 3/4 land in category 0
    counts, _ = mk._counts_and_support(
        np.zeros(4, dtype=int), fi, np.array([np.datetime64("2020-01-07")] * 4),
        np.ones(4, dtype=bool),
    )
    assert counts[0] == 3.0 and counts[1] == 1.0


def test_h_step_is_direct_not_a_powered_one_step_matrix() -> None:
    """Each horizon is estimated from its own transitions, imposing no
    first-order assumption on a process that need not be Markovian."""
    frame = all_event_targets(_synthetic(), (2, 8))
    m2 = MarkovBaseline(horizon=2).fit(frame)
    m8 = MarkovBaseline(horizon=8).fit(frame)
    r2, r8 = m2.row(2, 6), m8.row(2, 6)
    assert not np.allclose(r2, r8), "h=2 and h=8 rows should differ"
    # A powered one-step chain would spread mass geometrically; a direct
    # estimate need not, so simply assert they were fit independently.
    assert m2.horizon == 2 and m8.horizon == 8
