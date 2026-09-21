"""Stage 1 plus stage 2, and how much of the base-rate cost stage 1 recovers.

The oracle decomposition prices two things per target: what not knowing the
evaluation-period event rate costs, and what the cell model's ranking is worth.
Where the base-rate term dominates, no amount of cell-level feature work helps,
and the only way forward is to predict the level.

This measures whether that works. The number that matters is the fraction of the
base-rate cost that stage 1 recovers:

    recovery = (Brier(stage 2) - Brier(oracle model)) relative to
               (Brier(constant) - Brier(oracle constant))

expressed as the share of the gap closed. A recovery near 1 means the slow
climate state carries the level. A recovery near 0 means it does not, and the
17x year-to-year swing is simply not predictable from what we have.
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
    BaseRateModel,
    add_slow_predictors,
    domain_weeks,
    fit_deviation_weight,
    offset_logit_for_rows,
    select_predictors,
    two_stage_probability,
)
from cofire.model.config import Settings  # noqa: E402
from cofire.model.oracle_decomp import oracle_calibrate  # noqa: E402
from cofire.model.prob_metrics import block_bootstrap, brier, brier_decomposition  # noqa: E402
from cofire.model.prob_models import (  # noqa: E402
    fit_lightgbm_classifier,
    out_of_fold_frame,
    platt_recalibrate,
)
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    all_event_targets,
    constant_event_baseline,
    seasonal_climatology_baseline,
    target_names,
)

LOGGER = logging.getLogger("cofire.two_stage")

OUT_DIR = Path("artifacts/ablation")
FOLD_YEARS = (2020, 2021, 2024, 2025)


def evaluate_target(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    horizon: int,
    domain: str,
    n_boot: int = 200,
) -> dict[str, object] | None:
    """One target: constant, stage 2, and the oracle counterfactuals."""
    y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
        return None

    # --- stage 1: the level, from slow state, fitted on domain-weeks
    dw_train = domain_weeks(train, target)
    dw_valid = domain_weeks(valid, target)
    if dw_train.empty or dw_valid.empty:
        return None
    chosen = select_predictors(dw_train, target, FOLD_YEARS)
    s1 = BaseRateModel(target=target).fit(dw_train, chosen)
    z1 = offset_logit_for_rows(valid, s1, dw_valid)

    # --- stage 2: the cell model's ranking on top of that level
    raw = fit_lightgbm_classifier(train, valid, feature_cols, target)
    p_oof, y_oof, rows_oof = out_of_fold_frame(
        train, feature_cols, target, FOLD_YEARS, fit_lightgbm_classifier
    )
    p_platt = platt_recalibrate(p_oof, y_oof, raw) if p_oof.size else raw

    # The deviation weight is fitted on the pooled out-of-fold predictions, so
    # it never sees validation and does not inherit the cell model's in-sample
    # overconfidence. The offset is computed from the very rows those
    # predictions came from, which is why out_of_fold_frame returns them:
    # truncating two independently ordered arrays to a common length would pair
    # unrelated rows.
    if p_oof.size:
        z_oof = offset_logit_for_rows(rows_oof, s1, domain_weeks(rows_oof, target))
        weight = fit_deviation_weight(z_oof, p_oof, y_oof)
    else:
        weight = 0.0
    p_stage2 = two_stage_probability(z1, raw, weight=weight)

    # --- references and counterfactuals
    const = constant_event_baseline(train, target, valid)
    seasonal = seasonal_climatology_baseline(train, target, valid)
    const_oracle = np.full(len(valid), float(np.nanmean(y)), dtype=float)
    model_oracle = oracle_calibrate(raw, y)

    b_const = brier(const, y)
    b_seasonal = brier(seasonal, y)
    b_oracle_const = brier(const_oracle, y)
    b_platt = brier(p_platt, y)
    b_stage2 = brier(p_stage2, y)
    b_oracle_model = brier(model_oracle, y)

    # How much of the base-rate gap stage 1 closed. The gap is what the honest
    # single-stage model pays over the oracle-calibrated one.
    gap = b_platt - b_oracle_model
    recovered = (b_platt - b_stage2) / gap if gap > 1e-9 else float("nan")

    weeks = pd.to_datetime(valid["time"]).to_numpy()

    def bss(sel: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        if not m.any():
            return float("nan")
        ref = brier(const[m], y[m])
        return float("nan") if ref <= 1e-12 else 1.0 - brier(p_stage2[m], y[m]) / ref

    ci = block_bootstrap(bss, weeks, n_boot=n_boot)
    dec = brier_decomposition(p_stage2, y)

    return {
        "domain": domain,
        "target": target,
        "horizon": horizon,
        "n": int(np.isfinite(y).sum()),
        "train_rate": round(float(pd.to_numeric(train[target], errors="coerce").mean()), 5),
        "valid_rate": round(float(np.nanmean(y)), 5),
        "stage1_predictors": ",".join(chosen) if chosen else "(season only)",
        "deviation_weight": round(weight, 4),
        "brier_constant": round(b_const, 5),
        "brier_seasonal": round(b_seasonal, 5),
        "brier_oracle_constant": round(b_oracle_const, 5),
        "brier_single_stage": round(b_platt, 5),
        "brier_two_stage": round(b_stage2, 5),
        "brier_oracle_model": round(b_oracle_model, 5),
        "base_rate_gap": round(gap, 5),
        "stage1_recovered": round(recovered, 4) if np.isfinite(recovered) else float("nan"),
        "bss_two_stage_vs_constant": round(ci.point, 5),
        "bss_lo": round(ci.lo, 5),
        "bss_hi": round(ci.hi, 5),
        "n_weeks": ci.n_weeks,
        "n_eff_weeks": round(ci.n_eff, 1),
        "reliability": round(dec["reliability"], 6),
        "resolution": round(dec["resolution"], 6),
    }


def run_domain(domain: str, n_boot: int = 200) -> list[dict[str, object]]:
    from cofire.model.features import load_features

    os.environ["COFIRE_SUBSET_NAME"] = domain
    st = Settings()
    frame = load_features(st.processed_dir / "features_v1")
    if frame.empty:
        LOGGER.warning("%s: no features", domain)
        return []
    frame = all_event_targets(frame, HORIZONS)
    frame = add_slow_predictors(frame)
    cols = feature_columns(frame)
    v1 = [c for c in cols if c.startswith(("esi_", "rci_"))]
    if v1:
        frame = frame[frame[v1].notna().all(axis=1)]

    train, _cal, valid = _splits(frame, st, 0.25)
    if train.empty or valid.empty:
        return []

    rows: list[dict[str, object]] = []
    for h in HORIZONS:
        for target in target_names((h,)):
            if target not in frame.columns:
                continue
            rec = evaluate_target(train, valid, cols, target, h, domain, n_boot)
            if rec is None:
                continue
            rows.append(rec)
            LOGGER.info(
                "%s %-22s h=%d single=%.5f two=%.5f recovered=%s [%s]",
                domain, target, h, rec["brier_single_stage"], rec["brier_two_stage"],
                rec["stage1_recovered"], rec["stage1_predictors"],
            )
    return rows


def run(domains: tuple[str, ...] = ("larimer", "pueblo"), n_boot: int = 200) -> Path:
    rows: list[dict[str, object]] = []
    for dom in domains:
        rows.extend(run_domain(dom, n_boot))
    if not rows:
        raise SystemExit("no two-stage rows produced")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "two_stage.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    LOGGER.info("wrote %s (%d rows)", out, len(rows))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
