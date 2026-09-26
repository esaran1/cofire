"""Diagnostic: do the stage 1 survivors survive a leak-free refit?

The leak sweep (docs/LEAK_SWEEP.md) found two faults inside the frozen tree that
touch the validation-based results: training labels are `shift(-h)` with no
embargo, so the last h weeks of training rows carry outcomes from the
evaluation period, and within leave-one-year-out folds the `erc_pct` pools
include the held-out year itself. This module refits outside the frozen path
with both removed and reruns the stage 1 survivor test exactly as it was run:
the paired real-minus-shuffled BSS, circular block bootstrap, BH at q=0.10
across everything, Holm within event families, 12 positive weeks minimum.

Nothing here ships. The frozen functions are imported, never edited.

Two parts:

1. Stage 1 itself has one boundary, train 2007-2021 then validation 2022-2023.
   Every fit, the models and the reference baselines alike, drops training rows
   whose label lands after 2021-12-31. `erc_pct` for this split is recomputed
   from training years only and asserted equal to the stored values, which
   were already built that way; the self-inclusion fault lives in the folds.
2. The only fold-based choice that feeds stage 1 is the fire family, transition
   table against damped logistic (drought has one candidate). It is redone with
   `erc_pct` recomputed per fold from that fold's training years and an h-week
   embargo before each held-out year, to check the shipped family still wins.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LOGGER = logging.getLogger("cofire.ship.sensitivity")
OUT = Path("artifacts/audit")
DOMAINS = ("larimer", "pueblo")


def _raw(dom: str) -> tuple[pd.DataFrame, Any]:
    from cofire.model.config import get_settings
    from cofire.model.features_a import load as load_a

    os.environ["COFIRE_SUBSET_NAME"] = dom
    get_settings.cache_clear()
    st = get_settings()
    f = load_a(st)
    f["time"] = pd.to_datetime(f["time"])
    return f, st


def _with_targets(frame: pd.DataFrame, pct: np.ndarray) -> pd.DataFrame:
    from cofire.model.features_a import add_horizons
    from cofire.model.targets import HORIZONS, all_event_targets

    g = frame.copy()
    g["erc_pct"] = pct
    g = add_horizons(g, HORIZONS)
    return all_event_targets(g, HORIZONS)


def _embargo(train: pd.DataFrame, before: pd.Timestamp, h: int) -> pd.DataFrame:
    """Drop training rows whose h-week label lands on or after `before`."""
    t = pd.to_datetime(train["time"])
    return train[t + pd.Timedelta(weeks=h) < before]


def stage1(n_boot: int = 400, n_shuffles: int = 20) -> pd.DataFrame:
    from cofire.model.erc_pct import erc_percentile_reference
    from cofire.model.multiplicity import ALPHA_HOLM, Q, family_of
    from cofire.model.prob_metrics import brier
    from cofire.model.shipping import _drought_prediction, _fire_prediction
    from cofire.model.shipping import load as load_choices
    from cofire.model.stats_lib import (
        bootstrap_pvalue,
        multipletests_bh,
        multipletests_holm,
        paired_bss_shuffled,
    )
    from cofire.model.targets import fire_transition_baseline, seasonal_climatology_baseline

    choices = load_choices(out_dir=Path("artifacts/rerun_a"))
    rows: list[dict[str, Any]] = []
    for dom in DOMAINS:
        f, st = _raw(dom)
        t = f["time"]
        upto = f[t <= pd.Timestamp(st.valid_end)].reset_index(drop=True)
        tt = upto["time"]
        train_end = pd.Timestamp(st.train_end)
        pct = erc_percentile_reference(upto, (tt <= train_end).to_numpy())
        stored = pd.to_numeric(upto["erc_pct"], errors="coerce").to_numpy(float)
        assert np.allclose(pct, stored, equal_nan=True), (
            f"{dom}: stored erc_pct differs from a training-years-only recomputation"
        )
        g = _with_targets(upto, pct)
        gt = g["time"]
        train = g[gt <= train_end]
        valid = g[(gt >= pd.Timestamp(st.valid_start)) & (gt <= pd.Timestamp(st.valid_end))]
        weeks = pd.to_datetime(valid["time"]).to_numpy()
        for (target, h), c in sorted(choices.items()):
            if target not in valid.columns:
                continue
            y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
                continue
            clean = _embargo(train, train_end + pd.Timedelta(days=1), h)
            lab_t = pd.to_datetime(clean["time"]) + pd.Timedelta(weeks=h)
            assert (lab_t <= train_end).all(), "a training label lands in the evaluation period"
            pred = (
                _drought_prediction(h, clean, target, valid)
                if c.family == "markov"
                else _fire_prediction(c.family, clean, target, valid)
            )
            fire = target.startswith("f_gt")
            ref = (
                fire_transition_baseline(clean, target, valid)
                if fire
                else seasonal_climatology_baseline(clean, target, valid)
            )
            res = paired_bss_shuffled(pred, ref, y, weeks, n_boot=n_boot, n_shuffles=n_shuffles)
            p = bootstrap_pvalue(res)
            m = np.isfinite(pred) & np.isfinite(ref) & np.isfinite(y)
            rows.append({
                "domain": dom, "target": target, "horizon": h, "family": family_of(target),
                "arm": c.family, "n_positive_weeks": res.n_positive_weeks,
                "estimable": res.estimable,
                "paired_diff": res.point, "paired_lo": res.lo, "paired_hi": res.hi,
                "ci_above_zero": bool(np.isfinite(res.lo) and res.lo > 0),
                "pvalue": p,
                "bss_vs_ref": 1.0 - brier(pred[m], y[m]) / brier(ref[m], y[m]) if m.any() else np.nan,
                "rows_dropped_by_embargo": int(len(train) - len(clean)),
            })
            LOGGER.info("%s %-16s paired=%+.4f [%+.4f, %+.4f]", dom, target, res.point, res.lo, res.hi)

    df = pd.DataFrame(rows)
    est = df["estimable"] & df["pvalue"].notna()
    df["bh_reject"] = False
    if est.any():
        df.loc[est, "bh_reject"] = multipletests_bh(df.loc[est, "pvalue"].tolist(), q=Q)
    df["holm_reject"] = False
    for _key, grp in df[est].groupby(["domain", "family"]):
        df.loc[grp.index, "holm_reject"] = multipletests_holm(grp["pvalue"].tolist(), alpha=ALPHA_HOLM)
    df["survivor"] = df["estimable"] & df["ci_above_zero"] & df["bh_reject"] & df["holm_reject"]
    return df


def fire_family_choice() -> pd.DataFrame:
    """Transition against damped, per fold, leak-free. Mean Brier over folds."""
    from cofire.model.erc_pct import erc_percentile_reference
    from cofire.model.prob_metrics import brier
    from cofire.model.shipping import FOLD_YEARS, _fire_prediction
    from cofire.model.targets import HORIZONS, target_names

    fire_targets = [(tg, h) for h in HORIZONS for tg in target_names((h,)) if tg.startswith("f_gt")]
    rows: list[dict[str, Any]] = []
    for dom in DOMAINS:
        f, st = _raw(dom)
        period = f[f["time"] <= pd.Timestamp(st.train_end)].reset_index(drop=True)
        yr = period["time"].dt.year
        for year in FOLD_YEARS:
            # Percentile pools from this fold's training years only.
            pct = erc_percentile_reference(period, (yr != year).to_numpy())
            g = _with_targets(period, pct)
            gy = g["time"].dt.year
            held = g[gy == year]
            start = pd.Timestamp(f"{year}-01-01")
            for target, h in fire_targets:
                fit = g[gy != year]
                fit = fit[~((fit["time"] < start) & (fit["time"] + pd.Timedelta(weeks=h) >= start))]
                y = pd.to_numeric(held[target], errors="coerce").to_numpy(float)
                for arm in ("transition", "damped"):
                    p = _fire_prediction(arm, fit, target, held)
                    m = np.isfinite(p) & np.isfinite(y)
                    rows.append({"domain": dom, "year": year, "target": target, "horizon": h,
                                 "arm": arm, "brier": brier(p[m], y[m]) if m.any() else np.nan})
            LOGGER.info("%s fold %d done", dom, year)
    df = pd.DataFrame(rows)
    return df.groupby(["target", "horizon", "arm"], as_index=False)["brier"].mean()


def run() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    after = stage1()
    after.to_csv(OUT / "survivors_embargoed.csv", index=False)
    fam = fire_family_choice()
    fam.to_csv(OUT / "fire_family_embargoed.csv", index=False)
    return OUT


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
