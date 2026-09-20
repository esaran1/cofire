"""Hindcast 2026: first look at the locked holdout after hyperparameters are frozen."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cofire.model.config import HORIZONS_WEEKS, get_settings
from cofire.model.conformal import ConformalCalibrator, attach_intervals
from cofire.model.eval import (
    attach_skills,
    climatology_pred,
    evaluate_arm,
    format_skill_sentence,
    persistence_pred,
)
from cofire.model.features import load_features
from cofire.model.log import setup_logging
from cofire.model.train import git_sha, split_frames
from cofire.model.uncertainty import write_comparison
from cofire.model.uncertainty.bootstrap import attach_bootstrap, load_bootstrap

MAY1_ISSUE = date(2026, 5, 5)


class CutoffError(RuntimeError):
    """Raised when a feature row is later than the forecast issue date."""


def assert_cutoff(frame: pd.DataFrame, issue: date) -> None:
    times = pd.to_datetime(frame["time"])
    if (times > pd.Timestamp(issue)).any():
        bad = times[times > pd.Timestamp(issue)].max()
        raise CutoffError(f"issue {issue} saw future timestamp {bad.date()}")


def config_hash(settings_blob: dict[str, object]) -> str:
    raw = json.dumps(settings_blob, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def append_run_log(path: Path, sha: str, cfg: str) -> int:
    """Append one hindcast evaluation. Returns how many looks this config has had."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    if path.exists():
        records = json.loads(path.read_text())
        if not isinstance(records, list):
            records = []
    look_index = sum(1 for r in records if isinstance(r, dict) and r.get("config_hash") == cfg) + 1
    rec = {
        "git_sha": sha,
        "config_hash": cfg,
        "timestamp": datetime.now(UTC).isoformat(),
        "look_index": look_index,
    }
    records.append(rec)
    path.write_text(json.dumps(records, indent=2))
    return look_index


def _percentile_rank(value: float, dist: np.ndarray) -> float:
    dist = dist[np.isfinite(dist)]
    if dist.size == 0 or not np.isfinite(value):
        return float("nan")
    return float(100.0 * (dist <= value).mean())


def _bbox_contains(lat: float, lon: float) -> bool:
    west, south, east, north = get_settings().bbox
    return south <= lat <= north and west <= lon <= east


def run_hindcast() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    arm = (
        (settings.artifacts_dir / "shipping_arm.txt").read_text().strip()
        if (settings.artifacts_dir / "shipping_arm.txt").exists()
        else "lightgbm"
    )
    pred_dir = settings.artifacts_dir / "predictions"
    pred_path = pred_dir / f"{arm}_hindcast.parquet"
    if not pred_path.exists():
        raise SystemExit("no hindcast predictions — run `make train calibrate`")
    frame = pd.read_parquet(pred_path)
    frame["time"] = pd.to_datetime(frame["time"])
    for issue, chunk in frame.groupby(frame["time"].dt.date):
        assert_cutoff(chunk, issue)

    metrics_path = settings.artifacts_dir / "metrics.json"
    frozen = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    cfg = config_hash(
        {
            "shipping_arm": arm,
            "lambda_hydro": settings.lambda_hydro,
            "lambda_fuel": settings.lambda_fuel,
            "seed": settings.seed,
            "splits": [str(settings.valid_start), str(settings.valid_end)],
            "max_epochs_pi": 8,
            "lgbm_leaves": 31,
        }
    )
    log_path = settings.artifacts_dir / "hindcast" / "run_log.json"
    n_looks = append_run_log(log_path, git_sha(), cfg)
    assert log_path.exists(), "hindcast run_log.json was not written"
    assert n_looks >= 1
    log.info("hindcast look #%s for config %s", n_looks, cfg)
    if n_looks > 1:
        log.warning("repeated hindcast peek for this config — recorded in run_log.json")

    cal_path = settings.artifacts_dir / "calibration"
    conformal = ConformalCalibrator.load(cal_path)
    boot = load_bootstrap(cal_path)
    hc_conf = attach_intervals(frame, conformal, update_aci=True)
    hc_boot = attach_bootstrap(frame, boot, arm)
    hc_conf.to_parquet(pred_dir / f"{arm}_hindcast_intervals.parquet", index=False)

    cal_conf = pd.read_parquet(pred_dir / f"{arm}_calibrate_intervals.parquet")
    cal_boot = attach_bootstrap(_load_cal(pred_dir, arm), boot, arm)
    write_comparison(
        cal_conf,
        cal_boot,
        hc_conf,
        hc_boot,
        settings.artifacts_dir / "uncertainty",
    )

    out = settings.artifacts_dir / "hindcast"
    out.mkdir(parents=True, exist_ok=True)
    if "erc_pct_h4_lo" in hc_conf.columns:
        recs = []
        for t, g in hc_conf.groupby("time"):
            y = g["erc_pct_h4"].to_numpy(dtype=float) if "erc_pct_h4" in g else np.array([])
            lo = g["erc_pct_h4_lo"].to_numpy(dtype=float)
            hi = g["erc_pct_h4_hi"].to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(lo) & np.isfinite(hi)
            recs.append(
                {
                    "time": t,
                    "coverage": float(np.mean((y[ok] >= lo[ok]) & (y[ok] <= hi[ok]))) if ok.any() else np.nan,
                }
            )
        cov = pd.DataFrame(recs)
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(cov["time"], cov["coverage"], color="#e6c15c")
        ax.axhline(0.90, color="white", linestyle="--", linewidth=1)
        ax.set_title("Hindcast conformal coverage, 4-week ERC percentile")
        fig.tight_layout()
        fig.savefig(out / "coverage.png", dpi=140, facecolor="#0c0e12")
        plt.close(fig)

    fire_rows, control = _score_fires(hc_conf)
    pd.DataFrame(fire_rows).to_json(out / "fires.json", orient="records")
    (out / "control.json").write_text(json.dumps(control, indent=2, default=str))
    (out / "fires.md").write_text(_fires_md(fire_rows, control))

    _append_hindcast_metrics(frozen, arm, hc_conf, out, pred_dir)
    log.info("hindcast fires=%s in_domain=%s", len(fire_rows), sum(1 for r in fire_rows if r.get("in_domain")))
    return out


def _load_cal(pred_dir: Path, arm: str) -> pd.DataFrame:
    path = pred_dir / f"{arm}_calibrate.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def _score_fires(frame: pd.DataFrame) -> tuple[list[dict[str, object]], dict[str, object]]:
    from cofire.model.dates import previous_tuesday

    settings = get_settings()
    fires_path = settings.processed_dir / "nifc" / "perimeters_2026.geojson"
    fire_rows: list[dict[str, object]] = []
    if not fires_path.exists():
        return fire_rows, {"n": 0}
    import geopandas as gpd

    fires = gpd.read_file(fires_path)
    rng = np.random.default_rng(2026)
    for _, fire in fires.iterrows():
        disc = _discovery_date(fire)
        if disc is None:
            continue
        geom = fire.geometry
        if geom is None or geom.is_empty:
            continue
        lon, lat = float(geom.centroid.x), float(geom.centroid.y)
        name = str(fire.get("poly_IncidentName") or fire.get("INCIDENTNAME") or fire.get("FIRENAME") or "unnamed")
        acres = fire.get("poly_GISAcres") or fire.get("GISACRES") or fire.get("GISAcres")
        try:
            acres_f = float(acres) if acres is not None else float("nan")
        except (TypeError, ValueError):
            acres_f = float("nan")
        if np.isfinite(acres_f) and acres_f < 1000:
            continue
        rec: dict[str, object] = {
            "name": name,
            "discovery": disc.isoformat(),
            "lat": lat,
            "lon": lon,
            "acres": acres_f,
            "in_domain": _bbox_contains(lat, lon),
        }
        for h in HORIZONS_WEEKS:
            issue = disc - timedelta(days=7 * h)
            issue_t = previous_tuesday(issue)
            snap = frame[frame["time"] == pd.Timestamp(issue_t)]
            if snap.empty:
                rec[f"h{h}_fire_index"] = None
                rec[f"h{h}_pct_rank"] = None
                continue
            cell = _nearest(snap, lat, lon)
            fi = float(cell.get(f"erc_pct_h{h}_hat", np.nan))
            dist = snap[f"erc_pct_h{h}_hat"].to_numpy(dtype=float) if f"erc_pct_h{h}_hat" in snap else np.array([])
            rec[f"h{h}_fire_index"] = fi
            rec[f"h{h}_pct_rank"] = _percentile_rank(fi, dist)
            rec[f"h{h}_usdm"] = float(cell.get(f"usdm_h{h}_hat", np.nan))
            rec[f"h{h}_issue"] = issue_t.isoformat()
        fire_rows.append(rec)

    # 200 random non-fire cells, matched by the issue dates used above.
    issues = sorted(
        {
            str(r.get(f"h{h}_issue"))
            for r in fire_rows
            for h in HORIZONS_WEEKS
            if r.get(f"h{h}_issue") is not None
        }
    )
    fire_cells = {
        (round(float(r["lat"]), 4), round(float(r["lon"]), 4))
        for r in fire_rows
        if r.get("in_domain") and isinstance(r["lat"], (int, float)) and isinstance(r["lon"], (int, float))
    }
    control_ranks: dict[str, list[float]] = {f"h{h}": [] for h in HORIZONS_WEEKS}
    if issues:
        sample_issue = str(issues[0])
        snap = frame[frame["time"] == pd.Timestamp(sample_issue)]
        pool = snap.copy()
        if fire_cells:
            mask = [
                (round(float(a), 4), round(float(b), 4)) not in fire_cells
                for a, b in zip(pool["lat"], pool["lon"], strict=False)
            ]
            pool = pool.loc[mask]
        n = min(200, len(pool))
        if n:
            take = pool.sample(n=n, random_state=int(rng.integers(0, 2_000_000_000)))
            for h in HORIZONS_WEEKS:
                for issue_s in issues:
                    snap_i = frame[frame["time"] == pd.Timestamp(issue_s)]
                    if snap_i.empty or f"erc_pct_h{h}_hat" not in snap_i:
                        continue
                    dist = snap_i[f"erc_pct_h{h}_hat"].to_numpy(dtype=float)
                    for _, row in take.iterrows():
                        cell = _nearest(snap_i, float(row["lat"]), float(row["lon"]))
                        fi = float(cell.get(f"erc_pct_h{h}_hat", np.nan))
                        control_ranks[f"h{h}"].append(_percentile_rank(fi, dist))
    control = {
        "n": 200,
        "mean_pct_rank": {k: float(np.nanmean(v)) if v else float("nan") for k, v in control_ranks.items()},
        "note": "Random non-fire cells in the current domain, matched to fire issue dates. Mean rank should sit near 50 if the fire sample is unremarkable.",
    }
    return fire_rows, control


def _append_hindcast_metrics(
    frozen: dict[str, object], arm: str, hc: pd.DataFrame, out: Path, pred_dir: Path
) -> None:
    settings = get_settings()
    feat = load_features(settings.processed_dir / "features")
    splits = split_frames(feat) if len(feat) else {}
    train = splits.get("train", pd.DataFrame())
    pers = persistence_pred(hc)
    clim = climatology_pred(train, hc) if len(train) else pers
    pred_cols = [c for c in hc.columns if c.endswith("_hat")]
    pred = hc[pred_cols].copy()
    row = attach_skills(evaluate_arm(arm, pred, hc), hc, pred, pers, clim)
    pers_row = evaluate_arm("persistence", pers, hc)
    hindcast_rows: list[dict[str, object]] = [row, pers_row]
    for other in ("lightgbm", "pi_convlstm_none", "pi_convlstm_hydro", "pi_convlstm_both", "ensemble"):
        path = pred_dir / f"{other}_hindcast.parquet"
        if other == arm or not path.exists():
            continue
        other_frame = pd.read_parquet(path)
        other_pred = other_frame[[c for c in other_frame.columns if c.endswith("_hat")]].copy()
        opers = persistence_pred(other_frame)
        oclim = climatology_pred(train, other_frame) if len(train) else opers
        other_row = attach_skills(
            evaluate_arm(other, other_pred, other_frame), other_frame, other_pred, opers, oclim
        )
        hindcast_rows.append(other_row)
    frozen["hindcast"] = hindcast_rows
    frozen["hindcast_looks"] = json.loads((out / "run_log.json").read_text())
    (settings.artifacts_dir / "metrics.json").write_text(json.dumps(frozen, indent=2, default=str))
    md_path = settings.artifacts_dir / "metrics.md"
    extra = ["", "## Hindcast 2026 (first look after freeze)", ""]
    extra.append(
        "**Contaminated:** a post-hindcast scoring fix (`merge_pred` + NIFC epoch-ms dates) was applied. "
        "Hyperparameters were not changed. Skill vs persistence below is from look_index>1. See DECISIONS.md."
    )
    extra.append("")
    extra.append(format_skill_sentence(str(row.get("arm")), 2, "usdm", row, pers_row))
    extra.append(format_skill_sentence(str(row.get("arm")), 4, "usdm", row, pers_row))
    extra.append(format_skill_sentence(str(row.get("arm")), 8, "usdm", row, pers_row))
    extra.append(format_skill_sentence(str(row.get("arm")), 2, "erc", row, pers_row))
    extra.append(format_skill_sentence(str(row.get("arm")), 4, "erc", row, pers_row))
    extra.append(format_skill_sentence(str(row.get("arm")), 8, "erc", row, pers_row))
    extra.append("")
    for other_row in hindcast_rows:
        if other_row.get("arm") in {arm, "persistence"}:
            continue
        extra.append(format_skill_sentence(str(other_row.get("arm")), 4, "usdm", other_row, pers_row))
        extra.append(format_skill_sentence(str(other_row.get("arm")), 8, "usdm", other_row, pers_row))
        extra.append(format_skill_sentence(str(other_row.get("arm")), 4, "erc", other_row, pers_row))
        extra.append(format_skill_sentence(str(other_row.get("arm")), 8, "erc", other_row, pers_row))
    extra.append("")
    existing = md_path.read_text() if md_path.exists() else ""
    marker = "## Hindcast 2026"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip()
    md_path.write_text(existing.rstrip() + "\n" + "\n".join(extra))


def _nearest(snap: pd.DataFrame, lat: float, lon: float) -> pd.Series:
    d = (snap["lat"] - lat) ** 2 + (snap["lon"] - lon) ** 2
    return snap.loc[d.idxmin()]


def _discovery_date(fire: pd.Series) -> date | None:
    for key in ("attr_FireDiscoveryDateTime", "FIREDISCOVERYDATETIME", "DISCOVERY_DATE", "GDB_TO_DATE"):
        val = fire.get(key)
        if val is None:
            continue
        num: float | None
        try:
            num = float(val)
        except (TypeError, ValueError):
            num = None
        if num is not None and np.isfinite(num) and num > 1e11:
            ts = pd.to_datetime(num, unit="ms", errors="coerce")
        else:
            ts = pd.to_datetime(val, errors="coerce")
        if pd.notna(ts):
            stamp = pd.Timestamp(ts)
            return date(int(stamp.year), int(stamp.month), int(stamp.day))
    return None


def _fires_md(rows: list[dict[str, object]], control: dict[str, object]) -> str:
    lines = [
        "# 2026 perimeters vs pre-discovery fire-spread condition forecasts",
        "",
        "Values are the forecast ERC-percentile index at the fire location, issued 2/4/8 weeks before discovery, "
        "and the percentile rank of that forecast versus the domain on the same issue date. "
        "Fires outside the current bbox are nearest-cell only and flagged `in_domain=false`. "
        "No causal claim is made.",
        "",
        f"Control: 200 random non-fire cells, mean percentile rank {control.get('mean_pct_rank')}.",
        "",
        "| fire | in domain | discovery | acres | 2w rank | 4w rank | 8w rank |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| (none) | — | — | — | — | — | — |")
    for r in rows:
        lines.append(
            f"| {r.get('name')} | {r.get('in_domain')} | {r.get('discovery')} | {r.get('acres')} | "
            f"{r.get('h2_pct_rank')} | {r.get('h4_pct_rank')} | {r.get('h8_pct_rank')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run_hindcast()
