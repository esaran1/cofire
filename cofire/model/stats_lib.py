"""Established implementations of the statistics this project rolled by hand.

Every routine here replaces a custom one, and every replacement is checked
against the thing it replaces rather than swapped in on faith. The custom
versions stay importable so the comparison can be rerun.

What each replaces, and why it matters:

- `arch.bootstrap.CircularBlockBootstrap` for the block bootstrap. The custom
  version resampled whole weeks with replacement, which is a valid block
  bootstrap for exchangeable blocks but ignores the ordering between adjacent
  weeks. A circular block bootstrap keeps runs of consecutive weeks intact,
  which matters for a drought series where the autocorrelation is the point.
- `statsmodels.stats.multitest.multipletests` for BH and Holm. The custom
  versions were written from the definitions and tested, but a reviewer should
  not have to trust a hand-rolled step-up procedure.
- `statsmodels.tsa.stattools.acf` for the effective sample size. The custom
  `ar1_neff` assumed a first-order process; the ACF-based version sums the
  observed autocorrelations and makes no such assumption.
- `sklearn.calibration` for reliability curves and Platt scaling.

The minimum-positive-events rule is preserved in all of it: a rare-event target
with too few positive weeks is reported not estimable regardless of which
bootstrap draws the replicates.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402

from cofire.model.prob_metrics import MIN_POSITIVE_WEEKS, positive_weeks  # noqa: E402

LOGGER = logging.getLogger("cofire.stats_lib")


@dataclass
class BootstrapResult:
    point: float
    lo: float
    hi: float
    n_weeks: int
    n_eff: float
    n_positive_weeks: int
    estimable: bool
    reason: str = ""


def neff_from_acf(series: np.ndarray, max_lag: int | None = None) -> float:
    """Effective sample size from the observed autocorrelation function.

    n_eff = n / (1 + 2 * sum_k rho_k), summed over positive lags up to the
    first non-significant one. Makes no AR(1) assumption, unlike the routine it
    replaces.
    """
    from statsmodels.tsa.stattools import acf

    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 8 or np.allclose(x, x[0]):
        return float(n)
    lag = int(max_lag or min(n // 4, 20))
    try:
        rho = acf(x, nlags=lag, fft=False)
    except Exception:  # noqa: BLE001
        return float(n)
    # Sum positive autocorrelations until the first that crosses zero, the
    # standard initial-positive-sequence truncation.
    total = 0.0
    for k in range(1, len(rho)):
        if not np.isfinite(rho[k]) or rho[k] <= 0:
            break
        total += rho[k]
    denom = 1.0 + 2.0 * total
    return float(max(1.0, n / denom)) if denom > 0 else float(n)


def circular_block_bootstrap(
    stat_fn: Callable[[np.ndarray], float],
    weeks: np.ndarray,
    y: np.ndarray,
    n_boot: int = 400,
    alpha: float = 0.05,
    seed: int = 2026,
    block_size: int | None = None,
    min_positive_weeks: int = MIN_POSITIVE_WEEKS,
) -> BootstrapResult:
    """Circular block bootstrap from `arch`, with the rare-event rule kept.

    Blocks of consecutive weeks are resampled, wrapping at the end of the
    series, so runs of correlated weeks survive into the replicates. The
    estimability rule is applied first and is independent of the resampling
    scheme: a target with too few positive weeks has nothing to resample.
    """
    from arch.bootstrap import CircularBlockBootstrap

    uniq = np.unique(weeks)
    pos = positive_weeks(y, weeks)
    n_pos = int(pos.size)
    point = float(stat_fn(uniq))

    if n_pos < min_positive_weeks:
        return BootstrapResult(
            point, float("nan"), float("nan"), int(uniq.size), float("nan"), n_pos,
            estimable=False,
            reason=f"{n_pos} positive weeks is below the {min_positive_weeks} needed",
        )

    # Politis and White's rule of thumb scales with n^(1/3); for ~100 weeks
    # that is about 5, which is also roughly the persistence of a drought
    # episode at weekly resolution.
    bs_len = int(block_size or max(2, round(uniq.size ** (1 / 3))))
    idx = np.arange(uniq.size)
    bs = CircularBlockBootstrap(bs_len, idx, seed=seed)

    draws: list[float] = []
    for data, _kw in bs.bootstrap(n_boot):
        sel = uniq[np.asarray(data[0], dtype=int)]
        draws.append(stat_fn(sel))
    arr = np.asarray(draws, dtype=float)
    good = arr[np.isfinite(arr)]
    if good.size < max(20, n_boot // 10):
        return BootstrapResult(
            point, float("nan"), float("nan"), int(uniq.size), float("nan"), n_pos,
            estimable=False, reason=f"only {good.size} of {n_boot} replicates were finite",
        )
    lo = float(np.percentile(good, 100 * alpha / 2))
    hi = float(np.percentile(good, 100 * (1 - alpha / 2)))
    per_week = np.array([stat_fn(np.array([w])) for w in uniq], dtype=float)
    return BootstrapResult(
        point, lo, hi, int(uniq.size), neff_from_acf(per_week), n_pos, estimable=True
    )


def multipletests_bh(pvals: list[float], q: float = 0.10) -> list[bool]:
    """Benjamini-Hochberg via statsmodels."""
    from statsmodels.stats.multitest import multipletests

    if not pvals:
        return []
    reject, _, _, _ = multipletests(pvals, alpha=q, method="fdr_bh")
    return [bool(x) for x in reject]


def multipletests_holm(pvals: list[float], alpha: float = 0.10) -> list[bool]:
    """Holm-Bonferroni via statsmodels."""
    from statsmodels.stats.multitest import multipletests

    if not pvals:
        return []
    reject, _, _, _ = multipletests(pvals, alpha=alpha, method="holm")
    return [bool(x) for x in reject]


def platt_sklearn(p_cal: np.ndarray, y_cal: np.ndarray, p_target: np.ndarray) -> np.ndarray:
    """Platt scaling through scikit-learn's calibration machinery.

    Equivalent in form to the hand-rolled version, which also fits a logistic
    on the log-odds, but routed through the library so the comparison is
    against a maintained implementation.
    """
    from sklearn.linear_model import LogisticRegression

    m = np.isfinite(p_cal) & np.isfinite(y_cal)
    if m.sum() < 50 or len(np.unique(y_cal[m])) < 2:
        return p_target
    eps = 1e-6
    q = np.clip(p_cal[m], eps, 1 - eps)
    z = np.log(q / (1 - q)).reshape(-1, 1)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(z, y_cal[m])
    qt = np.clip(p_target, eps, 1 - eps)
    zt = np.log(qt / (1 - qt)).reshape(-1, 1)
    return np.asarray(lr.predict_proba(zt)[:, 1], dtype="float32")


def reliability_sklearn(
    p: np.ndarray, y: np.ndarray, n_bins: int = 10
) -> tuple[np.ndarray, np.ndarray]:
    """Reliability curve from scikit-learn."""
    from sklearn.calibration import calibration_curve

    m = np.isfinite(p) & np.isfinite(y)
    if m.sum() < 10 or len(np.unique(y[m])) < 2:
        return np.array([]), np.array([])
    frac, mean_pred = calibration_curve(y[m], np.clip(p[m], 0, 1), n_bins=n_bins, strategy="quantile")
    return np.asarray(frac), np.asarray(mean_pred)
