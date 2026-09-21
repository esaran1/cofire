"""Consolidated evaluation: three baselines, a rare-event bootstrap, multiplicity.

Everything the exploratory passes established is re-measured here under the
corrections the review demanded, because each of them changes what the numbers
mean:

- **Seasonal climatology is the primary reference.** The earlier two-stage table
  scored against a flat training constant, which credits a model for knowing the
  calendar.
- **Every target is also scored against persistence and the Markov baseline.**
  A level target like `d_ge2` at two weeks is mostly a persistence question, and
  a model that clears climatology but not persistence has no forecast skill
  there.
- **One fixed stage-1 specification**, all five slow predictors plus season,
  ridge-penalised with a single penalty chosen on pooled validation. Per-target
  selection was choosing among noise.
- **A stratified block bootstrap**, which refuses to report an interval for a
  target with too few positive weeks to resample.
- **Benjamini-Hochberg at q=0.10 across targets and domains**, with horizon
  variants of one event treated as a family and Holm applied within it.

Nothing here touches 2026.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.ablation import _splits, feature_columns  # noqa: E402
from cofire.model.base_rate import (  # noqa: E402
    FIXED_SPEC,
    add_slow_predictors,
    domain_weeks,
    fit_deviation_weight,
    fit_ridge,
    offset_logit_for_rows,
    select_penalty,
    two_stage_probability,
)
from cofire.model.config import Settings  # noqa: E402
from cofire.model.prob_metrics import (  # noqa: E402
    brier,
    stratified_block_bootstrap,
)
from cofire.model.prob_models import (  # noqa: E402
    fit_lightgbm_classifier,
    out_of_fold_frame,
)
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    MarkovBaseline,
    all_event_targets,
    constant_event_baseline,
    persistence_event_baseline,
    seasonal_climatology_baseline,
    target_names,
)

LOGGER = logging.getLogger("cofire.confirm")

OUT_DIR = Path("artifacts/ablation")
FOLD_YEARS = (2020, 2021, 2024, 2025)
DOMAINS = ("larimer", "pueblo")


def event_family(target: str) -> str:
    """Horizon variants of one event are one family for multiplicity control."""
    return target.rsplit("_h", 1)[0]


def _bss(p: np.ndarray, y: np.ndarray, ref: np.ndarray) -> float:
    b_ref = brier(ref, y)
    return float("nan") if b_ref <= 1e-12 else 1.0 - brier(p, y) / b_ref


def evaluate(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    cols: list[str],
    target: str,
    horizon: int,
    domain: str,
    penalty: float,
    n_boot: int = 400,
) -> dict[str, object] | None:
    y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
        return None

    dw_train, dw_valid = domain_weeks(train, target), domain_weeks(valid, target)
    if dw_train.empty or dw_valid.empty:
        return None

    # Stage 1 on the fixed specification, then the cell model on top.
    s1 = fit_ridge(dw_train, FIXED_SPEC, penalty)
    z1 = offset_logit_for_rows(valid, s1, dw_valid)
    raw = fit_lightgbm_classifier(train, valid, cols, target)
    p_oof, y_oof, rows_oof = out_of_fold_frame(
        train, cols, target, FOLD_YEARS, fit_lightgbm_classifier
    )
    if p_oof.size:
        z_oof = offset_logit_for_rows(rows_oof, s1, domain_weeks(rows_oof, target))
        weight = fit_deviation_weight(z_oof, p_oof, y_oof)
    else:
        weight = 0.0
    p = two_stage_probability(z1, raw, weight=weight)

    refs = {
        "seasonal": seasonal_climatology_baseline(train, target, valid),
        "persistence": persistence_event_baseline(valid, target),
        "markov": MarkovBaseline(horizon=horizon).fit(train).predict_events(valid).get(
            target, np.full(len(valid), np.nan)
        ),
        "constant": constant_event_baseline(train, target, valid),
    }

    weeks = pd.to_datetime(valid["time"]).to_numpy()

    def stat(sel: np.ndarray, ref: np.ndarray = refs["seasonal"]) -> float:
        m = np.isin(weeks, sel)
        return float("nan") if not m.any() else _bss(p[m], y[m], ref[m])

    res = stratified_block_bootstrap(stat, weeks, y, n_boot=n_boot)

    out: dict[str, object] = {
        "domain": domain,
        "target": target,
        "family": event_family(target),
        "horizon": horizon,
        "n": int(np.isfinite(y).sum()),
        "valid_rate": round(float(np.nanmean(y)), 5),
        "deviation_weight": round(weight, 4),
        "brier_model": round(brier(p, y), 5),
        "n_weeks": res.n_weeks,
        "n_positive_weeks": res.n_positive_weeks,
        "n_eff_weeks": round(res.n_eff, 1) if np.isfinite(res.n_eff) else float("nan"),
        "estimable": res.estimable,
        "not_estimable_reason": res.reason,
        # Primary reference first.
        "bss_vs_seasonal": round(res.point, 5),
        "bss_lo": round(res.lo, 5) if np.isfinite(res.lo) else float("nan"),
        "bss_hi": round(res.hi, 5) if np.isfinite(res.hi) else float("nan"),
    }
    for name, ref in refs.items():
        out[f"brier_{name}"] = round(brier(ref, y), 5)
        if name != "seasonal":
            out[f"bss_vs_{name}"] = round(_bss(p, y, ref), 5)
    return out


def benjamini_hochberg(pvals: list[float], q: float = 0.10) -> list[bool]:
    """Step-up procedure. Returns which hypotheses are rejected."""
    n = len(pvals)
    if n == 0:
        return []
    order = np.argsort(pvals)
    keep = np.zeros(n, dtype=bool)
    thresh = -1
    for rank, idx in enumerate(order, start=1):
        if pvals[idx] <= q * rank / n:
            thresh = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= thresh:
            keep[idx] = True
    return keep.tolist()


def holm(pvals: list[float], alpha: float = 0.10) -> list[bool]:
    """Step-down procedure, used within a family of horizon variants."""
    n = len(pvals)
    if n == 0:
        return []
    order = np.argsort(pvals)
    keep = np.zeros(n, dtype=bool)
    for rank, idx in enumerate(order, start=1):
        if pvals[idx] <= alpha / (n - rank + 1):
            keep[idx] = True
        else:
            break
    return keep.tolist()


def bootstrap_pvalue(lo: float, hi: float, point: float) -> float:
    """A two-sided p-value implied by a percentile interval.

    Approximate by construction: the interval is a 95% percentile interval, so
    this inverts it rather than recomputing the null. Good enough to rank
    hypotheses for a multiplicity procedure, and the intervals themselves are
    reported alongside so a reader is not relying on it alone.
    """
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return 1.0
    se = (hi - lo) / (2 * 1.96)
    if se <= 0:
        return 0.0 if point > 0 else 1.0
    from math import erfc, sqrt

    return float(erfc(abs(point) / (se * sqrt(2))))


def run(n_boot: int = 400) -> Path:
    from cofire.model.features import load_features

    # One penalty for every target and both domains, chosen on pooled LODO.
    pooled_dw: list[pd.DataFrame] = []
    per_domain: dict[str, tuple[pd.DataFrame, pd.DataFrame, list[str]]] = {}
    for dom in DOMAINS:
        os.environ["COFIRE_SUBSET_NAME"] = dom
        st = Settings()
        frame = load_features(st.processed_dir / "features_v1")
        if frame.empty:
            continue
        frame = add_slow_predictors(all_event_targets(frame, HORIZONS))
        cols = feature_columns(frame)
        v1 = [c for c in cols if c.startswith(("esi_", "rci_"))]
        if v1:
            frame = frame[frame[v1].notna().all(axis=1)]
        train, _cal, valid = _splits(frame, st, 0.25)
        if train.empty or valid.empty:
            continue
        per_domain[dom] = (train, valid, cols)
        for h in HORIZONS:
            for t in target_names((h,)):
                if t in frame.columns:
                    dw = domain_weeks(train, t)
                    if not dw.empty:
                        pooled_dw.append(dw)

    if not per_domain:
        raise SystemExit("no domains available")
    penalty = select_penalty(pooled_dw, FOLD_YEARS)

    rows: list[dict[str, object]] = []
    for dom, (train, valid, cols) in per_domain.items():
        for h in HORIZONS:
            for t in target_names((h,)):
                if t not in valid.columns:
                    continue
                rec = evaluate(train, valid, cols, t, h, dom, penalty, n_boot)
                if rec is None:
                    continue
                rows.append(rec)
                LOGGER.info(
                    "%s %-22s h=%d bss_seasonal=%+.4f pers=%+.4f markov=%+.4f pos_weeks=%d %s",
                    dom, t, h, rec["bss_vs_seasonal"], rec["bss_vs_persistence"],
                    rec["bss_vs_markov"], rec["n_positive_weeks"],
                    "" if rec["estimable"] else "NOT ESTIMABLE",
                )

    df = pd.DataFrame(rows)
    df["penalty"] = penalty

    # Multiplicity. Only estimable rows enter, since a row without an interval
    # has no p-value to control.
    df["p_value"] = [
        bootstrap_pvalue(r.bss_lo, r.bss_hi, r.bss_vs_seasonal) if r.estimable else float("nan")
        for r in df.itertuples()
    ]
    df["holm_within_family"] = False
    for _key, g in df[df.estimable].groupby(["domain", "family"]):
        flags = holm(g["p_value"].tolist(), alpha=0.10)
        df.loc[g.index, "holm_within_family"] = flags

    fam = df[df.estimable & df.holm_within_family]
    df["bh_survives"] = False
    if not fam.empty:
        df.loc[fam.index, "bh_survives"] = benjamini_hochberg(fam["p_value"].tolist(), q=0.10)
    # A negative skill score is not a discovery, whatever its p-value.
    df.loc[df["bss_vs_seasonal"] <= 0, ["holm_within_family", "bh_survives"]] = False

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "confirm.csv"
    df.to_csv(out, index=False)
    LOGGER.info(
        "wrote %s: %d rows, %d estimable, %d survive BH",
        out, len(df), int(df.estimable.sum()), int(df.bh_survives.sum()),
    )
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
