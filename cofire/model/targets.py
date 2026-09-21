"""Probabilistic targets and their baselines. INTENDED FOR HAND-REWRITE.

Why the targets changed
-----------------------
MAE on a drought *level* structurally favours persistence: USDM categories are
piecewise constant for weeks at a time, so "same as today" is close to optimal
on most rows and the loss is dominated by the many rows where nothing happened.
Regressing the *delta* failed for the mirror-image reason: most deltas are
exactly zero, so the regression learns to predict zero and the informative rows
are drowned.

Both failures share a cause. The learnable signal is not in the level or in the
mean change; it is in the probability of a transition. So the headline targets
are events:

  drought   P(intensify by >= 1 category), P(>= 2), P(improve by >= 1),
            P(no change), P(category >= D2), P(category >= D3)
  fire      P(ERC percentile > 80), P(> 90), P(> 97)

Fire thresholds follow operational fire-danger practice: ERC percentile bands
against the local climatological distribution are how agencies set staffing and
restriction levels, and the 80th, 90th and 97th percentiles are the common
break points for elevated, high and extreme. The choice is documented rather
than tuned.

The Markov baseline
-------------------
For transition targets, persistence is a weak opponent and climatology is only
slightly better. The honest baseline is the empirical transition matrix: given
the current USDM category and the calendar month, how often did the category
move by that much over h weeks in the training years? That encodes the real
persistence-and-drift structure of drought, and it is hard to beat. If the
models do not beat it, that is the finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HORIZONS = (2, 4, 8)
N_CATEGORIES = 5  # USDM 0..4 after the None/D0 merge documented in DECISIONS.md

# Operational fire-danger percentile break points.
ERC_THRESHOLDS = (80, 90, 97)


# ----------------------------------------------------------------- targets


def drought_event_targets(frame: pd.DataFrame, horizon: int) -> dict[str, np.ndarray]:
    """Binary drought events at t+h, as 0/1 arrays aligned to `frame`.

    NaN where the future label is missing, so downstream masking is explicit
    rather than an accidental zero.
    """
    now = pd.to_numeric(frame.get("usdm"), errors="coerce").to_numpy(dtype=float)
    fut = pd.to_numeric(frame.get(f"usdm_h{horizon}"), errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(now) & np.isfinite(fut)
    delta = np.where(valid, fut - now, np.nan)

    def ev(mask: np.ndarray) -> np.ndarray:
        out = np.full(now.shape, np.nan, dtype="float32")
        out[valid] = mask[valid].astype("float32")
        return out

    return {
        f"d_intensify1_h{horizon}": ev(delta >= 1),
        f"d_intensify2_h{horizon}": ev(delta >= 2),
        f"d_improve1_h{horizon}": ev(delta <= -1),
        f"d_nochange_h{horizon}": ev(delta == 0),
        f"d_ge2_h{horizon}": ev(fut >= 2),
        f"d_ge3_h{horizon}": ev(fut >= 3),
    }


def fire_event_targets(frame: pd.DataFrame, horizon: int) -> dict[str, np.ndarray]:
    """Binary ERC-percentile exceedance events at t+h."""
    fut = pd.to_numeric(frame.get(f"erc_pct_h{horizon}"), errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(fut)
    out: dict[str, np.ndarray] = {}
    for thr in ERC_THRESHOLDS:
        a = np.full(fut.shape, np.nan, dtype="float32")
        a[valid] = (fut[valid] > thr).astype("float32")
        out[f"f_gt{thr}_h{horizon}"] = a
    return out


def all_event_targets(frame: pd.DataFrame, horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    """Attach every event target for every horizon."""
    out = frame.copy()
    for h in horizons:
        for k, v in drought_event_targets(frame, h).items():
            out[k] = v
        for k, v in fire_event_targets(frame, h).items():
            out[k] = v
    return out


def target_names(horizons: tuple[int, ...] = HORIZONS) -> list[str]:
    names: list[str] = []
    for h in horizons:
        names += [
            f"d_intensify1_h{h}",
            f"d_intensify2_h{h}",
            f"d_improve1_h{h}",
            f"d_nochange_h{h}",
            f"d_ge2_h{h}",
            f"d_ge3_h{h}",
        ]
        names += [f"f_gt{t}_h{h}" for t in ERC_THRESHOLDS]
    return names


# ---------------------------------------------------------------- baselines


@dataclass
class MarkovBaseline:
    """Empirical h-week USDM transition probabilities, by category and month.

    Rows are conditioned on (current category, month) and sum to 1. Estimated on
    training rows only. Where a (category, month) cell has too few observations
    to estimate, it falls back to the category-only row, and then to the global
    row, so a rare state never yields an undefined forecast.
    """

    horizon: int
    min_count: int = 30
    by_cat_month: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)
    by_cat: dict[int, np.ndarray] = field(default_factory=dict)
    global_row: np.ndarray = field(default_factory=lambda: np.full(N_CATEGORIES, 1.0 / N_CATEGORIES))

    def fit(self, frame: pd.DataFrame) -> MarkovBaseline:
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        fut = pd.to_numeric(frame[f"usdm_h{self.horizon}"], errors="coerce").to_numpy(dtype=float)
        month = pd.to_datetime(frame["time"]).dt.month.to_numpy()
        ok = np.isfinite(now) & np.isfinite(fut)
        ci = np.clip(np.round(now[ok]), 0, N_CATEGORIES - 1).astype(int)
        fi = np.clip(np.round(fut[ok]), 0, N_CATEGORIES - 1).astype(int)
        mi = month[ok]

        glob = np.bincount(fi, minlength=N_CATEGORIES).astype(float)
        self.global_row = glob / max(glob.sum(), 1.0)

        for c in range(N_CATEGORIES):
            m = ci == c
            if m.sum() >= self.min_count:
                cnt = np.bincount(fi[m], minlength=N_CATEGORIES).astype(float)
                self.by_cat[c] = cnt / cnt.sum()
            for mo in range(1, 13):
                mm = m & (mi == mo)
                if mm.sum() >= self.min_count:
                    cnt = np.bincount(fi[mm], minlength=N_CATEGORIES).astype(float)
                    self.by_cat_month[(c, mo)] = cnt / cnt.sum()
        return self

    def row(self, category: int, month: int) -> np.ndarray:
        c = int(np.clip(category, 0, N_CATEGORIES - 1))
        return self.by_cat_month.get((c, int(month)), self.by_cat.get(c, self.global_row))

    def predict_matrix(self, frame: pd.DataFrame) -> np.ndarray:
        """(n_rows, N_CATEGORIES) distribution over the category at t+h."""
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        month = pd.to_datetime(frame["time"]).dt.month.to_numpy()
        out = np.empty((len(frame), N_CATEGORIES), dtype="float32")
        for i in range(len(frame)):
            c = 0 if not np.isfinite(now[i]) else int(np.clip(round(now[i]), 0, N_CATEGORIES - 1))
            out[i] = self.row(c, int(month[i]))
        return out

    def predict_events(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        """Event probabilities implied by the transition distribution."""
        p = self.predict_matrix(frame)
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        cur = np.clip(np.nan_to_num(np.round(now)), 0, N_CATEGORIES - 1).astype(int)
        h = self.horizon
        cats = np.arange(N_CATEGORIES)[None, :]
        cur_col = cur[:, None]
        return {
            f"d_intensify1_h{h}": (p * (cats >= cur_col + 1)).sum(axis=1),
            f"d_intensify2_h{h}": (p * (cats >= cur_col + 2)).sum(axis=1),
            f"d_improve1_h{h}": (p * (cats <= cur_col - 1)).sum(axis=1),
            f"d_nochange_h{h}": (p * (cats == cur_col)).sum(axis=1),
            f"d_ge2_h{h}": p[:, 2:].sum(axis=1),
            f"d_ge3_h{h}": p[:, 3:].sum(axis=1),
        }


def climatology_event_baseline(
    train: pd.DataFrame, target: str, index: pd.DataFrame
) -> np.ndarray:
    """Per-cell week-of-year base rate for an event, fit on training rows."""
    tr = train[["cell_id", "time", target]].copy()
    tr["woy"] = pd.to_datetime(tr["time"]).dt.isocalendar().week.astype(int)
    rate = tr.groupby(["cell_id", "woy"])[target].mean()
    overall = float(pd.to_numeric(tr[target], errors="coerce").mean())

    idx = index[["cell_id", "time"]].copy()
    idx["woy"] = pd.to_datetime(idx["time"]).dt.isocalendar().week.astype(int)
    joined = idx.join(rate, on=["cell_id", "woy"])
    vals: np.ndarray = pd.to_numeric(joined[target], errors="coerce").fillna(overall).to_numpy(dtype="float32")
    return vals


def persistence_event_baseline(frame: pd.DataFrame, target: str) -> np.ndarray:
    """Current state as a 0/1 forecast for exceedance targets.

    For transition targets persistence means "nothing changes", which is a
    probability of 0 for intensify/improve and 1 for no-change. Stated that way
    it is obviously a weak forecast, which is exactly why the Markov baseline
    exists.
    """
    n = len(frame)
    if target.startswith("d_nochange"):
        return np.ones(n, dtype="float32")
    if target.startswith("d_intensify") or target.startswith("d_improve"):
        return np.zeros(n, dtype="float32")
    if target.startswith("d_ge"):
        k = int(target.split("_ge")[1].split("_")[0])
        now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
        ge: np.ndarray = (np.nan_to_num(now) >= k).astype("float32")
        return ge
    if target.startswith("f_gt"):
        thr = int(target.split("_gt")[1].split("_")[0])
        now = pd.to_numeric(frame.get("erc_pct"), errors="coerce").to_numpy(dtype=float)
        gt: np.ndarray = (np.nan_to_num(now) > thr).astype("float32")
        return gt
    return np.full(n, 0.5, dtype="float32")
