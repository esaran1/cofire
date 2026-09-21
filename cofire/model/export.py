"""Write COGs, overlay PNGs, and the compact per-cell JSON the API serves."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from cofire.model.config import HORIZONS_WEEKS, get_settings
from cofire.model.explain import GROUP_ORDER, feature_to_group
from cofire.model.log import setup_logging


def _why_fallback(row: pd.Series) -> list[dict[str, object]]:
    """If SHAP cache misses, fall back to signed z-style drivers already on the row — labeled as such."""
    mapping = [
        ("precipitation_deficit", "precipitation deficit", -float(row.get("spi_90", 0) or 0), "spi_90"),
        ("snowpack", "snowpack", -((float(row.get("swe_pct_median", 100) or 100) - 100) / 50.0), "swe_pct_median"),
        ("soil_dryness", "soil dryness", -float(row.get("fm1000_anom", 0) or 0), "fm1000_anom"),
        ("vegetation_fuel_dryness", "vegetation and fuel dryness", (float(row.get("erc_pct", 50) or 50) - 50) / 50.0, "erc_pct"),
        ("heat", "heat", float(row.get("tmmx_anom", 0) or 0), "tmmx_anom"),
    ]
    mag = sum(abs(v[2]) for v in mapping) or 1.0
    from cofire.model.explain import TEMPLATES

    bars = []
    for group, label, raw, feat in mapping:
        val = raw / mag
        polarity = "pos" if val >= 0 else "neg"
        bars.append(
            {
                "group": group,
                "label": label,
                "value": val,
                "raw": raw,
                "top_feature": feat,
                "text": TEMPLATES[group][polarity],
                "sign": polarity,
                "source": "feature-z (SHAP cache miss)",
            }
        )
    return bars


def run_export() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    arm = (settings.artifacts_dir / "shipping_arm.txt").read_text().strip() if (settings.artifacts_dir / "shipping_arm.txt").exists() else "lightgbm"
    pred_dir = settings.artifacts_dir / "predictions"
    # Prefer the scoring-free 2026 forecasts (cofire.model.forecast_issues): they
    # carry intervals from the frozen calibrate pool and cost no holdout look.
    # Fall back to the scored hindcast intervals only if that stage has not run.
    path = pred_dir / f"{arm}_forecast_issues.parquet"
    if not path.exists():
        path = pred_dir / f"{arm}_hindcast_intervals.parquet"
    if not path.exists():
        path = pred_dir / f"{arm}_hindcast.parquet"
    cal = pred_dir / f"{arm}_calibrate_intervals.parquet"
    frames = []
    for p in (path, cal, pred_dir / f"{arm}_valid.parquet"):
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        raise SystemExit("no predictions to export")

    # Drop any frame whose cells sit outside the active domain. The hindcast
    # intervals parquet is written only by hindcast.py, which costs a holdout
    # look, so after a subset move it can legitimately be stale. Mixing its
    # cells with fresh ones silently produces a two-domain index and a map
    # pointed at the wrong place, which is worse than exporting without it.
    west, south, east, north = settings.bbox
    kept = []
    for f in frames:
        if "lat" not in f.columns or f.empty:
            continue
        inside = ((f["lat"] >= south) & (f["lat"] <= north) & (f["lon"] >= west) & (f["lon"] <= east)).mean()
        if inside < 0.5:
            log.warning(
                "export: dropping %s rows outside the %s bbox (%.0f%% inside); "
                "re-run that stage for this subset",
                len(f),
                settings.subset_name,
                inside * 100,
            )
            continue
        kept.append(f)
    if not kept:
        raise SystemExit("no predictions inside the active bbox - re-run train/calibrate for this subset")
    frame = pd.concat(kept, ignore_index=True)
    frame["time"] = pd.to_datetime(frame["time"])

    why_path = settings.artifacts_dir / "why.json"
    why_lookup: dict[tuple[str, str], list[dict[str, object]]] = {}
    shap_src = pred_dir / "lightgbm_hindcast.parquet"
    if shap_src.exists() and (settings.artifacts_dir / "models" / "lightgbm").exists():
        try:
            from cofire.model.explain import cache_why
            from cofire.model.models.lightgbm_arm import LightGBMConditionModel

            lgbm = LightGBMConditionModel.load(settings.artifacts_dir / "models" / "lightgbm")
            booster = lgbm.models.get("erc_pct_h4")
            if booster is not None:
                src = pd.read_parquet(shap_src)
                cache_why(booster, src, why_path, sample=min(400, len(src)))
        except Exception as exc:  # noqa: BLE001
            log.warning("SHAP cache skipped: %s", exc)
    if why_path.exists():
        for rec in json.loads(why_path.read_text()):
            why_lookup[(rec["cell_id"], rec["time"])] = rec["bars"]

    mapping = feature_to_group()
    # Targets with zero LODO resolution in THIS domain. Domain dependent: 8 on
    # Larimer against 4 on Pueblo, so it is read rather than hard-coded.
    flat_targets: set[str] = set()
    _flat_path = Path("artifacts/shipping/flat_targets.json")
    if _flat_path.exists():
        try:
            flat_targets = set(json.loads(_flat_path.read_text()).get(settings.subset_name, []))
        except (json.JSONDecodeError, OSError):
            flat_targets = set()

    cells: list[dict[str, object]] = []
    for (cell_id, t), chunk in frame.groupby(["cell_id", "time"]):
        row = chunk.iloc[0]
        issue = str(pd.Timestamp(t).date())
        why = why_lookup.get((str(cell_id), issue))
        if why is None:
            why = _why_fallback(row)
        entry: dict[str, object] = {
            "cell_id": str(cell_id),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "issue": issue,
            "resolution_m": 30 if settings.enable_hls else 4000,
            "shipping_arm": arm,
            "why": why,
            "horizons": {},
        }
        for h in HORIZONS_WEEKS:
            fire = float(row.get(f"erc_pct_h{h}_hat", np.nan))
            bi = float(row.get("bi_pct", np.nan))
            fire_index = float(np.nanmean([fire, bi])) if np.isfinite(bi) else fire
            entry["horizons"][str(h)] = {  # type: ignore[index]
                "drought_point": _finite(row.get(f"usdm_h{h}_hat")),
                "drought_set": row.get(f"usdm_h{h}_set") if isinstance(row.get(f"usdm_h{h}_set"), list) else [],
                "fire_index": fire_index,
                "fire_lo": _finite(row.get(f"erc_pct_h{h}_lo")),
                "fire_hi": _finite(row.get(f"erc_pct_h{h}_hi")),
                "confidence": _finite(row.get(f"erc_pct_h{h}_conf"), 0.5),
                "alpha": _finite(row.get(f"erc_pct_h{h}_alpha"), 0.1),
                # v1 probabilistic targets, each carrying its own baseline so
                # the card can show the model beside the reference rather than
                # in place of it. `baseline` is null for fire, which has no
                # Markov reference: a USDM category transition matrix cannot
                # forecast ERC exceedance. See docs/DECISIONS.md.
                "p_intensify": {
                    "value": _finite(row.get(f"d_intensify1_h{h}_hat")),
                    "baseline": _finite(row.get(f"d_intensify1_h{h}_markov")),
                    "flat": f"d_intensify1_h{h}" in flat_targets,
                },
                "p_d2plus": {
                    "value": _finite(row.get(f"d_ge2_h{h}_hat")),
                    "baseline": _finite(row.get(f"d_ge2_h{h}_markov")),
                    "flat": f"d_ge2_h{h}" in flat_targets,
                },
                "p_fire_gt90": {
                    "value": _finite(row.get(f"f_gt90_h{h}_hat")),
                    "baseline": None,
                    "flat": f"f_gt90_h{h}" in flat_targets,
                },
            }
        cells.append(entry)

    index_path = settings.artifacts_dir / "forecast_index.json"
    issues = sorted({str(c["issue"]) for c in cells})
    payload = {
        "resolution_m": 30 if settings.enable_hls else 4000,
        "resolution_note": "gridMET native ~4 km cells. Downscaling to 10–30 m is off."
        if not settings.enable_hls
        else "HLS/Sentinel-2 downscaling is on; confirm the layer actually loaded.",
        "shipping_arm": arm,
        "issues": issues,
        "cells": cells,
    }
    index_path.write_text(json.dumps(payload, default=_json_default))
    _write_overlays(frame, settings.artifacts_dir / "overlays")
    log.info("export cells=%s issues=%s -> %s", len(cells), len(issues), index_path)
    _ = mapping, GROUP_ORDER
    return index_path


def _finite(val: object, default: float | None = None) -> float | None:
    try:
        x = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return x if np.isfinite(x) else default


def _json_default(obj: object) -> object:
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def _write_overlays(frame: pd.DataFrame, root: Path) -> None:
    """Coarse PNG per issue/horizon/variable for MapLibre image source."""
    root.mkdir(parents=True, exist_ok=True)
    if frame.empty:
        return
    lats = np.sort(frame["lat"].unique())[::-1]
    lons = np.sort(frame["lon"].unique())
    for issue, chunk in frame.groupby(pd.to_datetime(frame["time"]).dt.date):
        for h in HORIZONS_WEEKS:
            for var, col, _cmap in (
                ("drought", f"usdm_h{h}_hat", "YlOrBr"),
                ("fire", f"erc_pct_h{h}_hat", "YlOrRd"),
            ):
                if col not in chunk.columns:
                    continue
                grid = np.full((len(lats), len(lons)), np.nan)
                lat_i = {float(v): i for i, v in enumerate(lats)}
                lon_i = {float(v): i for i, v in enumerate(lons)}
                for row in chunk.itertuples():
                    yi, xi = lat_i.get(float(row.lat)), lon_i.get(float(row.lon))
                    if yi is None or xi is None:
                        continue
                    grid[yi, xi] = float(getattr(row, col, np.nan))
                png = _colorize(grid, var)
                dest = root / f"{issue}_{h}_{var}.png"
                Image.fromarray(png).save(dest)
                bounds = {
                    "west": float(lons.min()),
                    "south": float(lats.min()),
                    "east": float(lons.max()),
                    "north": float(lats.max()),
                }
                dest.with_suffix(".json").write_text(json.dumps(bounds))


def _colorize(grid: np.ndarray, var: str) -> np.ndarray:
    h, w = grid.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    if var == "drought":
        # 0–4 → yellow-brown
        v = np.clip(np.nan_to_num(grid, nan=-1), 0, 4) / 4.0
        rgba[..., 0] = (230 + 25 * v).astype(np.uint8)
        rgba[..., 1] = (193 - 80 * v).astype(np.uint8)
        rgba[..., 2] = (92 - 40 * v).astype(np.uint8)
        rgba[..., 3] = np.where(np.isfinite(grid), 180, 0).astype(np.uint8)
    else:
        v = np.clip(np.nan_to_num(grid, nan=0), 0, 100) / 100.0
        rgba[..., 0] = np.uint8(255)
        rgba[..., 1] = (90 + 80 * (1 - v)).astype(np.uint8)
        rgba[..., 2] = np.uint8(42)
        rgba[..., 3] = np.where(np.isfinite(grid), (80 + 140 * v).astype(np.uint8), 0)
    # nearest-neighbor upscale so 4 km cells are visible
    img = Image.fromarray(rgba, mode="RGBA").resize((max(w * 8, 8), max(h * 8, 8)), Image.Resampling.NEAREST)
    return np.asarray(img)


if __name__ == "__main__":
    run_export()
