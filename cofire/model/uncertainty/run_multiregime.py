"""Run the pre-registered multi-regime calibration experiment.

Executes exactly the variants in docs/PREREGISTRATION_CALIBRATION.md across LODO
folds, on both dev subsets, and writes artifacts/uncertainty/multiregime.{md,json}.

Per-fold checkpoints so an interrupted run resumes (the v0.5 OpenMP deadlock cost
a whole run once). Never touches 2026.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import HORIZONS_WEEKS, SEED, get_settings
from cofire.model.features import load_features
from cofire.model.lodo import HOLDOUT_YEAR, LODO_YEARS
from cofire.model.log import setup_logging
from cofire.model.models.lightgbm_arm import LightGBMConditionModel
from cofire.model.uncertainty.multiregime import (
    evaluate_variant,
    label,
    regime_profiles,
    variant_specs,
    write_report,
)


def _predictions_by_year(frame: pd.DataFrame, fold_year: int, seed: int = SEED) -> dict[int, pd.DataFrame]:
    """Fit with fold_year removed, predict every year (incl. the fold) once."""
    t = pd.to_datetime(frame["time"])
    train = frame[(t.dt.year != fold_year) & (t.dt.year != HOLDOUT_YEAR)].copy()
    model = LightGBMConditionModel(seed=seed)
    model.fit(train, None)
    out: dict[int, pd.DataFrame] = {}
    for year, chunk in frame.groupby(t.dt.year):
        y = int(year)
        if y == HOLDOUT_YEAR:
            continue
        c = chunk.reset_index(drop=True)
        out[y] = c.join(model.predict(c).reset_index(drop=True))
    return out


def run_for_domain(domain: str, ckpt_dir: Path, resume: bool = True) -> list[dict[str, object]]:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    frame = load_features(settings.processed_dir / "features")
    if frame.empty:
        log.warning("no features for domain %s", domain)
        return []
    rows: list[dict[str, object]] = []
    for fold_year in LODO_YEARS:
        ck = ckpt_dir / f"{domain}_{fold_year}.json"
        if resume and ck.exists():
            log.info("multiregime resume %s", ck.name)
            rows.extend(json.loads(ck.read_text()))
            continue
        log.info("multiregime domain=%s fold=%s", domain, fold_year)
        preds = _predictions_by_year(frame, fold_year)
        if fold_year not in preds:
            continue
        profiles = regime_profiles(frame)
        got: list[dict[str, object]] = []
        for h in HORIZONS_WEEKS:
            resid = {
                y: np.abs(
                    pd.to_numeric(df[f"erc_pct_h{h}"], errors="coerce").to_numpy(dtype=float)
                    - pd.to_numeric(df[f"erc_pct_h{h}_hat"], errors="coerce").to_numpy(dtype=float)
                )
                for y, df in preds.items()
            }
            resid = {y: r[np.isfinite(r)] for y, r in resid.items()}
            for variant, k in variant_specs():
                res = evaluate_variant(variant, fold_year, resid, profiles, preds[fold_year], h, k=k)
                res["domain"] = domain
                res["label"] = label(variant, k)
                res["fold_year"] = fold_year
                got.append(res)
        ck.write_text(json.dumps(got, indent=2, default=str))
        rows.extend(got)
    return rows


def main() -> Path:
    settings = get_settings()
    out_dir = settings.artifacts_dir / "uncertainty"
    ckpt = out_dir / "multiregime_checkpoints"
    ckpt.mkdir(parents=True, exist_ok=True)
    rows = run_for_domain(settings.subset_name, ckpt)
    # Merge any other domain already computed, so the report covers both.
    for other in ckpt.glob("*.json"):
        dom = other.stem.split("_")[0]
        if dom == settings.subset_name:
            continue
        rows.extend(json.loads(other.read_text()))
    path = write_report(rows, out_dir)
    return path


if __name__ == "__main__":
    print(main())
