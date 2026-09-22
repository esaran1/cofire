"""Phase 3: source-group ablation against the Markov baseline. HAND-REWRITE.

The headline scientific result. For each target, horizon, domain and feature
set, fit a classifier and score it against the Markov transition baseline with
block-bootstrap confidence intervals resampled by week.

Three things this is careful about:

1. **The baseline is the opponent, not the floor.** Every number is reported as
   skill against Markov, which already knows the (category, month) transition
   statistics. A model that cannot beat it has not earned its complexity, and
   reporting raw Brier would hide that.

2. **Isotonic recalibration is fit on a calibration split the model never
   trained on.** Class weighting deliberately distorts the probability scale, so
   the raw scores rank well and calibrate badly. The calibration split is carved
   out of training years, never from validation.

3. **Confidence intervals resample weeks.** Cell-weeks are autocorrelated in
   space and time; a row bootstrap would report intervals several times too
   narrow and turn noise into findings.

macOS threading: LightGBM is pinned to one thread and torch is never imported
in this process, so the documented OpenMP deadlock cannot be reached here.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.config import Settings, get_settings  # noqa: E402
from cofire.model.prob_metrics import evaluate_probabilistic  # noqa: E402
from cofire.model.prob_models import (  # noqa: E402
    ablation_sets,
    fit_lightgbm_classifier,
    fit_logistic,
    out_of_fold_predictions,
    platt_recalibrate,
    split_groups,
)
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    MarkovBaseline,
    all_event_targets,
    climatology_event_baseline,
    constant_event_baseline,
    persistence_event_baseline,
    target_names,
)

LOGGER = logging.getLogger("cofire.ablation")

# Columns that are outcomes, identifiers or raw coordinates: never features.
NON_FEATURES = {"time", "cell_id", "lat", "lon", "year"}


@dataclass
class AblationConfig:
    """What to run. Kept small so the grid stays reportable."""

    horizons: tuple[int, ...] = HORIZONS
    arms: tuple[str, ...] = ("lightgbm", "logistic")
    n_boot: int = 300
    cal_fraction: float = 0.25
    seed: int = 2026
    targets: tuple[str, ...] = ()
    # LODO folds used to pool out-of-fold predictions for the calibrator.
    fold_years: tuple[int, ...] = (2020, 2021, 2024, 2025)
    # Restrict every arm to the rows where every source group is present, so a
    # group's lift is not confounded with how many rows it can be fit on.
    equal_rows: bool = True


# Columns built by shifting a series backwards in time, i.e. the future values
# the model is asked to predict. The regression feature store carries these as
# `usdm_h4`, `erc_pct_h4` and so on, built with `shift(-h)`. They are targets,
# never inputs: including them gave AUC 1.000 and Brier skill 0.995 against the
# Markov baseline, which is what a leak looks like.
FUTURE_SUFFIX = re.compile(r"_h\d+$")


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Numeric predictors, excluding every target, leak and identifier."""
    tgt = set(target_names())
    out = []
    for c in frame.columns:
        if c in NON_FEATURES or c in tgt:
            continue
        if c.startswith(("d_", "f_")):  # event targets at any horizon
            continue
        if FUTURE_SUFFIX.search(c):  # future-dated: see FUTURE_SUFFIX
            continue
        if pd.api.types.is_numeric_dtype(frame[c]):
            out.append(c)
    return out


def _splits(
    frame: pd.DataFrame, settings: Settings, cal_fraction: float
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Train / calibration / validation, split by time and never by row.

    The calibration slice is the *latest* training weeks, so it is the closest
    thing to validation that validation never sees. Splitting calibration
    randomly across rows would leak: two cells in the same week are near
    duplicates.
    """
    t = pd.to_datetime(frame["time"])
    train_end = pd.Timestamp(settings.train_end)
    valid = frame[(t >= pd.Timestamp(settings.valid_start)) & (t <= pd.Timestamp(settings.valid_end))]
    train_all = frame[t <= train_end]

    weeks = np.array(sorted(pd.to_datetime(train_all["time"]).unique()))
    if len(weeks) < 8:
        return train_all, train_all.iloc[:0], valid
    cut = weeks[int(len(weeks) * (1 - cal_fraction))]
    tt = pd.to_datetime(train_all["time"])
    return train_all[tt < cut], train_all[tt >= cut], valid


def run_domain(
    frame: pd.DataFrame,
    settings: Settings,
    cfg: AblationConfig,
    domain: str,
) -> list[dict[str, object]]:
    """Every (target, horizon, feature set, arm) for one domain."""
    rows: list[dict[str, object]] = []
    frame = all_event_targets(frame, cfg.horizons)
    feats = feature_columns(frame)
    groups = split_groups(feats)
    sets = ablation_sets(groups)
    LOGGER.info(
        "%s: %d rows, %d features -> sets %s",
        domain,
        len(frame),
        len(feats),
        {k: len(v) for k, v in sets.items()},
    )

    # Equal row sets. ESI exists only from 2018, while the feature store starts
    # earlier, so an arm carrying ESI features is otherwise fit on a different
    # and smaller sample than the gridMET-only arm. Its lift would then be
    # confounded with sample size rather than attributable to the source. Every
    # arm, gridMET-only included, is restricted to the rows where every group is
    # present, and the unrestricted gridMET-only result is reported separately.
    full_frame = frame
    if cfg.equal_rows:
        v1_cols = [c for g in ("esi", "rci") for c in groups.get(g, [])]
        if v1_cols:
            keep = frame[v1_cols].notna().all(axis=1)
            LOGGER.info(
                "%s: equal-row restriction keeps %d of %d rows (%.1f%%)",
                domain, int(keep.sum()), len(frame), 100.0 * float(keep.mean()),
            )
            frame = frame[keep]

    train, cal, valid = _splits(frame, settings, cfg.cal_fraction)
    LOGGER.info("%s: train=%d cal=%d valid=%d", domain, len(train), len(cal), len(valid))
    if valid.empty or train.empty:
        LOGGER.warning("%s: empty split, skipping", domain)
        return rows

    # The full-record gridMET-only arm, reported beside the restricted one so
    # the cost of the restriction is visible rather than assumed away.
    full_train, _full_cal, full_valid = _splits(full_frame, settings, cfg.cal_fraction)

    wanted = set(cfg.targets) if cfg.targets else None

    for h in cfg.horizons:
        markov = MarkovBaseline(horizon=h).fit(train)
        mk_valid = markov.predict_events(valid)

        for tname in target_names((h,)):
            if tname not in frame.columns:
                continue
            if wanted and tname not in wanted:
                continue
            y_valid = pd.to_numeric(valid[tname], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(y_valid).any() or len(np.unique(y_valid[np.isfinite(y_valid)])) < 2:
                LOGGER.info("%s h=%d %s: degenerate target, skipping", domain, h, tname)
                continue

            baselines = {
                # Constant is the primary skill reference: it is the hardest
                # opponent on rare events, because Brier is calibration
                # dominated and a constant has no reliability error to pay.
                "constant": constant_event_baseline(train, tname, valid),
                "markov": mk_valid.get(tname, np.full(len(valid), np.nan)),
                "climatology": climatology_event_baseline(train, tname, valid),
                "persistence": persistence_event_baseline(valid, tname),
            }
            # Score the baselines themselves, so the table has a floor row.
            for bname, bp in baselines.items():
                rep = evaluate_probabilistic(
                    bp, y_valid, valid["time"].to_numpy(),
                    # Constant first: it is the primary reference. Markov is
                    # secondary, reported now that it satisfies the training
                    # bound on both domains.
                    {"constant": baselines["constant"], "markov": baselines["markov"]},
                    n_boot=cfg.n_boot,
                )
                rows.append(
                    {"domain": domain, "target": tname, "horizon": h, "arm": f"baseline:{bname}",
                     "feature_set": "-", "n_features": 0, "runtime_s": 0.0, **rep}
                )

            for set_name, cols in sets.items():
                for arm in cfg.arms:
                    t0 = time.time()
                    fit = fit_lightgbm_classifier if arm == "lightgbm" else fit_logistic
                    try:
                        p_valid = fit(train, valid, cols, tname)
                        # Platt on pooled out-of-fold predictions, not isotonic
                        # on one calibration split: the base rate moves between
                        # years, and a calibrator fit on a single year carries
                        # that year's rate into one that does not share it.
                        p_oof, y_oof = out_of_fold_predictions(
                            train, cols, tname, cfg.fold_years, fit
                        )
                        if p_oof.size:
                            p_valid = platt_recalibrate(p_oof, y_oof, p_valid)
                        elif not cal.empty:
                            p_cal = fit(train, cal, cols, tname)
                            y_cal = pd.to_numeric(cal[tname], errors="coerce").to_numpy(dtype=float)
                            p_valid = platt_recalibrate(p_cal, y_cal, p_valid)
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning("%s %s %s h=%d failed: %s", domain, arm, tname, h, exc)
                        continue
                    rep = evaluate_probabilistic(
                        p_valid, y_valid, valid["time"].to_numpy(), baselines, n_boot=cfg.n_boot
                    )
                    rows.append(
                        {"domain": domain, "target": tname, "horizon": h, "arm": arm,
                         "feature_set": set_name, "n_features": len(cols),
                         "row_set": "equal" if cfg.equal_rows else "full",
                         "n_rows_train": len(train),
                         "runtime_s": round(time.time() - t0, 1), **rep}
                    )
                    # Same arm on the unrestricted record, for the base group
                    # only: that is where the restriction costs rows, and
                    # comparing the two prices the restriction itself.
                    if cfg.equal_rows and set_name == "gridmet" and not full_valid.empty:
                        try:
                            p_full = fit(full_train, full_valid, cols, tname)
                            y_full = pd.to_numeric(
                                full_valid[tname], errors="coerce"
                            ).to_numpy(dtype=float)
                            mk_full = MarkovBaseline(horizon=h).fit(full_train)
                            rep_full = evaluate_probabilistic(
                                p_full, y_full, full_valid["time"].to_numpy(),
                                {
                                    "markov": mk_full.predict_events(full_valid).get(
                                        tname, np.full(len(full_valid), np.nan)
                                    ),
                                    "constant": constant_event_baseline(
                                        full_train, tname, full_valid
                                    ),
                                },
                                n_boot=cfg.n_boot,
                            )
                            rows.append(
                                {"domain": domain, "target": tname, "horizon": h,
                                 "arm": arm, "feature_set": "gridmet_full_record",
                                 "n_features": len(cols), "row_set": "full",
                                 "n_rows_train": len(full_train),
                                 "runtime_s": 0.0, **rep_full}
                            )
                        except Exception as exc:  # noqa: BLE001
                            LOGGER.warning("%s full-record arm failed: %s", domain, exc)
                    LOGGER.info(
                        "%s %s %s h=%d [%s] bss_markov=%.4f (%.4f..%.4f) auc=%.3f",
                        domain, arm, tname, h, set_name,
                        rep.get("bss_vs_markov", float("nan")),
                        rep.get("bss_vs_markov_lo", float("nan")),
                        rep.get("bss_vs_markov_hi", float("nan")),
                        rep.get("roc_auc", float("nan")),
                    )
    return rows


def lift_table(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Ablation lift: what each source group adds, per target and horizon.

    Lift is the change in Brier skill against Markov when a group is added, so a
    positive number means the group bought skill the baseline did not have.
    """
    df = pd.DataFrame([r for r in rows if not str(r["arm"]).startswith("baseline:")])
    if df.empty:
        return df
    order = ["gridmet", "+esi", "+rci"]
    out = []
    for (dom, tgt, h, arm), g in df.groupby(["domain", "target", "horizon", "arm"]):
        by = {r["feature_set"]: r for _, r in g.iterrows()}
        prev = None
        for s in order:
            if s not in by:
                continue
            cur = float(by[s]["bss_vs_markov"])
            out.append({
                "domain": dom, "target": tgt, "horizon": h, "arm": arm, "feature_set": s,
                "bss_vs_markov": cur,
                "bss_lo": float(by[s]["bss_vs_markov_lo"]),
                "bss_hi": float(by[s]["bss_vs_markov_hi"]),
                # Skill against a constant at the training base rate. This is
                # the column to read first: Markov proved miscalibrated on the
                # validation regime, so skill against it overstates the models.
                "bss_vs_constant": float(by[s].get("bss_vs_constant", float("nan"))),
                "bss_vs_constant_lo": float(by[s].get("bss_vs_constant_lo", float("nan"))),
                "bss_vs_constant_hi": float(by[s].get("bss_vs_constant_hi", float("nan"))),
                "brier": float(by[s]["brier"]),
                "lift_over_previous": float("nan") if prev is None else cur - prev,
                "roc_auc": float(by[s]["roc_auc"]),
                "n_weeks": by[s].get("n_weeks"),
                "n_eff_weeks": by[s].get("n_eff_weeks"),
            })
            prev = cur
    return pd.DataFrame(out)


def run(
    settings: Settings | None = None,
    cfg: AblationConfig | None = None,
    domains: tuple[str, ...] = ("larimer", "pueblo"),
) -> Path:
    """Run both domains and write the artifacts."""
    from cofire.model.config import Settings as S
    from cofire.model.features import load_features

    cfg = cfg or AblationConfig()
    out_dir = Path("artifacts/ablation")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, object]] = []

    for dom in domains:
        os.environ["COFIRE_SUBSET_NAME"] = dom
        get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
        st = S() if settings is None else settings
        root = st.processed_dir / "features_v1"
        if not root.exists():
            root = st.processed_dir / "features"
            LOGGER.warning("%s: no features_v1, falling back to %s", dom, root)
        frame = load_features(root)
        if frame.empty:
            LOGGER.warning("%s: no features at %s, skipping", dom, root)
            continue
        all_rows.extend(run_domain(frame, st, cfg, dom))

    if not all_rows:
        raise SystemExit("ablation produced no rows; check feature stores")

    raw = pd.DataFrame(all_rows)
    raw.to_csv(out_dir / "results.csv", index=False)
    lift = lift_table(all_rows)
    lift.to_csv(out_dir / "lift_by_source_group.csv", index=False)
    (out_dir / "config.json").write_text(
        json.dumps({"horizons": list(cfg.horizons), "arms": list(cfg.arms),
                    "n_boot": cfg.n_boot, "cal_fraction": cfg.cal_fraction,
                    "seed": cfg.seed, "domains": list(domains)}, indent=2)
    )
    LOGGER.info("wrote %s (%d rows) and the lift table (%d rows)",
                out_dir / "results.csv", len(raw), len(lift))
    return out_dir


if __name__ == "__main__":
    from cofire.model.log import setup_logging

    setup_logging(Path("logs"))
    run()
