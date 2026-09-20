"""Train all arms, baselines, ablations. INTENDED FOR HAND-REWRITE.

Time-blocked splits only. No random row splits. Three PI-ConvLSTM configs
(no penalties, hydro only, both). Shipping arm = best validation ERC MAE.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error, r2_score

from cofire.model.config import HORIZONS_WEEKS, SEED, get_settings
from cofire.model.explain import GROUP_ORDER, load_groups
from cofire.model.features import available_features, build_feature_store, load_features
from cofire.model.log import setup_logging
from cofire.model.models import ConditionModel
from cofire.model.models.ensemble import EnsembleModel
from cofire.model.models.external import ExternalDroughtModel
from cofire.model.models.lightgbm_arm import LightGBMConditionModel
from cofire.model.models.pi_convlstm import PhysicsInformedConvLSTM


def _as_float(value: object, default: float = float("nan")) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


np.random.seed(SEED)


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "uncommitted"


def split_frames(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    settings = get_settings()
    t = pd.to_datetime(frame["time"])
    return {
        "train": frame[t <= pd.Timestamp(settings.train_end)].copy(),
        "valid": frame[(t >= pd.Timestamp(settings.valid_start)) & (t <= pd.Timestamp(settings.valid_end))].copy(),
        "calibrate": frame[
            (t >= pd.Timestamp(settings.calibrate_start)) & (t <= pd.Timestamp(settings.calibrate_end))
        ].copy(),
        "hindcast": frame[t >= pd.Timestamp(settings.hindcast_start)].copy(),
    }


def persistence(frame: pd.DataFrame, h: int) -> pd.Series:
    return frame["usdm"] if "usdm" in frame.columns else pd.Series(np.nan, index=frame.index)


def climatology(train: pd.DataFrame, frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in train.columns or "woy" not in train.columns:
        return pd.Series(np.nan, index=frame.index)
    means = train.groupby(["cell_id", "woy"])[col].mean()
    keys = list(zip(frame["cell_id"], frame["woy"], strict=False))
    return pd.Series([means.get(k, np.nan) for k in keys], index=frame.index)


def persistence_plus_trend(frame: pd.DataFrame, col: str) -> pd.Series:
    g = frame.sort_values(["cell_id", "time"]).groupby("cell_id")[col]
    prev = g.shift(1)
    cur = frame[col]
    return cur + (cur - prev)


def skill_vs_persistence(mae_model: float, mae_pers: float) -> float:
    if not np.isfinite(mae_pers) or mae_pers == 0:
        return float("nan")
    return float(1.0 - mae_model / mae_pers)


def evaluate_arm(name: str, pred: pd.DataFrame, truth: pd.DataFrame) -> dict[str, object]:
    merged = truth.join(pred, how="left")
    out: dict[str, object] = {"arm": name}
    for h in HORIZONS_WEEKS:
        if f"usdm_h{h}" in merged and f"usdm_h{h}_hat" in merged:
            y = merged[f"usdm_h{h}"].to_numpy(dtype=float)
            yhat = merged[f"usdm_h{h}_hat"].to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(yhat)
            out[f"usdm_h{h}_mae"] = float(mean_absolute_error(y[ok], yhat[ok])) if ok.any() else float("nan")
            out[f"usdm_h{h}_acc"] = float(np.mean(np.round(yhat[ok]) == y[ok])) if ok.any() else float("nan")
        if f"erc_pct_h{h}" in merged and f"erc_pct_h{h}_hat" in merged:
            y = merged[f"erc_pct_h{h}"].to_numpy(dtype=float)
            yhat = merged[f"erc_pct_h{h}_hat"].to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(yhat)
            out[f"erc_h{h}_mae"] = float(mean_absolute_error(y[ok], yhat[ok])) if ok.any() else float("nan")
            out[f"erc_h{h}_r2"] = float(r2_score(y[ok], yhat[ok])) if ok.sum() > 2 else float("nan")
        ge_col = f"usdm_ge2_h{h}_hat"
        if ge_col in merged and f"usdm_h{h}" in merged:
            y = (merged[f"usdm_h{h}"] >= 2).astype(float)
            p = merged[ge_col].clip(0, 1)
            ok = y.notna() & p.notna()
            out[f"usdm_h{h}_brier_ge2"] = (
                float(brier_score_loss(y[ok], p[ok])) if ok.any() else float("nan")
            )
    return out


def group_ablation(train: pd.DataFrame, valid: pd.DataFrame) -> list[dict[str, object]]:
    """Retrain LightGBM with each SHAP group dropped; delta vs full on validation."""
    groups = load_groups()
    full = LightGBMConditionModel()
    full.fit(train, valid)
    full_pred = full.predict(valid)
    full_metrics = evaluate_arm("full", full_pred, valid)
    rows = [{"group": "none (full)", **{k: v for k, v in full_metrics.items() if k != "arm"}}]
    base_mae = _as_float(full_metrics.get("erc_h4_mae"))
    for group in GROUP_ORDER:
        dropped = set(groups.get(group, []))
        slim = train.drop(columns=[c for c in dropped if c in train.columns])
        slim_v = valid.drop(columns=[c for c in dropped if c in valid.columns])
        model = LightGBMConditionModel()
        model.fit(slim, slim_v)
        metrics = evaluate_arm(f"drop_{group}", model.predict(slim_v), slim_v)
        mae = _as_float(metrics.get("erc_h4_mae"))
        rows.append(
            {
                "group": group,
                "erc_h4_mae": mae,
                "delta_erc_h4_mae": mae - base_mae if np.isfinite(mae) and np.isfinite(base_mae) else float("nan"),
            }
        )
    return rows


def pick_shipping(val_metrics: list[dict[str, object]]) -> str:
    def key(m: dict[str, object]) -> tuple[float, float]:
        e = _as_float(m.get("erc_h4_mae"), 1e9)
        u = _as_float(m.get("usdm_h4_mae"), 1e9)
        return (e, u)

    eligible = [m for m in val_metrics if m["arm"] in {"lightgbm", "pi_convlstm_both", "ensemble"}]
    if not eligible:
        eligible = val_metrics
    return str(min(eligible, key=key)["arm"])


def run_train() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    feat_root = settings.processed_dir / "features"
    if not list(feat_root.glob("year=*.parquet")):
        log.info("building feature store")
        build_feature_store(settings)
    frame = load_features(feat_root)
    if frame.empty:
        raise SystemExit("feature store is empty — run `make data`")
    splits = split_frames(frame)
    train, valid = splits["train"], splits["valid"]
    log.info("train rows=%s valid=%s", len(train), len(valid))

    ext = ExternalDroughtModel()
    if ext.available:
        train = train.copy()
        valid = valid.copy()
        train["external_drought"] = ext.as_feature(train)
        valid["external_drought"] = ext.as_feature(valid)

    lgbm = LightGBMConditionModel()
    lgbm.fit(train, valid)
    lgbm.save(settings.artifacts_dir / "models" / "lightgbm")

    pi_configs = [
        ("pi_convlstm_none", 0.0, 0.0),
        ("pi_convlstm_hydro", settings.lambda_hydro, 0.0),
        ("pi_convlstm_both", settings.lambda_hydro, settings.lambda_fuel),
    ]
    pi_models: dict[str, PhysicsInformedConvLSTM] = {}
    for name, lh, lf in pi_configs:
        log.info("training %s", name)
        model = PhysicsInformedConvLSTM(lambda_hydro=lh, lambda_fuel=lf, max_epochs=8)
        model.fit(train, valid)
        model.save(settings.artifacts_dir / "models" / name)
        pi_models[name] = model

    members = {"lightgbm": lgbm, "pi_convlstm_both": pi_models["pi_convlstm_both"]}
    if ext.available:
        members["external_drought"] = ext
    lgbm_val = evaluate_arm("lightgbm", lgbm.predict(valid), valid)
    pi_val = evaluate_arm("pi_convlstm_both", pi_models["pi_convlstm_both"].predict(valid), valid)
    w_lgb = 1.0 / max(_as_float(lgbm_val.get("erc_h4_mae"), 1.0) or 1.0, 1e-3)
    w_pi = 1.0 / max(_as_float(pi_val.get("erc_h4_mae"), 1.0) or 1.0, 1e-3)
    weights = {"lightgbm": w_lgb, "pi_convlstm_both": w_pi}
    if ext.available:
        weights["external_drought"] = min(w_lgb, w_pi) * 0.25
    ensemble = EnsembleModel(members, weights)

    val_metrics = [
        lgbm_val,
        evaluate_arm("pi_convlstm_none", pi_models["pi_convlstm_none"].predict(valid), valid),
        evaluate_arm("pi_convlstm_hydro", pi_models["pi_convlstm_hydro"].predict(valid), valid),
        pi_val,
        evaluate_arm("ensemble", ensemble.predict(valid), valid),
    ]
    # Baselines on drought / ERC at h=4.
    pers = persistence(valid, 4)
    clim = climatology(train, valid, "erc_pct")
    if "usdm_h4" in valid.columns:
        ok = valid["usdm_h4"].notna() & pers.notna()
        if ok.any():
            val_metrics.append(
                {
                    "arm": "persistence",
                    "usdm_h4_mae": float(mean_absolute_error(valid.loc[ok, "usdm_h4"], pers[ok])),
                }
            )
    if "erc_pct_h4" in valid.columns and clim.notna().any():
        ok = valid["erc_pct_h4"].notna() & clim.notna()
        if ok.any():
            val_metrics.append(
                {
                    "arm": "climatology",
                    "erc_h4_mae": float(mean_absolute_error(valid.loc[ok, "erc_pct_h4"], clim[ok])),
                }
            )
    if "erc_pct" in valid.columns and "erc_pct_h4" in valid.columns:
        ppt = persistence_plus_trend(valid, "erc_pct")
        ok = valid["erc_pct_h4"].notna() & ppt.notna()
        if ok.any():
            val_metrics.append(
                {
                    "arm": "persistence_plus_trend",
                    "erc_h4_mae": float(mean_absolute_error(valid.loc[ok, "erc_pct_h4"], ppt[ok])),
                }
            )

    shipping = pick_shipping(val_metrics)
    ablation = group_ablation(train, valid)

    pred_dir = settings.artifacts_dir / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    arm_predictors: dict[str, ConditionModel] = {
        "lightgbm": lgbm,
        "pi_convlstm_none": pi_models["pi_convlstm_none"],
        "pi_convlstm_hydro": pi_models["pi_convlstm_hydro"],
        "pi_convlstm_both": pi_models["pi_convlstm_both"],
        "ensemble": ensemble,
    }
    for split_name, split in splits.items():
        for arm_name, predictor in arm_predictors.items():
            pred = predictor.predict(split)
            merged = split.reset_index(drop=True).join(pred.reset_index(drop=True))
            merged.to_parquet(pred_dir / f"{arm_name}_{split_name}.parquet", index=False)

    manifest_hash = ""
    man = settings.data_dir / "MANIFEST.json"
    if man.exists():
        payload = json.loads(man.read_text())
        manifest_hash = str(payload.get("hash", ""))

    metrics = {
        "git_sha": git_sha(),
        "manifest_hash": manifest_hash,
        "shipping_arm": shipping,
        "validation": val_metrics,
        "ablation": ablation,
        "pi_coeffs": {k: v.extra() for k, v in pi_models.items()},
        "ensemble_weights": weights,
        "features": available_features(train),
        "n_train": int(len(train)),
        "n_valid": int(len(valid)),
        "resolution_m": 30 if settings.enable_hls else 4000,
    }
    (settings.artifacts_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    (settings.artifacts_dir / "shipping_arm.txt").write_text(shipping)
    (settings.artifacts_dir / "metrics.md").write_text(_metrics_md(metrics))
    log.info("shipping arm=%s", shipping)
    return settings.artifacts_dir / "metrics.md"


def _metrics_md(metrics: dict[str, object]) -> str:
    lines = [
        "# COFIRE metrics",
        "",
        "These models forecast **drought severity** and **conditions that allow fires to spread** (ERC percentile / fire-spread condition index). They do not forecast ignitions.",
        "",
        f"Shipping arm: **{metrics['shipping_arm']}** (best validation ERC-percentile MAE).",
        f"Git: `{metrics['git_sha']}`  MANIFEST: `{metrics['manifest_hash']}`",
        f"Displayed resolution: {metrics['resolution_m']} m (gridMET native 4 km unless HLS is on and loaded).",
        "",
        "## Validation",
        "",
        "| arm | ERC h=4 MAE | drought h=4 MAE | drought h=4 exact acc |",
        "| --- | --- | --- | --- |",
    ]
    val_rows = metrics.get("validation")
    if isinstance(val_rows, list):
        for row in val_rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| {row.get('arm')} | {row.get('erc_h4_mae', '')} | {row.get('usdm_h4_mae', '')} | {row.get('usdm_h4_acc', '')} |"
            )
    lines += ["", "## Feature-group ablation (LightGBM, validation ERC h=4)", "", "| group dropped | MAE | delta vs full |", "| --- | --- | --- |"]
    abl_rows = metrics.get("ablation")
    if isinstance(abl_rows, list):
        for row in abl_rows:
            if not isinstance(row, dict):
                continue
            lines.append(f"| {row.get('group')} | {row.get('erc_h4_mae', '')} | {row.get('delta_erc_h4_mae', '')} |")
    lines += [
        "",
        "## PI-ConvLSTM penalties",
        "",
        "`k` and `f(vpd, precip_28d)` are fit on the training split only. λ_hydro = λ_fuel = 0.1 a priori; not searched on val or hindcast.",
        "Configs: no penalties, hydro only, both.",
        "",
    ]
    by_arm: dict[str, dict[str, object]] = {}
    if isinstance(val_rows, list):
        for row in val_rows:
            if isinstance(row, dict) and isinstance(row.get("arm"), str):
                by_arm[str(row["arm"])] = row
    none_mae = _as_float((by_arm.get("pi_convlstm_none") or {}).get("erc_h4_mae"))
    hydro_mae = _as_float((by_arm.get("pi_convlstm_hydro") or {}).get("erc_h4_mae"))
    both_mae = _as_float((by_arm.get("pi_convlstm_both") or {}).get("erc_h4_mae"))
    if np.isfinite(none_mae) and np.isfinite(hydro_mae):
        if hydro_mae < none_mae:
            lines.append(
                f"L_hydro improved validation ERC h=4 MAE ({hydro_mae:.3f} vs {none_mae:.3f} with no penalties)."
            )
        else:
            lines.append(
                f"L_hydro did not improve validation ERC h=4 MAE ({hydro_mae:.3f} vs {none_mae:.3f} with no penalties)."
            )
    if np.isfinite(hydro_mae) and np.isfinite(both_mae):
        if both_mae < hydro_mae:
            lines.append(
                f"L_fuel on top of L_hydro improved validation ERC h=4 MAE ({both_mae:.3f} vs {hydro_mae:.3f} hydro-only)."
            )
        else:
            lines.append(
                f"L_fuel on top of L_hydro did not improve validation ERC h=4 MAE ({both_mae:.3f} vs {hydro_mae:.3f} hydro-only)."
            )
    if np.isfinite(none_mae) and np.isfinite(both_mae):
        if both_mae < none_mae:
            lines.append(
                f"Both penalties together beat no-penalty ({both_mae:.3f} vs {none_mae:.3f})."
            )
        else:
            lines.append(
                f"Both penalties together did not beat no-penalty ({both_mae:.3f} vs {none_mae:.3f})."
            )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    run_train()
