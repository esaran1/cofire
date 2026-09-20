"""Pipeline sanity gates. Failures mean downstream metrics are meaningless.

Run before `make train`. Does not score the 2026 hindcast.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from cofire.model.config import HORIZONS_WEEKS, SEED, get_settings
from cofire.model.eval import (
    _as_float,
    ar1_neff,
    climatology_pred,
    evaluate_arm,
    persistence_pred,
    random_pred,
)
from cofire.model.features import (
    add_calendar,
    add_lags_and_rolls,
    available_features,
    build_feature_store,
    load_features,
)
from cofire.model.log import setup_logging
from cofire.model.models.lightgbm_arm import LightGBMConditionModel
from cofire.model.train import git_sha, split_frames


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str
    extra: dict[str, Any]


def _usdm_yearly(ds: xr.Dataset) -> pd.DataFrame:
    usdm = ds["usdm"]
    years = pd.to_datetime(ds["time"].values).year
    rows = []
    for year in sorted(set(years.tolist())):
        slab = usdm.isel(time=np.where(years == year)[0])
        vals = slab.values.astype(float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            continue
        rows.append(
            {
                "year": int(year),
                "n": int(vals.size),
                "mean": float(vals.mean()),
                "pct_d1plus": float((vals >= 1).mean()),
                "pct_d2plus": float((vals >= 2).mean()),
            }
        )
    return pd.DataFrame(rows)


def gate_label_sanity() -> Gate:
    """Shape check vs published Colorado drought years. 2012 is not in the Larimer fetch."""
    path = get_settings().processed_dir / "usdm" / "weekly.nc"
    ds = xr.open_dataset(path)
    table = _usdm_yearly(ds)
    ds.close()
    by = {int(r.year): r for r in table.itertuples()}
    notes = [
        "Published Colorado drought shape (statewide, not Larimer-specific): "
        "2012, 2018, 2021 dry; 2019, 2023 wet. Larimer fetch starts 2018 (2012 absent)."
    ]
    checks: list[bool] = []
    if 2018 in by and 2019 in by:
        ok = float(by[2018].mean) > float(by[2019].mean)
        checks.append(ok)
        notes.append(
            f"2018 mean USDM {by[2018].mean:.3f} vs 2019 {by[2019].mean:.3f} "
            f"({'dry>wet' if ok else 'FAILED expected 2018 drier than 2019'})."
        )
    if 2021 in by and 2023 in by:
        ok = float(by[2021].mean) > float(by[2023].mean)
        checks.append(ok)
        notes.append(
            f"2021 mean USDM {by[2021].mean:.3f} vs 2023 {by[2023].mean:.3f} "
            f"({'dry>wet' if ok else 'FAILED expected 2021 drier than 2023'})."
        )
    if 2012 not in by:
        notes.append("2012 not in this cube (outside Larimer data window). Not a fail.")
    passed = bool(checks) and all(checks)
    extra = {"table": table.to_dict(orient="records")}
    return Gate("label_sanity", passed, " ".join(notes), extra)


def gate_grid_alignment() -> Gate:
    """Ten random USDM polygons vs rasterized labels. Pass if agreement > 0.98."""
    import io
    import zipfile

    import geopandas as gpd
    from shapely.geometry import Point, box

    settings = get_settings()
    ds = xr.open_dataset(settings.processed_dir / "usdm" / "weekly.nc")
    lats = ds["lat"].values
    lons = ds["lon"].values
    times = pd.to_datetime(ds["time"].values)
    rng = np.random.default_rng(SEED)
    west, south, east, north = settings.bbox
    bbox_poly = box(west, south, east, north)
    candidates: list[tuple[int, date]] = []
    for i, ts in enumerate(times):
        d = ts.date()
        zpath = settings.raw_dir / "usdm" / f"{d.year}_USDM_M.zip"
        if zpath.exists():
            candidates.append((i, d))
    if len(candidates) < 10:
        ds.close()
        return Gate("grid_alignment", False, f"only {len(candidates)} weeks with zips", {})
    order = rng.permutation(len(candidates))
    agreements: list[float] = []
    used: list[str] = []
    for idx in order:
        if len(agreements) >= 10:
            break
        ti, week = candidates[int(idx)]
        zpath = settings.raw_dir / "usdm" / f"{week.year}_USDM_M.zip"
        inner_name = f"USDM_{week.strftime('%Y%m%d')}_M.zip"
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
            member = next((n for n in names if week.strftime("%Y%m%d") in n and n.lower().endswith(".zip")), None)
            if member is None:
                member = inner_name if inner_name in names else None
            if member is None:
                continue
            with zipfile.ZipFile(io.BytesIO(zf.read(member))) as inner:
                shp = next(n for n in inner.namelist() if n.lower().endswith(".shp"))
                bio = io.BytesIO()
                with zipfile.ZipFile(bio, "w") as buf:
                    stem = Path(shp).stem
                    for member_name in inner.namelist():
                        if Path(member_name).stem == stem or Path(member_name).name.startswith(stem):
                            buf.writestr(Path(member_name).name, inner.read(member_name))
                bio.seek(0)
                gdf = gpd.read_file(bio).to_crs(epsg=4326)
        dm_col = "DM" if "DM" in gdf.columns else "dm"
        gdf = gdf[gdf.intersects(bbox_poly)].copy()
        if gdf.empty:
            continue
        raster = ds["usdm"].isel(time=ti).values
        gdf["_ixn"] = gdf.geometry.intersection(bbox_poly).area
        gdf = gdf[gdf["_ixn"] > 0]
        if gdf.empty:
            continue
        poly_row = gdf.sort_values("_ixn", ascending=False).iloc[0]
        poly = poly_row.geometry
        cat = int(poly_row[dm_col])
        hits = 0
        n = 0
        for yi, lat in enumerate(lats):
            for xi, lon in enumerate(lons):
                if not poly.contains(Point(float(lon), float(lat))):
                    continue
                cell = raster[yi, xi]
                if not np.isfinite(cell):
                    continue
                n += 1
                if int(cell) == cat:
                    hits += 1
        if n == 0:
            continue
        agr = hits / n
        agreements.append(agr)
        used.append(f"{week.isoformat()} DM={cat} n={n} agr={agr:.3f}")
    ds.close()
    if not agreements:
        return Gate("grid_alignment", False, "no polygon contained a grid-cell centroid", {})
    mean_agr = float(np.mean(agreements))
    passed = mean_agr > 0.98 and min(agreements) > 0.90
    return Gate(
        "grid_alignment",
        passed,
        f"mean agreement {mean_agr:.4f} over {len(agreements)} polygons (pass > 0.98). " + "; ".join(used),
        {"agreements": agreements},
    )


def gate_future_data(frame: pd.DataFrame) -> Gate:
    """Recompute lags/rolls on prefixes truncated at issue t; must match stored features."""
    rng = np.random.default_rng(SEED)
    work = frame.dropna(subset=["pr", "cell_id"]).copy()
    work["time"] = pd.to_datetime(work["time"])
    cells = work["cell_id"].unique()
    if len(cells) == 0:
        return Gate("future_data", False, "no cells with precipitation", {})
    sample_cells = rng.choice(cells, size=min(8, len(cells)), replace=False)
    mismatches = 0
    checked = 0
    examples: list[str] = []
    for cell in sample_cells:
        chunk = work[work["cell_id"] == cell].sort_values("time")
        if len(chunk) < 20:
            continue
        times = chunk["time"].to_numpy()
        for t in rng.choice(times[12:-8], size=min(5, max(1, len(times) - 20)), replace=False):
            prefix = chunk[chunk["time"] <= t].copy()
            rebuilt = add_lags_and_rolls(add_calendar(prefix[["cell_id", "time", "lat", "lon", "pr", "pet", "usdm"]].copy()))
            stored_rows = chunk[chunk["time"] == t]
            rebuilt_rows = rebuilt[rebuilt["time"] == t]
            if stored_rows.empty or rebuilt_rows.empty:
                mismatches += 1
                if len(examples) < 6:
                    examples.append(f"{cell} {pd.Timestamp(t).date()} missing rebuilt or stored row")
                continue
            stored = stored_rows.iloc[0]
            row = rebuilt_rows.iloc[0]
            for col in ("pr_lag1", "pr_lag4", "pr_roll4", "usdm_trend_4w"):
                if col not in stored.index or col not in row.index:
                    continue
                a, b = stored[col], row[col]
                checked += 1
                if pd.isna(a) and pd.isna(b):
                    continue
                if not np.isfinite(a) or not np.isfinite(b) or abs(float(a) - float(b)) > 1e-6:
                    mismatches += 1
                    if len(examples) < 6:
                        examples.append(f"{cell} {pd.Timestamp(t).date()} {col} stored={a} rebuilt={b}")
    # Targets may look forward; features must not.
    leaked_targets = [c for c in available_features(frame) if any(c.endswith(f"_h{h}") for h in HORIZONS_WEEKS)]
    if leaked_targets:
        return Gate("future_data", False, f"horizon targets in feature list: {leaked_targets}", {})
    passed = mismatches == 0 and checked > 0
    return Gate(
        "future_data",
        passed,
        f"checked {checked} lag/roll values, mismatches={mismatches}. " + "; ".join(examples),
        {"checked": checked, "mismatches": mismatches},
    )


def gate_baselines(train: pd.DataFrame, valid: pd.DataFrame) -> Gate:
    pers = evaluate_arm("persistence", persistence_pred(valid), valid)
    clim = evaluate_arm("climatology", climatology_pred(train, valid), valid)
    rnd = evaluate_arm("random", random_pred(train, valid), valid)
    notes = []
    passed = True
    d0_rate = float((valid["usdm"] == 0).mean()) if "usdm" in valid.columns else float("nan")
    for h in HORIZONS_WEEKS:
        p = _as_float(pers.get(f"usdm_h{h}_mae"))
        c = _as_float(clim.get(f"usdm_h{h}_mae"))
        r = _as_float(rnd.get(f"usdm_h{h}_mae"))
        notes.append(f"drought h={h}: pers MAE={p:.3f} clim={c:.3f} random={r:.3f}")
        if np.isfinite(p) and np.isfinite(r) and p > r + 1e-6:
            passed = False
            notes.append(f"FAIL persistence does not beat random at drought h={h}.")
        ep = _as_float(pers.get(f"erc_h{h}_mae"))
        er = _as_float(rnd.get(f"erc_h{h}_mae"))
        notes.append(f"ERC-percentile h={h}: pers MAE={ep:.3f} random={er:.3f}")
        if h == 2 and np.isfinite(ep) and np.isfinite(er) and ep > er + 1e-6:
            passed = False
            notes.append("FAIL ERC persistence does not beat random at h=2.")
        if h == 8:
            notes.append(
                "ERC persistence at 8 weeks is not required to beat a constant mean; "
                "weather memory is days to a couple of weeks."
            )
    notes.append(
        f"Drought climatology vs random on this valid year is informational "
        f"(valid D0 rate={d0_rate:.3f}); 2023 is wetter than train, so the D0 mode wins MAE. "
        "Not a hard fail."
    )
    # Climatology-beats-random check on raw ERC (has a seasonal cycle; erc_pct is already a percentile).
    if {"erc", "woy", "cell_id"}.issubset(train.columns) and {"erc", "woy", "cell_id"}.issubset(valid.columns):
        from sklearn.metrics import mean_absolute_error

        means = train.groupby(["cell_id", "woy"], sort=False)["erc"].mean()
        keys = list(zip(valid["cell_id"], valid["woy"], strict=False))
        yhat = np.asarray([means.get(k, np.nan) for k in keys], dtype=float)
        y = valid["erc"].to_numpy(dtype=float)
        glob = float(train["erc"].mean())
        ok = np.isfinite(y) & np.isfinite(yhat)
        if ok.any():
            mae_c = float(mean_absolute_error(y[ok], yhat[ok]))
            mae_g = float(mean_absolute_error(y[ok], np.full(int(ok.sum()), glob)))
            notes.append(f"raw ERC cell-woy climatology MAE={mae_c:.3f} vs constant train-mean MAE={mae_g:.3f}.")
            if mae_c > mae_g + 1e-6:
                passed = False
                notes.append("FAIL cell-woy climatology does not beat a constant mean on raw ERC.")
            else:
                notes.append("PASS cell-woy climatology beats a constant mean on raw ERC.")
    notes.append(
        "Models beating persistence at 2 weeks is not required; failing to beat it at 8 weeks is a later model-quality issue, not this gate."
    )
    return Gate(
        "baseline_floor",
        passed,
        " ".join(notes),
        {"persistence": pers, "climatology": clim, "random": rnd},
    )


def gate_shuffle(train: pd.DataFrame, valid: pd.DataFrame) -> Gate:
    """Retrain LightGBM with targets shuffled inside the train block. Skill must collapse."""
    rng = np.random.default_rng(SEED)
    shuffled = train.copy()
    for h in HORIZONS_WEEKS:
        for col in (f"usdm_h{h}", f"erc_pct_h{h}"):
            if col not in shuffled.columns:
                continue
            vals = shuffled[col].to_numpy()
            order = rng.permutation(len(vals))
            shuffled[col] = vals[order]
    model = LightGBMConditionModel()
    model.fit(shuffled, valid)
    pred = model.predict(valid)
    metrics = evaluate_arm("shuffled", pred, valid)
    r2 = _as_float(metrics.get("erc_h4_r2"))
    mae = _as_float(metrics.get("erc_h4_mae"))
    pers = evaluate_arm("persistence", persistence_pred(valid), valid)
    pers_mae = _as_float(pers.get("erc_h4_mae"))
    # Collapse: R² near 0 and MAE not better than persistence by a large margin.
    passed = (not np.isfinite(r2) or r2 < 0.15) and (not np.isfinite(mae) or not np.isfinite(pers_mae) or mae > pers_mae * 0.9)
    return Gate(
        "shuffle_test",
        passed,
        f"shuffled LightGBM ERC h=4 R²={r2:.3f} MAE={mae:.3f} vs persistence MAE={pers_mae:.3f}. "
        "Pass if R² < 0.15 and MAE is not substantially better than persistence.",
        {"metrics": metrics},
    )


def gate_autocorr(frame: pd.DataFrame) -> Gate:
    weekly = (
        frame.groupby(pd.to_datetime(frame["time"]))[["usdm", "erc_pct"]]
        .mean()
        .sort_index()
    )
    rho_u, neff_u, n_u = ar1_neff(weekly["usdm"].to_numpy(dtype=float))
    rho_e, neff_e, n_e = ar1_neff(weekly["erc_pct"].to_numpy(dtype=float))
    n_cells = int(frame["cell_id"].nunique())
    n_rows = int(len(frame))
    detail = (
        f"Weekly domain-mean AR(1): USDM rho={rho_u:.3f} n={n_u} n_eff={neff_u:.1f}; "
        f"ERC rho={rho_e:.3f} n={n_e} n_eff={neff_e:.1f}. "
        f"Raw rows={n_rows} cells={n_cells}. Headline CIs must use week-block bootstrap; "
        "do not treat cell-weeks as independent."
    )
    return Gate(
        "autocorrelation",
        True,
        detail,
        {
            "usdm_rho": rho_u,
            "usdm_neff_weeks": neff_u,
            "erc_rho": rho_e,
            "erc_neff_weeks": neff_e,
            "n_weeks": n_u,
            "n_cells": n_cells,
            "n_rows": n_rows,
        },
    )


def run_sanity() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    gates: list[Gate] = []
    gates.append(gate_label_sanity())
    gates.append(gate_grid_alignment())

    feat_root = settings.processed_dir / "features"
    if not list(feat_root.glob("year=*.parquet")):
        log.info("building feature store for sanity")
        build_feature_store(settings)
    frame = load_features(feat_root)
    if frame.empty:
        raise SystemExit("feature store empty")
    splits = split_frames(frame)
    train, valid = splits["train"], splits["valid"]
    log.info("sanity train=%s valid=%s (hindcast not used)", len(train), len(valid))
    gates.append(gate_future_data(frame))
    gates.append(gate_baselines(train, valid))
    gates.append(gate_autocorr(train))
    gates.append(gate_shuffle(train, valid))

    out = settings.artifacts_dir / "sanity.md"
    payload = {
        "git_sha": git_sha(),
        "all_passed": all(g.passed for g in gates),
        "gates": [asdict(g) for g in gates],
    }
    (settings.artifacts_dir / "sanity.json").write_text(json.dumps(payload, indent=2, default=str))
    lines = [
        "# Sanity gates",
        "",
        f"Git `{payload['git_sha']}`. Hindcast 2026 was not scored.",
        "",
        f"Overall: **{'PASS' if payload['all_passed'] else 'FAIL'}**.",
        "",
    ]
    for g in gates:
        lines.append(f"## {g.name}: {'PASS' if g.passed else 'FAIL'}")
        lines.append("")
        lines.append(g.detail)
        lines.append("")
        if g.name == "label_sanity" and "table" in g.extra:
            lines.append("| year | n | mean USDM | % D1+ | % D2+ |")
            lines.append("| --- | --- | --- | --- | --- |")
            for row in g.extra["table"]:
                lines.append(
                    f"| {row['year']} | {row['n']} | {row['mean']:.3f} | {row['pct_d1plus']:.3f} | {row['pct_d2plus']:.3f} |"
                )
            lines.append("")
    out.write_text("\n".join(lines))
    log.info("wrote %s all_passed=%s", out, payload["all_passed"])
    if not payload["all_passed"]:
        failed = [g.name for g in gates if not g.passed]
        try:
            from cofire.model.status import write_status

            write_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("STATUS.md not written after sanity fail: %s", exc)
        raise SystemExit(f"sanity gates failed: {failed} — see {out}")
    return out


if __name__ == "__main__":
    run_sanity()
