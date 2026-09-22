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


def shuffle_within_blocks(
    y: np.ndarray,
    weeks: np.ndarray,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Permute `y` within contiguous blocks of weeks, preserving block totals.

    The control a skill claim is tested against. Shuffling within the same
    circular blocks used by the bootstrap keeps the marginal rate, the block
    structure and the seasonal envelope, and destroys only the row-level
    association between prediction and outcome. A shuffle across the whole
    series would also destroy the seasonality, which would make the control
    easier to beat than it should be.
    """
    out = np.asarray(y, dtype=float).copy()
    uniq = np.unique(weeks)
    for start in range(0, uniq.size, block_size):
        blk = uniq[start : start + block_size]
        sel = np.isin(weeks, blk)
        idx = np.flatnonzero(sel)
        if idx.size > 1:
            out[idx] = out[rng.permutation(idx)]
    return out


def paired_real_minus_shuffled(
    stat_fn: Callable[[np.ndarray, np.ndarray], float],
    weeks: np.ndarray,
    y: np.ndarray,
    n_boot: int = 400,
    alpha: float = 0.05,
    seed: int = 2026,
    block_size: int | None = None,
    n_shuffles: int = 20,
    min_positive_weeks: int = MIN_POSITIVE_WEEKS,
) -> BootstrapResult:
    """The skill test: is the statistic higher on real targets than shuffled?

    Two models that are both functions of the same input can differ in Brier on
    shuffled labels through probability spread alone, so a skill statistic
    computed on real targets says nothing by itself. What says something is the
    paired difference: the same rows, the same blocks, the same resampling, the
    statistic on the real target minus the statistic on a target shuffled
    within those blocks. A claim requires that difference's CI above zero.

    `stat_fn(selected_weeks, y)` must take the target explicitly, so the real
    and shuffled arms run through one code path rather than two.

    The shuffled arm averages `n_shuffles` permutations so that the control is
    the expected value under the null rather than one draw of it, and the same
    permutations are reused across bootstrap replicates so that the pairing is
    on the rows, not on the noise in the shuffle.
    """
    from arch.bootstrap import CircularBlockBootstrap

    uniq = np.unique(weeks)
    pos = positive_weeks(y, weeks)
    n_pos = int(pos.size)
    bs_len = int(block_size or max(2, round(uniq.size ** (1 / 3))))

    if n_pos < min_positive_weeks:
        return BootstrapResult(
            float("nan"), float("nan"), float("nan"), int(uniq.size), float("nan"),
            n_pos, estimable=False,
            reason=f"{n_pos} positive weeks is below the {min_positive_weeks} needed",
        )

    rng = np.random.default_rng(seed)
    shuffles = [shuffle_within_blocks(y, weeks, bs_len, rng) for _ in range(n_shuffles)]

    def diff(sel: np.ndarray) -> float:
        real = stat_fn(sel, y)
        if not np.isfinite(real):
            return float("nan")
        ctrl = [stat_fn(sel, ys) for ys in shuffles]
        ctrl_arr = np.asarray(ctrl, dtype=float)
        ctrl_arr = ctrl_arr[np.isfinite(ctrl_arr)]
        if ctrl_arr.size == 0:
            return float("nan")
        return float(real - ctrl_arr.mean())

    point = diff(uniq)
    idx = np.arange(uniq.size)
    bs = CircularBlockBootstrap(bs_len, idx, seed=seed)
    draws = [diff(uniq[np.asarray(d[0], dtype=int)]) for d, _kw in bs.bootstrap(n_boot)]
    arr = np.asarray(draws, dtype=float)
    good = arr[np.isfinite(arr)]
    if good.size < max(20, n_boot // 10):
        return BootstrapResult(
            point, float("nan"), float("nan"), int(uniq.size), float("nan"), n_pos,
            estimable=False, reason=f"only {good.size} of {n_boot} replicates were finite",
        )
    lo = float(np.percentile(good, 100 * alpha / 2))
    hi = float(np.percentile(good, 100 * (1 - alpha / 2)))
    return BootstrapResult(
        point, lo, hi, int(uniq.size), neff_from_acf(good), n_pos, estimable=True
    )


def bootstrap_pvalue(res: BootstrapResult, n_boot: int = 400) -> float:
    """A two-sided p-value from a bootstrap CI, for feeding BH and Holm.

    Inverts the percentile interval: the p-value is the smallest alpha at which
    the interval excludes zero, approximated from the normal quantile implied
    by the point estimate and the interval half-width. Crude, and stated as
    such, but the multiplicity procedures need p-values and the alternative is
    running the bootstrap at every alpha.
    """
    from scipy import stats as _st

    if not res.estimable or not np.isfinite(res.lo) or not np.isfinite(res.hi):
        return float("nan")
    se = (res.hi - res.lo) / (2 * 1.959963984540054)
    if not np.isfinite(se) or se <= 0:
        return 0.0 if res.lo > 0 else 1.0
    z = res.point / se
    return float(2.0 * _st.norm.sf(abs(z)))


def brier_week_sums(
    p: np.ndarray, y: np.ndarray, weeks: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-week squared-error sums and counts, for a fast exact Brier.

    A Brier score is a mean of squared errors, so the score over any selection
    of weeks is the sum of those weeks' error sums divided by the sum of their
    counts. Precomputing per week turns each bootstrap replicate from a scan of
    every row into a gather over a few hundred weeks.

    This also fixes a defect in the obvious implementation. Selecting rows with
    `np.isin(weeks, sel)` is a set membership test, so a week drawn twice in a
    bootstrap replicate contributes once rather than twice, which quietly
    reweights every replicate. Indexing by position, as the callers of this
    function do, preserves multiplicity.
    """
    m = np.isfinite(p) & np.isfinite(y)
    uniq, inv = np.unique(weeks[m], return_inverse=True)
    err = (np.clip(p[m], 0.0, 1.0) - y[m]) ** 2
    sums = np.bincount(inv, weights=err, minlength=uniq.size)
    counts = np.bincount(inv, minlength=uniq.size).astype(float)
    return uniq, sums, counts


def bss_from_sums(
    idx: np.ndarray,
    model_sums: np.ndarray,
    ref_sums: np.ndarray,
    counts: np.ndarray,
) -> float:
    """Brier skill score over the weeks at positions `idx`, with multiplicity."""
    n = counts[idx].sum()
    if n <= 0:
        return float("nan")
    ref = ref_sums[idx].sum() / n
    if ref <= 1e-12:
        return float("nan")
    return float(1.0 - (model_sums[idx].sum() / n) / ref)


def paired_bss_shuffled(
    pred: np.ndarray,
    ref: np.ndarray,
    y: np.ndarray,
    weeks: np.ndarray,
    n_boot: int = 400,
    alpha: float = 0.05,
    seed: int = 2026,
    block_size: int | None = None,
    n_shuffles: int = 20,
    min_positive_weeks: int = MIN_POSITIVE_WEEKS,
) -> BootstrapResult:
    """`paired_real_minus_shuffled` specialised to a Brier skill score.

    Same statistic and same rule as the general version, precomputed per week
    so a full run finishes inside a stage. `tests/test_paired_shuffle.py`
    checks the two agree on the same inputs.
    """
    from arch.bootstrap import CircularBlockBootstrap

    m = np.isfinite(pred) & np.isfinite(ref) & np.isfinite(y)
    pred, ref, y, weeks = pred[m], ref[m], y[m], weeks[m]

    uniq = np.unique(weeks)
    pos = positive_weeks(y, weeks)
    n_pos = int(pos.size)
    bs_len = int(block_size or max(2, round(uniq.size ** (1 / 3))))

    if n_pos < min_positive_weeks:
        return BootstrapResult(
            float("nan"), float("nan"), float("nan"), int(uniq.size), float("nan"),
            n_pos, estimable=False,
            reason=f"{n_pos} positive weeks is below the {min_positive_weeks} needed",
        )

    rng = np.random.default_rng(seed)
    targets = [y] + [
        shuffle_within_blocks(y, weeks, bs_len, rng) for _ in range(n_shuffles)
    ]
    # One (model, reference) pair of per-week sums per target, real first.
    packed = []
    for yy in targets:
        u, ms, cs = brier_week_sums(pred, yy, weeks)
        _u, rs, _cs = brier_week_sums(ref, yy, weeks)
        packed.append((ms, rs, cs))
    counts = packed[0][2]

    def diff(idx: np.ndarray) -> float:
        real = bss_from_sums(idx, packed[0][0], packed[0][1], counts)
        if not np.isfinite(real):
            return float("nan")
        ctrl = np.asarray(
            [bss_from_sums(idx, ms, rs, cs) for ms, rs, cs in packed[1:]], dtype=float
        )
        ctrl = ctrl[np.isfinite(ctrl)]
        return float(real - ctrl.mean()) if ctrl.size else float("nan")

    all_idx = np.arange(uniq.size)
    point = diff(all_idx)
    bs = CircularBlockBootstrap(bs_len, all_idx, seed=seed)
    draws = [diff(np.asarray(d[0], dtype=int)) for d, _kw in bs.bootstrap(n_boot)]
    arr = np.asarray(draws, dtype=float)
    good = arr[np.isfinite(arr)]
    if good.size < max(20, n_boot // 10):
        return BootstrapResult(
            point, float("nan"), float("nan"), int(uniq.size), float("nan"), n_pos,
            estimable=False, reason=f"only {good.size} of {n_boot} replicates were finite",
        )
    return BootstrapResult(
        point,
        float(np.percentile(good, 100 * alpha / 2)),
        float(np.percentile(good, 100 * (1 - alpha / 2))),
        int(uniq.size), neff_from_acf(good), n_pos, estimable=True,
    )
