"""Step 3: the mechanical rerun of configuration A on the extended record.

No method changes. Everything is refitted from scratch on the restored 2007 to
2021 training split, through the audited loader, and every fitted artifact
records the window it was fitted on.

Staged so no single run exceeds the hour: `stage_step1`, `stage_continuous`,
`stage_pid` and `stage_classify` each write their own artifact and can be run
independently, so a hang costs one stage rather than the run.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.config import Settings, get_settings  # noqa: E402
from cofire.model.features_a import add_horizons  # noqa: E402
from cofire.model.features_a import load as load_a
from cofire.model.fit_window import (  # noqa: E402
    TRAIN_ONLY,
    FitWindow,
    write_sidecar,
)
from cofire.model.prob_metrics import brier, brier_decomposition  # noqa: E402
from cofire.model.shipping import (  # noqa: E402
    DOMAIN_FOLDS,
    FIRE_ARMS,
    FOLD_YEARS,
    ShippingChoice,
    _drought_prediction,
    _fire_prediction,
    continuous_predict,
    lodo_score,
    save,
)
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    all_event_targets,
    target_names,
)

LOGGER = logging.getLogger("cofire.rerun_a")

OUT = Path("artifacts/rerun_a")
DOMAINS = ("larimer", "pueblo")


def load_domain(domain: str) -> tuple[pd.DataFrame, pd.DataFrame, Settings]:
    """Targets attached, split applied. Train and validation frames."""
    os.environ["COFIRE_SUBSET_NAME"] = domain
    get_settings.cache_clear()
    st = get_settings()
    frame = load_a(st)
    if frame.empty:
        raise SystemExit(f"{domain}: no config-A store")
    frame["time"] = pd.to_datetime(frame["time"])
    frame = add_horizons(frame, HORIZONS)
    frame = all_event_targets(frame, HORIZONS)
    t = frame["time"]
    train = frame[t <= pd.Timestamp(st.train_end)]
    valid = frame[
        (t >= pd.Timestamp(st.valid_start)) & (t <= pd.Timestamp(st.valid_end))
    ]
    return train, valid, st


def stage_step1(n_domains: tuple[str, ...] = DOMAINS) -> Path:
    """Family per target, pooled against per-domain, on the shared folds."""
    frames = {d: load_domain(d)[0] for d in n_domains}
    pooled = pd.concat(
        [f.assign(domain=d, domain_id=float(DOMAINS.index(d))) for d, f in frames.items()],
        ignore_index=True,
    )
    choices: list[ShippingChoice] = []
    for h in HORIZONS:
        for target in target_names((h,)):
            if any(target not in f.columns for f in frames.values()):
                continue
            arms = FIRE_ARMS if target.startswith("f_gt") else ("markov",)
            best: ShippingChoice | None = None
            for arm in arms:
                per_dom = [lodo_score(f, target, h, arm, FOLD_YEARS)[0] for f in frames.values()]
                per_mean = float(np.nanmean(per_dom)) if per_dom else float("nan")
                pooled_scores = [
                    lodo_score(pooled, target, h, arm, FOLD_YEARS, eval_domain=d)[0]
                    for d in frames
                ]
                pool_mean = float(np.nanmean(pooled_scores)) if pooled_scores else float("nan")
                use_pooled = np.isfinite(pool_mean) and (
                    not np.isfinite(per_mean) or pool_mean <= per_mean
                )
                score = pool_mean if use_pooled else per_mean
                if not np.isfinite(score):
                    continue
                src = pooled if use_pooled else next(iter(frames.values()))
                _b, rel, res = lodo_score(src, target, h, arm, FOLD_YEARS)
                cand = ShippingChoice(target, h, arm, bool(use_pooled), score, rel, res)
                if best is None or cand.lodo_brier < best.lodo_brier:
                    best = cand
            if best is not None:
                choices.append(best)
                LOGGER.info(
                    "%-16s h=%d -> %-11s pooled=%-5s brier=%.5f rel=%.6f res=%.6f",
                    best.target, best.horizon, best.family, best.pooled,
                    best.lodo_brier, best.reliability, best.resolution,
                )
    OUT.mkdir(parents=True, exist_ok=True)
    p = save(choices, out_dir=OUT)
    st = get_settings()
    write_sidecar(p, FitWindow(st.train_start, st.train_end, TRAIN_ONLY), "step1 choices")
    return p


def stage_by_domain() -> Path:
    """Per-domain Brier and decomposition under the frozen families."""
    from cofire.model.shipping import load as load_choices

    choices = load_choices(out_dir=OUT)
    if not choices:
        raise SystemExit("run stage_step1 first")
    rows: list[dict[str, object]] = []
    for dom in DOMAINS:
        train, _valid, _st = load_domain(dom)
        folds = DOMAIN_FOLDS[dom]
        for (target, h), c in sorted(choices.items()):
            if target not in train.columns:
                continue
            b, rel, res = lodo_score(train, target, h, c.family, folds)
            if not np.isfinite(b):
                continue
            rows.append(
                {
                    "domain": dom, "target": target, "horizon": h, "family": c.family,
                    "pooled": c.pooled, "lodo_brier": round(b, 5),
                    "reliability": round(rel, 6), "resolution": round(res, 6),
                    "n_folds": len(folds),
                }
            )
        LOGGER.info("%s: %d rows over %d folds", dom, len(rows), len(folds))
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "step1_by_domain.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def baseline_table(n_boot: int = 400) -> Path:
    """Every shipped target against every applicable baseline, on validation."""
    from cofire.model.shipping import load as load_choices
    from cofire.model.stats_lib import circular_block_bootstrap
    from cofire.model.targets import (
        MarkovBaseline,
        constant_event_baseline,
        damped_persistence_baseline,
        fire_transition_baseline,
        persistence_event_baseline,
        seasonal_climatology_baseline,
    )

    choices = load_choices(out_dir=OUT)
    rows: list[dict[str, object]] = []
    for dom in DOMAINS:
        train, valid, _st = load_domain(dom)
        for (target, h), c in sorted(choices.items()):
            if target not in valid.columns:
                continue
            y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
                continue
            pred = (
                _drought_prediction(h, train, target, valid)
                if c.family == "markov"
                else _fire_prediction(c.family, train, target, valid)
            )
            refs: dict[str, np.ndarray] = {
                "seasonal": seasonal_climatology_baseline(train, target, valid),
                "persistence": persistence_event_baseline(valid, target),
                "constant": constant_event_baseline(train, target, valid),
            }
            if target.startswith("f_gt"):
                refs["transition"] = fire_transition_baseline(train, target, valid)
                refs["damped"] = damped_persistence_baseline(train, target, valid)
            else:
                refs["markov"] = (
                    MarkovBaseline(horizon=h).fit(train).predict_events(valid).get(
                        target, np.full(len(valid), np.nan)
                    )
                )
            weeks = pd.to_datetime(valid["time"]).to_numpy()
            dec = brier_decomposition(pred, y)
            rec: dict[str, object] = {
                "domain": dom, "target": target, "horizon": h, "family": c.family,
                "n": int(np.isfinite(y).sum()),
                "brier_model": round(brier(pred, y), 5),
                "reliability": round(dec["reliability"], 6),
                "resolution": round(dec["resolution"], 6),
            }
            for name, ref in refs.items():
                bref = brier(ref, y)
                rec[f"brier_{name}"] = round(bref, 5)
                rec[f"bss_vs_{name}"] = (
                    round(1.0 - brier(pred, y) / bref, 5) if bref > 1e-12 else float("nan")
                )

            # The headline comparison for fire: against the transition table.
            key = "transition" if target.startswith("f_gt") else "seasonal"
            ref = refs[key]

            def stat(sel: np.ndarray, pred: np.ndarray = pred, y: np.ndarray = y,
                     ref: np.ndarray = ref, weeks: np.ndarray = weeks) -> float:
                m = np.isin(weeks, sel)
                if not m.any():
                    return float("nan")
                b = brier(ref[m], y[m])
                return float("nan") if b <= 1e-12 else 1.0 - brier(pred[m], y[m]) / b

            res = circular_block_bootstrap(stat, weeks, y, n_boot=n_boot)
            rec.update(
                {
                    "headline_ref": key,
                    "bss_lo": round(res.lo, 4) if np.isfinite(res.lo) else float("nan"),
                    "bss_hi": round(res.hi, 4) if np.isfinite(res.hi) else float("nan"),
                    "n_positive_weeks": res.n_positive_weeks,
                    "estimable": res.estimable,
                }
            )
            rows.append(rec)
            LOGGER.info(
                "%s %-16s h=%d %s bss_vs_%s=%+.4f [%s] posWk=%d",
                dom, target, h, c.family, key, rec[f"bss_vs_{key}"],
                "not estimable" if not res.estimable else f"{res.lo:+.3f},{res.hi:+.3f}",
                res.n_positive_weeks,
            )
    OUT.mkdir(parents=True, exist_ok=True)
    p_out = OUT / "baselines.csv"
    pd.DataFrame(rows).to_csv(p_out, index=False)
    return p_out


def stage_continuous() -> Path:
    """Continuous analogue per horizon, on pooled-fold MAE."""
    frames = {d: load_domain(d)[0] for d in DOMAINS}
    pooled = pd.concat(frames.values(), ignore_index=True)
    t = pd.to_datetime(pooled["time"])
    chosen: dict[int, str] = {}
    for h in HORIZONS:
        scores: dict[str, float] = {}
        for arm in ("damped_regression", "decile_mean"):
            errs: list[float] = []
            for year in FOLD_YEARS:
                tr, te = pooled[t.dt.year != year], pooled[t.dt.year == year]
                if tr.empty or te.empty:
                    continue
                y = pd.to_numeric(te.get(f"erc_pct_h{h}"), errors="coerce").to_numpy(dtype=float)
                pr = continuous_predict(arm, tr, h, te)
                m = np.isfinite(y) & np.isfinite(pr)
                if m.any():
                    errs.append(float(np.mean(np.abs(pr[m] - y[m]))))
            scores[arm] = float(np.mean(errs)) if errs else float("inf")
        best = min(scores, key=lambda k: scores[k])
        chosen[h] = best
        LOGGER.info("h=%d -> %s (MAE %s)", h, best, {k: round(v, 3) for k, v in scores.items()})
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "continuous_arms.json"
    out_path.write_text(json.dumps({str(k): v for k, v in chosen.items()}, indent=2))
    st = get_settings()
    write_sidecar(out_path, FitWindow(st.train_start, st.train_end, TRAIN_ONLY), "continuous arms")
    return out_path


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    stage = sys.argv[1] if len(sys.argv) > 1 else "step1"
    fn = {
        "step1": stage_step1,
        "by_domain": stage_by_domain,
        "baselines": baseline_table,
        "continuous": stage_continuous,
    }[stage]
    print(fn())
