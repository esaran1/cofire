"""Probabilistic classifiers and the source-group ablation. HAND-REWRITE.

Order follows the brief: LightGBM classifiers per target and horizon with
isotonic recalibration on the calibration split, logistic regression on the same
features as a check on whether trees add anything, and every arm reported
against every baseline.

macOS threading: LightGBM is pinned to one thread and torch is never imported
here, so the documented OpenMP deadlock cannot be reached from this module.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

os.environ.setdefault("OMP_NUM_THREADS", "1")

LOGGER = logging.getLogger("cofire.prob_models")

# Feature groups for the ablation. gridmet is everything already in the store;
# the others are the v1 additions.
GROUP_PREFIXES: dict[str, tuple[str, ...]] = {
    "esi": ("esi_",),
    "rci": ("rci_",),
}


def split_groups(columns: list[str]) -> dict[str, list[str]]:
    """Partition feature columns into source groups."""
    out: dict[str, list[str]] = {k: [] for k in GROUP_PREFIXES}
    gridmet: list[str] = []
    for c in columns:
        placed = False
        for g, prefixes in GROUP_PREFIXES.items():
            if any(c.startswith(p) for p in prefixes):
                out[g].append(c)
                placed = True
                break
        if not placed:
            gridmet.append(c)
    out["gridmet"] = gridmet
    return out


def ablation_sets(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    """Cumulative feature sets, so each row prices one addition."""
    base = groups.get("gridmet", [])
    sets: dict[str, list[str]] = {"gridmet": list(base)}
    running = list(base)
    for g in ("esi", "rci"):
        cols = groups.get(g, [])
        if not cols:
            continue
        running = running + cols
        sets[f"+{g}"] = list(running)
    return sets


@dataclass
class ProbModelResult:
    target: str
    horizon: int
    arm: str
    feature_set: str
    domain: str
    p_valid: np.ndarray = field(repr=False)
    y_valid: np.ndarray = field(repr=False)
    weeks_valid: np.ndarray = field(repr=False)


def _xy(
    frame: pd.DataFrame, feature_cols: list[str], target: str
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    y = pd.to_numeric(frame.get(target), errors="coerce").to_numpy(dtype=float)
    m = np.isfinite(y)
    x = frame.loc[m, feature_cols].replace([np.inf, -np.inf], np.nan)
    return x, y[m], m


def fit_lightgbm_classifier(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    seed: int = 2026,
) -> np.ndarray:
    """Class-weighted LightGBM, predicting on `valid`.

    Class weighting matters: intensification by two categories is rare, and an
    unweighted objective will happily predict the base rate everywhere and score
    well on Brier while carrying no resolution at all.
    """
    import lightgbm as lgb

    xtr, ytr, _ = _xy(train, feature_cols, target)
    if xtr.empty or len(np.unique(ytr)) < 2:
        return np.full(len(valid), float(np.nanmean(ytr)) if ytr.size else 0.5, dtype="float32")

    pos = float(ytr.sum())
    neg = float(len(ytr) - pos)
    spw = (neg / pos) if pos > 0 else 1.0

    params = {
        "objective": "binary",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 40,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "verbosity": -1,
        "seed": seed,
        "num_threads": 1,
        "scale_pos_weight": spw,
    }
    ds = lgb.Dataset(xtr, label=ytr, free_raw_data=False)
    booster = lgb.train(params, ds, num_boost_round=150)
    xva = valid[feature_cols].replace([np.inf, -np.inf], np.nan)
    return np.asarray(booster.predict(xva), dtype="float32")


def fit_logistic(
    train: pd.DataFrame, valid: pd.DataFrame, feature_cols: list[str], target: str
) -> np.ndarray:
    """Logistic regression on the same features.

    The point is not to win. It is to tell whether the trees are adding
    nonlinearity or merely adding variance.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    xtr, ytr, _ = _xy(train, feature_cols, target)
    if xtr.empty or len(np.unique(ytr)) < 2:
        return np.full(len(valid), float(np.nanmean(ytr)) if ytr.size else 0.5, dtype="float32")
    med = xtr.median(numeric_only=True)
    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=400, class_weight="balanced", n_jobs=1),
    )
    pipe.fit(xtr.fillna(med), ytr)
    xva = valid[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(med)
    return np.asarray(pipe.predict_proba(xva)[:, 1], dtype="float32")


def isotonic_recalibrate(
    p_cal: np.ndarray, y_cal: np.ndarray, p_target: np.ndarray
) -> np.ndarray:
    """Fit isotonic regression on the calibration split only.

    Class weighting distorts the probability scale by design, so the raw scores
    are good at ranking and bad at calibration. Isotonic fixes the scale without
    touching the ranking, and it is fit on the calibration split so it never
    sees validation or holdout outcomes.
    """
    from sklearn.isotonic import IsotonicRegression

    m = np.isfinite(p_cal) & np.isfinite(y_cal)
    if m.sum() < 50 or len(np.unique(y_cal[m])) < 2:
        return p_target
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(p_cal[m], y_cal[m])
    return np.asarray(iso.predict(np.clip(p_target, 0, 1)), dtype="float32")
