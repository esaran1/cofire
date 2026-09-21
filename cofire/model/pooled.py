"""Item 4: does pooling the two domains help either of them? HAND-REWRITE.

The motivation is the unanimity measurement. Within a week the cells of one
domain move together, so a domain contributes roughly one independent time
series rather than 432. Two domains are therefore two series, and doubling the
number of independent episodes is a much larger relative gain than doubling the
number of rows would suggest.

Against that, the domains differ: Larimer is montane with elevation-limited ESI
coverage, Pueblo is lower and drier. Pooling imposes one set of splits on both.
A domain indicator lets the trees separate them where that matters, but it does
not make the comparison free, which is why the per-domain model is the control
and the evaluation is always per domain.

Evaluated on LODO folds rather than a single validation year, because with so
few independent episodes a single year's result is mostly noise.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.ablation import feature_columns  # noqa: E402
from cofire.model.config import Settings  # noqa: E402
from cofire.model.prob_metrics import block_bootstrap, brier  # noqa: E402
from cofire.model.prob_models import fit_lightgbm_classifier  # noqa: E402
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    all_event_targets,
    constant_event_baseline,
    target_names,
)

LOGGER = logging.getLogger("cofire.pooled")

OUT_DIR = Path("artifacts/ablation")
FOLD_YEARS = (2020, 2021, 2024, 2025)
DOMAINS = ("larimer", "pueblo")


def load_domain(domain: str) -> pd.DataFrame:
    """One domain's v1 features with targets, restricted to equal rows."""
    from cofire.model.features import load_features

    os.environ["COFIRE_SUBSET_NAME"] = domain
    st = Settings()
    frame = load_features(st.processed_dir / "features_v1")
    if frame.empty:
        return frame
    frame = all_event_targets(frame, HORIZONS)
    cols = feature_columns(frame)
    v1 = [c for c in cols if c.startswith(("esi_", "rci_"))]
    if v1:
        frame = frame[frame[v1].notna().all(axis=1)]
    frame = frame.copy()
    frame["domain"] = domain
    # A numeric indicator, so the trees can split on it where the domains
    # genuinely differ and ignore it where they do not.
    frame["domain_id"] = float(DOMAINS.index(domain))
    return frame


def lodo_brier(
    frame: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    eval_domain: str,
    fold_years: tuple[int, ...] = FOLD_YEARS,
) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray]:
    """Brier over held-out years, always scored on `eval_domain` only.

    Returns (model brier, constant brier, pooled predictions, outcomes, weeks).
    Training may span both domains; scoring never does.
    """
    t = pd.to_datetime(frame["time"])
    ps: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    cs: list[np.ndarray] = []
    ws: list[np.ndarray] = []
    for year in fold_years:
        train = frame[t.dt.year != year]
        held = frame[(t.dt.year == year) & (frame["domain"] == eval_domain)]
        if train.empty or held.empty:
            continue
        y = pd.to_numeric(held[target], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
            continue
        p = fit_lightgbm_classifier(train, held, feature_cols, target)
        ps.append(np.asarray(p, dtype=float))
        ys.append(y)
        cs.append(constant_event_baseline(train, target, held))
        ws.append(pd.to_datetime(held["time"]).to_numpy())
    if not ps:
        return float("nan"), float("nan"), np.array([]), np.array([]), np.array([])
    p_all = np.concatenate(ps)
    y_all = np.concatenate(ys)
    c_all = np.concatenate(cs)
    w_all = np.concatenate(ws)
    return brier(p_all, y_all), brier(c_all, y_all), p_all, y_all, w_all


def compare_target(
    per_domain: dict[str, pd.DataFrame],
    pooled: pd.DataFrame,
    feature_cols: list[str],
    target: str,
    horizon: int,
    n_boot: int = 200,
) -> list[dict[str, object]]:
    """Per-domain against pooled, evaluated separately on each domain."""
    rows: list[dict[str, object]] = []
    for dom in DOMAINS:
        own = per_domain.get(dom)
        if own is None or own.empty or target not in own.columns:
            continue
        b_own, b_const, p_own, y, weeks = lodo_brier(own, feature_cols, target, dom)
        b_pool, _, p_pool, y2, _ = lodo_brier(pooled, feature_cols, target, dom)
        if not np.isfinite(b_own) or not np.isfinite(b_pool):
            continue
        if y.shape != y2.shape:
            LOGGER.warning("%s %s: fold shapes differ, skipping", dom, target)
            continue

        # Bind the loop variables as defaults: a closure over them would
        # capture whatever the last iteration left behind, not this domain's.
        def bss(
            sel: np.ndarray,
            p: np.ndarray = p_pool,
            _w: np.ndarray = weeks,
            _y: np.ndarray = y,
        ) -> float:
            m = np.isin(_w, sel)
            if not m.any():
                return float("nan")
            ref = brier(np.full(int(m.sum()), float(np.nanmean(_y[m]))), _y[m])
            return float("nan") if ref <= 1e-12 else 1.0 - brier(p[m], _y[m]) / ref

        ci = block_bootstrap(bss, weeks, n_boot=n_boot)
        rows.append(
            {
                "domain": dom,
                "target": target,
                "horizon": horizon,
                "n": int(y.size),
                "brier_per_domain": round(b_own, 5),
                "brier_pooled": round(b_pool, 5),
                "brier_constant": round(b_const, 5),
                # Positive means pooling helped this domain.
                "pooling_gain": round(b_own - b_pool, 5),
                "bss_pooled_vs_constant": round(ci.point, 5),
                "bss_lo": round(ci.lo, 5),
                "bss_hi": round(ci.hi, 5),
                "n_weeks": ci.n_weeks,
                "n_eff_weeks": round(ci.n_eff, 1),
                "verdict": "pooling helps" if b_own - b_pool > 0 else "per-domain better",
            }
        )
        LOGGER.info(
            "%s %-22s h=%d own=%.5f pooled=%.5f gain=%+.5f",
            dom, target, horizon, b_own, b_pool, b_own - b_pool,
        )
    return rows


def run(n_boot: int = 200) -> Path:
    per_domain = {d: load_domain(d) for d in DOMAINS}
    present = {d: f for d, f in per_domain.items() if not f.empty}
    if len(present) < 2:
        raise SystemExit(f"pooling needs both domains, have {sorted(present)}")

    pooled = pd.concat(present.values(), ignore_index=True)
    # Features common to both, plus the domain indicator.
    common = sorted(set.intersection(*(set(feature_columns(f)) for f in present.values())))
    if "domain_id" not in common:
        common.append("domain_id")
    LOGGER.info("pooled rows=%d, common features=%d", len(pooled), len(common))

    rows: list[dict[str, object]] = []
    for h in HORIZONS:
        for target in target_names((h,)):
            if any(target not in f.columns for f in present.values()):
                continue
            rows.extend(compare_target(present, pooled, common, target, h, n_boot))
    if not rows:
        raise SystemExit("no pooled comparison rows produced")
    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "pooled_vs_per_domain.csv"
    df.to_csv(out, index=False)
    LOGGER.info("wrote %s (%d rows)", out, len(df))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
