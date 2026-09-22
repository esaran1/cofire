"""Split the Brier gap into base-rate cost and discrimination value. HAND-REWRITE.

The question this answers, per target, is where the remaining gap to the
constant baseline actually lives. Two things are conflated in a raw Brier score
on a rare event:

1. **Base-rate cost.** The event rate moves between years with no trend to
   extrapolate. On Pueblo `d_intensify1_h4` it runs 0.0114 in 2024 to 0.1948 in
   2018, a 17x range. Anything fit on past years carries the wrong level into a
   year that does not share it, and on a rare event Brier is dominated by that.

2. **Discrimination value.** Whether the model ranks cell-weeks correctly at
   all, which is what a feature can actually buy.

Four forecasts separate them:

    constant at the training rate    what is achievable in practice
    constant at the TRUE rate        an oracle that knows the level, no ranking
    the fitted model                 what we actually ship
    the model, oracle-calibrated     the model's ranking, level handed to it

The oracle rows are not available in practice. They are counterfactuals whose
only job is attribution:

    base-rate cost   = Brier(train constant) - Brier(oracle constant)
    discrimination   = Brier(oracle constant) - Brier(oracle model)
    calibration loss = Brier(model) - Brier(oracle model)

If the base-rate cost dominates, more features will not help and the next step
is predicting the level. If discrimination dominates, the features are the
place to work.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.ablation import _splits, feature_columns  # noqa: E402
from cofire.model.config import Settings  # noqa: E402
from cofire.model.prob_metrics import block_bootstrap, brier, brier_decomposition  # noqa: E402
from cofire.model.prob_models import (  # noqa: E402
    fit_lightgbm_classifier,
    out_of_fold_predictions,
    platt_recalibrate,
)
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    all_event_targets,
    constant_event_baseline,
    target_names,
)

LOGGER = logging.getLogger("cofire.oracle_decomp")

OUT_DIR = Path("artifacts/ablation")
FOLD_YEARS = (2020, 2021, 2024, 2025)


def oracle_calibrate(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Platt scaling fit on the evaluation outcomes themselves.

    Deliberately cheating, and only ever used to measure a counterfactual. It
    hands the model the level it could not have known while leaving its ranking
    untouched, so the difference from the honest fit prices exactly what not
    knowing the level costs.
    """
    from sklearn.linear_model import LogisticRegression

    m = np.isfinite(p) & np.isfinite(y)
    if m.sum() < 50 or len(np.unique(y[m])) < 2:
        return p
    eps = 1e-6
    q = np.clip(p, eps, 1 - eps)
    z = np.log(q / (1 - q))
    lr = LogisticRegression(max_iter=400)
    lr.fit(z[m].reshape(-1, 1), y[m])
    return np.asarray(lr.predict_proba(z.reshape(-1, 1))[:, 1], dtype=float)


def decompose_target(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    horizon: int,
    domain: str,
    n_boot: int = 200,
) -> dict[str, object] | None:
    """The four forecasts and the attribution for one target."""
    y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
        return None

    train_rate = float(pd.to_numeric(train[target], errors="coerce").mean())
    true_rate = float(np.nanmean(y))

    const_train = constant_event_baseline(train, target, valid)
    const_oracle = np.full(len(valid), true_rate, dtype=float)

    model = fit_lightgbm_classifier(train, valid, feature_cols, target)
    p_oof, y_oof = out_of_fold_predictions(
        train, feature_cols, target, FOLD_YEARS, fit_lightgbm_classifier
    )
    model_cal = platt_recalibrate(p_oof, y_oof, model) if p_oof.size else model
    model_oracle = oracle_calibrate(model, y)

    b_ct = brier(const_train, y)
    b_co = brier(const_oracle, y)
    b_m = brier(model_cal, y)
    b_mo = brier(model_oracle, y)

    # Block-bootstrap the honest skill against the honest baseline.
    weeks = pd.to_datetime(valid["time"]).to_numpy()

    def bss(sel: np.ndarray) -> float:
        m = np.isin(weeks, sel)
        if not m.any():
            return float("nan")
        ref = brier(const_train[m], y[m])
        return float("nan") if ref <= 1e-12 else 1.0 - brier(model_cal[m], y[m]) / ref

    ci = block_bootstrap(bss, weeks, n_boot=n_boot)
    dec = brier_decomposition(model_cal, y)

    return {
        "domain": domain,
        "target": target,
        "horizon": horizon,
        "n": int(np.isfinite(y).sum()),
        "train_rate": round(train_rate, 5),
        "valid_rate": round(true_rate, 5),
        "rate_ratio": round(true_rate / train_rate, 3) if train_rate > 0 else float("nan"),
        "brier_const_train": round(b_ct, 5),
        "brier_const_oracle": round(b_co, 5),
        "brier_model": round(b_m, 5),
        "brier_model_oracle": round(b_mo, 5),
        # Attribution. Positive base_rate_cost means knowing the level would help.
        "base_rate_cost": round(b_ct - b_co, 5),
        "discrimination_value": round(b_co - b_mo, 5),
        "calibration_loss": round(b_m - b_mo, 5),
        "bss_vs_const_train": round(ci.point, 5),
        "bss_lo": round(ci.lo, 5),
        "bss_hi": round(ci.hi, 5),
        "n_weeks": ci.n_weeks,
        "n_eff_weeks": round(ci.n_eff, 1),
        "reliability": round(dec["reliability"], 6),
        "resolution": round(dec["resolution"], 6),
        "uncertainty": round(dec["uncertainty"], 6),
        # Which term dominates, stated rather than left to the reader to infer.
        "dominant": (
            "base_rate" if (b_ct - b_co) > (b_co - b_mo) else "discrimination"
        ),
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
    cols = feature_columns(frame)

    # Equal row sets, as in the ablation: every arm sees the same rows.
    v1 = [c for c in cols if c.startswith(("esi_", "rci_"))]
    if v1:
        frame = frame[frame[v1].notna().all(axis=1)]

    train, _cal, valid = _splits(frame, st, 0.25)
    if train.empty or valid.empty:
        LOGGER.warning("%s: empty split", domain)
        return []

    rows: list[dict[str, object]] = []
    for h in HORIZONS:
        for target in target_names((h,)):
            if target not in frame.columns:
                continue
            rec = decompose_target(train, valid, cols, target, h, domain, n_boot)
            if rec is None:
                LOGGER.info("%s %s: degenerate, skipped", domain, target)
                continue
            rows.append(rec)
            LOGGER.info(
                "%s %-22s h=%d rates %.4f->%.4f  base_rate=%.5f discrim=%.5f  %s",
                domain, target, h, rec["train_rate"], rec["valid_rate"],
                rec["base_rate_cost"], rec["discrimination_value"], rec["dominant"],
            )
    return rows


def run(domains: tuple[str, ...] = ("larimer", "pueblo"), n_boot: int = 200) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for dom in domains:
        rows.extend(run_domain(dom, n_boot))
    if not rows:
        raise SystemExit("no decomposition rows produced")
    df = pd.DataFrame(rows)
    out = OUT_DIR / "oracle_decomposition.csv"
    df.to_csv(out, index=False)
    LOGGER.info("wrote %s (%d rows)", out, len(df))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
