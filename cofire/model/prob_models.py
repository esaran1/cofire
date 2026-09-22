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
from collections.abc import Callable
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
    """LightGBM on the natural class balance, predicting on `valid`.

    No class weighting. The earlier version set `scale_pos_weight` to the
    negative/positive ratio, which is standard practice when the goal is
    ranking, and wrong here. Weighting shifts the predicted probabilities off
    the true scale by construction, and the scale is what Brier scores. The
    result was AUC 0.598 with a Brier worse than a constant forecast: real
    discrimination, unusable probabilities.

    Recalibration cannot reliably undo it either, because the shift depends on
    the base rate and the base rate moves between the calibration years and the
    evaluation year. Fitting the model on the natural balance keeps the output
    on the probability scale to begin with.
    """
    import lightgbm as lgb

    xtr, ytr, _ = _xy(train, feature_cols, target)
    if xtr.empty or len(np.unique(ytr)) < 2:
        return np.full(len(valid), float(np.nanmean(ytr)) if ytr.size else 0.5, dtype="float32")

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
    # No `class_weight="balanced"`, for the same reason LightGBM drops
    # `scale_pos_weight`: it moves the probabilities off the scale Brier scores.
    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=400),
    )
    pipe.fit(xtr.fillna(med), ytr)
    xva = valid[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(med)
    return np.asarray(pipe.predict_proba(xva)[:, 1], dtype="float32")


def platt_recalibrate(
    p_cal: np.ndarray, y_cal: np.ndarray, p_target: np.ndarray
) -> np.ndarray:
    """Platt scaling: a logistic fit on the log-odds of the raw score.

    Replaces isotonic regression, which overfits badly here. Isotonic is
    non-parametric and needs many positive events per bin to be stable; on
    targets whose base rate is 0.4% it fits the noise in a handful of positives
    and produces a step function that does not transfer to another year. Platt
    has two parameters, so it cannot chase that noise.

    Fit on pooled out-of-fold predictions when they are available, which is what
    `out_of_fold_predictions` assembles from the LODO folds. A single
    calibration split gives one year's worth of base rate, and the base rate is
    exactly what moves between years.
    """
    from sklearn.linear_model import LogisticRegression

    m = np.isfinite(p_cal) & np.isfinite(y_cal)
    if m.sum() < 50 or len(np.unique(y_cal[m])) < 2:
        return p_target
    eps = 1e-6
    z = np.log(np.clip(p_cal[m], eps, 1 - eps) / (1 - np.clip(p_cal[m], eps, 1 - eps)))
    lr = LogisticRegression(max_iter=400)
    lr.fit(z.reshape(-1, 1), y_cal[m])
    zt = np.clip(p_target, eps, 1 - eps)
    zt = np.log(zt / (1 - zt))
    return np.asarray(lr.predict_proba(zt.reshape(-1, 1))[:, 1], dtype="float32")


def out_of_fold_predictions(
    frame: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    fold_years: tuple[int, ...],
    fit: Callable[[pd.DataFrame, pd.DataFrame, list[str], str], np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Pooled out-of-fold predictions across the LODO folds.

    For each fold year the model is fit on the other years and predicts that
    year, so every prediction is out of sample. Pooling them gives the
    calibrator several years of base-rate variation to fit against rather than
    one, which is the whole point: a calibrator fit on a single year learns that
    year's base rate and carries it into a year that does not share it.
    """
    t = pd.to_datetime(frame["time"])
    ps: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for year in fold_years:
        held = frame[t.dt.year == year]
        rest = frame[t.dt.year != year]
        if held.empty or rest.empty:
            continue
        y = pd.to_numeric(held[target], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
            continue
        ps.append(np.asarray(fit(rest, held, feature_cols, target), dtype=float))
        ys.append(y)
    if not ps:
        return np.array([]), np.array([])
    return np.concatenate(ps), np.concatenate(ys)


def out_of_fold_frame(
    frame: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    fold_years: tuple[int, ...],
    fit: Callable[[pd.DataFrame, pd.DataFrame, list[str], str], np.ndarray],
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Out-of-fold predictions, with the rows they came from.

    Returns (predictions, outcomes, rows). The rows matter when something
    downstream needs to line up another per-row quantity with these
    predictions: truncating two independently ordered arrays to a common length
    would silently pair unrelated rows.
    """
    t = pd.to_datetime(frame["time"])
    ps: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    frames: list[pd.DataFrame] = []
    for year in fold_years:
        held = frame[t.dt.year == year]
        rest = frame[t.dt.year != year]
        if held.empty or rest.empty:
            continue
        y = pd.to_numeric(held[target], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
            continue
        ps.append(np.asarray(fit(rest, held, feature_cols, target), dtype=float))
        ys.append(y)
        frames.append(held)
    if not ps:
        return np.array([]), np.array([]), frame.iloc[:0]
    return np.concatenate(ps), np.concatenate(ys), pd.concat(frames, ignore_index=True)
