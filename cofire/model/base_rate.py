"""Stage 1: predict the domain event rate from slow climate state. HAND-REWRITE.

The oracle decomposition showed the dominant cost is not knowing the *level* of
the event rate in the evaluation year. The rate of `d_intensify1_h4` on Pueblo
runs 0.0114 in 2024 to 0.1948 in 2018, a 17x range with no trend, and no
calibrator fit on past years can recover that.

So this predicts the level directly, from state that actually varies between
years: the Pacific (ONI, PDO), the snowpack (SNOTEL SWE percent of median) and
the land-surface memory (ESI 12WK, precipitation deficit).

Two constraints, fixed before any of it was fitted:

- **At most four slow predictors plus season.** There are roughly 400 domain
  weeks in the training record and far fewer independent episodes, so a larger
  model would fit the episodes rather than the climate.
- **One row per domain-week, not per cell.** The cells within a week are near
  duplicates: 84% of (category, month, week) blocks are more than 98% unanimous.
  Fitting on cells would claim 432x the sample size it really has.

Stage 2 uses the stage-1 logit as an offset in the cell model, so the cell model
spends its capacity on ranking cells within a week rather than on relearning the
level.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LOGGER = logging.getLogger("cofire.base_rate")

# The candidate pool. The selection rule picks at most MAX_SLOW of these.
CANDIDATES = ("oni", "pdo", "swe_pct_median", "esi_12wk", "pr_deficit_12w")
MAX_SLOW = 4
SEASON_TERMS = ("sin_doy", "cos_doy")


def domain_weeks(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    """Collapse cell-weeks to one row per week: the domain event rate.

    This is the unit the level actually lives at. Everything here is a weekly
    mean over the domain, including the predictors, so a week contributes one
    observation.
    """
    f = frame.copy()
    f["time"] = pd.to_datetime(f["time"])
    y = pd.to_numeric(f[target], errors="coerce")
    f = f.assign(_y=y)
    agg: dict[str, str] = {"_y": "mean"}
    for c in CANDIDATES:
        if c in f.columns:
            agg[c] = "mean"
    out = f.groupby("time").agg(agg).reset_index().rename(columns={"_y": "rate"})
    doy = out["time"].dt.dayofyear.to_numpy(dtype=float)
    out["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    out["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    return out.dropna(subset=["rate"])


def add_slow_predictors(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the slow-state columns the stage-1 model draws on.

    ONI and PDO come from the monthly indices with their publication lag. The
    precipitation deficit is built from what the feature store already carries.
    SNOTEL SWE and ESI 12WK are already present when their sources were fetched.
    """
    from cofire.model.data.climate_indices import attach_monthly_indices

    out = attach_monthly_indices(frame)
    # 12-week precipitation deficit: the rolling total against its own
    # week-of-year climatology, in millimetres. Negative means drier than usual.
    if "pr_roll13" in out.columns:
        t = pd.to_datetime(out["time"])
        woy = t.dt.isocalendar().week.astype(int)
        clim = out.assign(_w=woy).groupby("_w")["pr_roll13"].transform("mean")
        out["pr_deficit_12w"] = pd.to_numeric(out["pr_roll13"], errors="coerce") - clim
    return out


@dataclass
class BaseRateModel:
    """Logistic regression on domain-week rates, with a fixed size limit."""

    target: str
    predictors: tuple[str, ...] = ()
    coef: np.ndarray = field(default_factory=lambda: np.zeros(0))
    intercept: float = 0.0
    mean: np.ndarray = field(default_factory=lambda: np.zeros(0))
    scale: np.ndarray = field(default_factory=lambda: np.ones(0))
    fallback_rate: float = 0.0

    def _design(self, dw: pd.DataFrame) -> np.ndarray:
        cols = list(self.predictors) + list(SEASON_TERMS)
        x = dw.reindex(columns=cols).to_numpy(dtype=float)
        x = np.where(np.isfinite(x), x, 0.0)
        if self.mean.size:
            x = (x - self.mean) / np.where(self.scale > 0, self.scale, 1.0)
        return np.asarray(x, dtype=float)

    def fit(self, dw: pd.DataFrame, predictors: tuple[str, ...]) -> BaseRateModel:
        """Fit on domain-week rates, weighting each week equally.

        The response is a rate in [0, 1] rather than a binary outcome, so this
        is a quasi-binomial fit: the logit of the observed rate, regressed with
        ordinary least squares. That keeps it two-parameter-per-predictor small
        and avoids pretending each week is a single Bernoulli draw.
        """
        self.predictors = tuple(p for p in predictors if p in dw.columns)
        self.fallback_rate = float(np.clip(dw["rate"].mean(), 1e-4, 1 - 1e-4))
        x = self._design(dw)
        self.mean = x.mean(axis=0)
        self.scale = x.std(axis=0)
        x = self._design(dw)

        eps = 1e-3
        r = np.clip(dw["rate"].to_numpy(dtype=float), eps, 1 - eps)
        z = np.log(r / (1 - r))
        xd = np.column_stack([np.ones(len(x)), x])
        coef, *_ = np.linalg.lstsq(xd, z, rcond=None)
        self.intercept = float(coef[0])
        self.coef = np.asarray(coef[1:], dtype=float)
        return self

    def predict_logit(self, dw: pd.DataFrame) -> np.ndarray:
        if not self.predictors and self.coef.size == 0:
            p = self.fallback_rate
            return np.full(len(dw), np.log(p / (1 - p)), dtype=float)
        x = self._design(dw)
        return np.asarray(self.intercept + x @ self.coef, dtype=float)

    def predict_rate(self, dw: pd.DataFrame) -> np.ndarray:
        z = self.predict_logit(dw)
        return np.asarray(1.0 / (1.0 + np.exp(-np.clip(z, -30, 30))), dtype=float)


# The fixed stage-1 specification. Per-target forward selection chose each
# predictor on 17 to 23 of 51 fits, which is the signature of a search ranking
# noise: with roughly 400 domain weeks and few independent episodes there is not
# enough evidence to tell these apart. One specification is used for every
# target, and the ridge penalty is chosen once on pooled validation rather than
# per target.
FIXED_SPEC = CANDIDATES


def fit_ridge(
    dw: pd.DataFrame, predictors: tuple[str, ...], penalty: float
) -> BaseRateModel:
    """Ridge-penalised quasi-binomial fit on domain-week rates."""
    m = BaseRateModel(target="_")
    m.predictors = tuple(p for p in predictors if p in dw.columns)
    m.fallback_rate = float(np.clip(dw["rate"].mean(), 1e-4, 1 - 1e-4))
    x = m._design(dw)
    m.mean = x.mean(axis=0)
    m.scale = x.std(axis=0)
    x = m._design(dw)

    eps = 1e-3
    r = np.clip(dw["rate"].to_numpy(dtype=float), eps, 1 - eps)
    z = np.log(r / (1 - r))
    xd = np.column_stack([np.ones(len(x)), x])
    # Penalise the slopes, never the intercept: shrinking the intercept would
    # pull the level away from the training rate, which is the one thing the
    # model does know.
    pen = np.eye(xd.shape[1]) * penalty
    pen[0, 0] = 0.0
    coef = np.linalg.solve(xd.T @ xd + pen, xd.T @ z)
    m.intercept = float(coef[0])
    m.coef = np.asarray(coef[1:], dtype=float)
    return m


def select_penalty(
    per_target_dw: list[pd.DataFrame], fold_years: tuple[int, ...],
    grid: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0),
) -> float:
    """One penalty for every target, chosen on pooled LODO error.

    Pooled so that the choice cannot be tuned per target, which is the failure
    mode the fixed specification exists to remove.
    """
    best, best_score = grid[0], float("inf")
    for pen in grid:
        errs: list[float] = []
        for dw in per_target_dw:
            years = pd.to_datetime(dw["time"]).dt.year
            for yr in fold_years:
                tr, te = dw[years != yr], dw[years == yr]
                if len(tr) < 20 or te.empty:
                    continue
                m = fit_ridge(tr, FIXED_SPEC, pen)
                eps = 1e-3
                r = np.clip(te["rate"].to_numpy(dtype=float), eps, 1 - eps)
                errs.append(float(np.mean((m.predict_logit(te) - np.log(r / (1 - r))) ** 2)))
        score = float(np.mean(errs)) if errs else float("inf")
        LOGGER.info("penalty %.3g -> pooled LODO mse %.5f", pen, score)
        if score < best_score:
            best, best_score = pen, score
    LOGGER.info("selected penalty %.3g", best)
    return best


def select_predictors(
    dw_train: pd.DataFrame,
    target: str,
    fold_years: tuple[int, ...],
    max_slow: int = MAX_SLOW,
) -> tuple[str, ...]:
    """Forward selection on LODO folds, capped at `max_slow`.

    The cap is fixed in advance rather than chosen by the search, which is the
    whole point: with roughly 400 domain weeks and few independent episodes, a
    search allowed to grow would find episode-specific structure.
    """
    available = [c for c in CANDIDATES if c in dw_train.columns and dw_train[c].notna().any()]
    chosen: list[str] = []
    best_score = _lodo_score(dw_train, (), fold_years)
    while len(chosen) < max_slow:
        gains: list[tuple[float, str]] = []
        for cand in available:
            if cand in chosen:
                continue
            score = _lodo_score(dw_train, (*chosen, cand), fold_years)
            gains.append((score, cand))
        if not gains:
            break
        gains.sort()
        score, cand = gains[0]
        if score >= best_score - 1e-9:  # no improvement
            break
        best_score = score
        chosen.append(cand)
    LOGGER.info("%s: selected %s (LODO mse %.5f)", target, chosen or "(season only)", best_score)
    return tuple(chosen)


def _lodo_score(dw: pd.DataFrame, predictors: tuple[str, ...], fold_years: tuple[int, ...]) -> float:
    """Mean squared error on the logit scale, across held-out years."""
    errs: list[float] = []
    years = pd.to_datetime(dw["time"]).dt.year
    for y in fold_years:
        tr, te = dw[years != y], dw[years == y]
        if len(tr) < 20 or te.empty:
            continue
        m = BaseRateModel(target="_").fit(tr, predictors)
        eps = 1e-3
        r = np.clip(te["rate"].to_numpy(dtype=float), eps, 1 - eps)
        z_true = np.log(r / (1 - r))
        errs.append(float(np.mean((m.predict_logit(te) - z_true) ** 2)))
    return float(np.mean(errs)) if errs else float("inf")


def offset_logit_for_rows(
    frame: pd.DataFrame, model: BaseRateModel, dw: pd.DataFrame
) -> np.ndarray:
    """Broadcast the stage-1 weekly logit back onto cell rows."""
    z = pd.Series(model.predict_logit(dw), index=pd.to_datetime(dw["time"]))
    t = pd.to_datetime(frame["time"])
    return np.asarray(t.map(z).to_numpy(dtype=float), dtype=float)


def fit_deviation_weight(
    stage1_logit: np.ndarray, cell_score: np.ndarray, y: np.ndarray
) -> float:
    """How much the cell model's deviation is worth, fitted out of sample.

    The cell logit is not on a meaningful scale: measured on Larimer
    `f_gt90_h8` it has sd 1.88 and spans -7.9 to 2.9. Adding that to a level at
    full weight swamps the level, which is what drove the first two-stage run to
    a mean prediction of 0.1615 against an actual rate of 0.067 and a recovery of
    -18. The weight is therefore estimated rather than assumed, by a
    one-parameter logistic fit with the stage-1 logit as a fixed offset.

    Must be fitted on data the cell model did not train on, or the weight
    inherits the cell model's in-sample overconfidence.
    """
    from sklearn.linear_model import LogisticRegression

    m = np.isfinite(stage1_logit) & np.isfinite(cell_score) & np.isfinite(y)
    if m.sum() < 50 or len(np.unique(y[m])) < 2:
        return 0.0
    eps = 1e-6
    q = np.clip(cell_score[m], eps, 1 - eps)
    zc = np.log(q / (1 - q))
    dev = zc - float(np.mean(zc))
    # Fit only the slope on the deviation; the level is already carried by the
    # offset, so no intercept is estimated.
    lr = LogisticRegression(max_iter=400, fit_intercept=False)
    try:
        lr.fit(dev.reshape(-1, 1), y[m], sample_weight=None)
    except ValueError:
        return 0.0
    w = float(lr.coef_.ravel()[0])
    # A negative weight would mean the ranking is inverted, which is a finding
    # about the model rather than something to exploit, so it is floored at 0.
    return float(np.clip(w, 0.0, 1.0))


def two_stage_probability(
    stage1_logit: np.ndarray, cell_score: np.ndarray, weight: float = 1.0
) -> np.ndarray:
    """Combine the stage-1 level with the cell model's ranking.

    The cell score is re-centred on its own logit mean so it contributes only
    the *deviation* of a cell from its week, and the level comes entirely from
    stage 1. Without the re-centring the two stages would both assert a level
    and the result would double-count.

    `weight` scales the deviation. It defaults to 1.0 for the identity case but
    should normally come from `fit_deviation_weight`, because an unscaled cell
    logit overwhelms the level it is meant to refine.
    """
    eps = 1e-6
    q = np.clip(cell_score, eps, 1 - eps)
    zc = np.log(q / (1 - q))
    finite = zc[np.isfinite(zc)]
    centre = float(np.mean(finite)) if finite.size else 0.0
    z = stage1_logit + weight * (zc - centre)
    return np.asarray(1.0 / (1.0 + np.exp(-np.clip(z, -30, 30))), dtype=float)
