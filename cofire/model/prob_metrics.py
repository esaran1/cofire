"""Metrics for probabilistic forecasts. INTENDED FOR HAND-REWRITE.

Everything here respects two constraints that the earlier regression metrics
did not:

1. Skill is reported against a *named* baseline, not against zero. A Brier
   score alone says nothing; a Brier skill score against the Markov baseline
   says whether the model adds anything over knowing the transition statistics.

2. Confidence intervals resample *weeks*, not rows. Cell-weeks are strongly
   autocorrelated in both space and time, so a row bootstrap reports intervals
   several times too narrow. Block resampling by week is the minimum honest
   correction, and the effective sample size is reported alongside so the reader
   can see how few independent observations there really are.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd


def _clean(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = np.isfinite(p) & np.isfinite(y)
    return np.clip(p[m], 0.0, 1.0), y[m]


def brier(p: np.ndarray, y: np.ndarray) -> float:
    p, y = _clean(p, y)
    return float(np.mean((p - y) ** 2)) if p.size else float("nan")


def brier_skill(p: np.ndarray, y: np.ndarray, ref: np.ndarray) -> float:
    """1 - BS(model)/BS(reference). Positive means better than the reference."""
    m = np.isfinite(p) & np.isfinite(y) & np.isfinite(ref)
    if not m.any():
        return float("nan")
    bs = float(np.mean((np.clip(p[m], 0, 1) - y[m]) ** 2))
    bs_ref = float(np.mean((np.clip(ref[m], 0, 1) - y[m]) ** 2))
    if bs_ref <= 1e-12:
        return float("nan")
    return 1.0 - bs / bs_ref


def brier_decomposition(p: np.ndarray, y: np.ndarray, bins: int = 10) -> dict[str, float]:
    """Murphy decomposition: reliability, resolution, uncertainty.

    BS = reliability - resolution + uncertainty. Reliability near zero means the
    stated probabilities match observed frequencies; resolution is how much the
    forecast separates events from non-events.
    """
    p, y = _clean(p, y)
    if p.size == 0:
        return {"reliability": float("nan"), "resolution": float("nan"), "uncertainty": float("nan")}
    obar = float(np.mean(y))
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    rel = res = 0.0
    n = p.size
    for b in range(bins):
        m = idx == b
        nk = int(m.sum())
        if nk == 0:
            continue
        pk = float(np.mean(p[m]))
        ok = float(np.mean(y[m]))
        rel += nk * (pk - ok) ** 2
        res += nk * (ok - obar) ** 2
    return {
        "reliability": rel / n,
        "resolution": res / n,
        "uncertainty": obar * (1 - obar),
    }


def reliability_curve(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Points for a reliability diagram: mean forecast vs observed frequency."""
    p, y = _clean(p, y)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    out: list[dict[str, float]] = []
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        out.append(
            {
                "bin": b,
                "mean_forecast": float(np.mean(p[m])),
                "observed_freq": float(np.mean(y[m])),
                "n": int(m.sum()),
            }
        )
    return out


def roc_auc(p: np.ndarray, y: np.ndarray) -> float:
    """Rank-based AUC. No sklearn dependency, ties handled by average rank."""
    p, y = _clean(p, y)
    pos, neg = y == 1, y == 0
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(p.size, dtype=float)
    ranks[order] = np.arange(1, p.size + 1)
    # Average ranks within ties so a constant forecast scores exactly 0.5.
    s = pd.Series(p)
    ranks = s.rank(method="average").to_numpy()
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def pr_auc(p: np.ndarray, y: np.ndarray) -> float:
    """Average precision. The honest headline for rare events, where ROC-AUC
    flatters a model that never has to commit."""
    p, y = _clean(p, y)
    if p.size == 0 or y.sum() == 0:
        return float("nan")
    order = np.argsort(-p, kind="mergesort")
    ys = y[order]
    tp = np.cumsum(ys)
    precision = tp / np.arange(1, ys.size + 1)
    return float(np.sum(precision * ys) / ys.sum())


def macro_f1_ge2(p: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> float:
    """Macro F1 at a stated threshold, for comparison with published USDM work."""
    p, y = _clean(p, y)
    if p.size == 0:
        return float("nan")
    yhat = (p >= threshold).astype(int)
    f1s = []
    for cls in (0, 1):
        tp = float(np.sum((yhat == cls) & (y == cls)))
        fp = float(np.sum((yhat == cls) & (y != cls)))
        fn = float(np.sum((yhat != cls) & (y == cls)))
        denom = 2 * tp + fp + fn
        f1s.append(0.0 if denom == 0 else 2 * tp / denom)
    return float(np.mean(f1s))


# --------------------------------------------------- autocorrelation-aware CI


def ar1_neff(series: np.ndarray) -> float:
    """Effective sample size under AR(1), n * (1-rho)/(1+rho)."""
    x = series[np.isfinite(series)]
    n = x.size
    if n < 3:
        return float(n)
    xc = x - x.mean()
    denom = float(np.sum(xc**2))
    if denom <= 0:
        return float(n)
    rho = float(np.sum(xc[:-1] * xc[1:]) / denom)
    rho = float(np.clip(rho, -0.999, 0.999))
    return float(max(1.0, n * (1 - rho) / (1 + rho)))


@dataclass
class BlockBootstrapResult:
    point: float
    lo: float
    hi: float
    n_weeks: int
    n_eff: float


def block_bootstrap(
    stat_fn: Callable[[np.ndarray], float],
    weeks: np.ndarray,
    n_boot: int = 500,
    alpha: float = 0.05,
    seed: int = 2026,
) -> BlockBootstrapResult:
    """Resample whole weeks, not rows.

    `stat_fn` takes an array of selected week labels and returns a scalar. Weeks
    are the block unit because a cell-week is correlated with its neighbours in
    both space and time; resampling rows would treat 100k correlated
    observations as 100k independent ones and report intervals far too narrow.
    """
    uniq = np.array(sorted(set(weeks.tolist())))
    rng = np.random.default_rng(seed)
    point = float(stat_fn(uniq))
    if uniq.size < 3:
        return BlockBootstrapResult(point, float("nan"), float("nan"), int(uniq.size), float(uniq.size))
    draws = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        draws[b] = stat_fn(pick)
    good = draws[np.isfinite(draws)]
    lo, hi = (
        (float(np.percentile(good, 100 * alpha / 2)), float(np.percentile(good, 100 * (1 - alpha / 2))))
        if good.size
        else (float("nan"), float("nan"))
    )
    return BlockBootstrapResult(point, lo, hi, int(uniq.size), ar1_neff(uniq.astype(float)))


def evaluate_probabilistic(
    p: np.ndarray,
    y: np.ndarray,
    weeks: np.ndarray,
    baselines: dict[str, np.ndarray],
    n_boot: int = 300,
) -> dict[str, object]:
    """Full report for one target: scores, skill against each baseline, CIs."""
    out: dict[str, object] = {
        "n": int(np.sum(np.isfinite(p) & np.isfinite(y))),
        "base_rate": float(np.nanmean(y)) if np.isfinite(y).any() else float("nan"),
        "brier": brier(p, y),
        "roc_auc": roc_auc(p, y),
        "pr_auc": pr_auc(p, y),
        "macro_f1": macro_f1_ge2(p, y),
        **{f"decomp_{k}": v for k, v in brier_decomposition(p, y).items()},
    }
    wk = pd.to_datetime(weeks).to_numpy()
    for name, ref in baselines.items():
        out[f"bss_vs_{name}"] = brier_skill(p, y, ref)

        def stat(sel: np.ndarray, _ref: np.ndarray = ref) -> float:
            m = np.isin(wk, sel)
            return brier_skill(p[m], y[m], _ref[m])

        res = block_bootstrap(stat, wk, n_boot=n_boot)
        out[f"bss_vs_{name}_lo"] = res.lo
        out[f"bss_vs_{name}_hi"] = res.hi
        out["n_weeks"] = res.n_weeks
        out["n_eff_weeks"] = round(res.n_eff, 1)
    return out
