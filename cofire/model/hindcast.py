"""Hindcast 2026: issue-time cutoff, realized comparison, NIFC overlay."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cofire.model.config import HORIZONS_WEEKS, get_settings
from cofire.model.log import setup_logging

MAY1_ISSUE = date(2026, 5, 5)


class CutoffError(RuntimeError):
    """Raised when a feature row is later than the forecast issue date."""


def assert_cutoff(frame: pd.DataFrame, issue: date) -> None:
    times = pd.to_datetime(frame["time"])
    if (times > pd.Timestamp(issue)).any():
        bad = times[times > pd.Timestamp(issue)].max()
        raise CutoffError(f"issue {issue} saw future timestamp {bad.date()}")


def _percentile_rank(value: float, dist: np.ndarray) -> float:
    dist = dist[np.isfinite(dist)]
    if dist.size == 0 or not np.isfinite(value):
        return float("nan")
    return float(100.0 * (dist <= value).mean())


def run_hindcast() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    arm = (settings.artifacts_dir / "shipping_arm.txt").read_text().strip() if (settings.artifacts_dir / "shipping_arm.txt").exists() else "lightgbm"
    pred_path = settings.artifacts_dir / "predictions" / f"{arm}_hindcast_intervals.parquet"
    if not pred_path.exists():
        pred_path = settings.artifacts_dir / "predictions" / f"{arm}_hindcast.parquet"
    if not pred_path.exists():
        raise SystemExit("no hindcast predictions — run `make train calibrate`")
    frame = pd.read_parquet(pred_path)
    frame["time"] = pd.to_datetime(frame["time"])
    for issue, chunk in frame.groupby(frame["time"].dt.date):
        assert_cutoff(chunk, issue)

    out = settings.artifacts_dir / "hindcast"
    out.mkdir(parents=True, exist_ok=True)

    # Coverage over time from conformal columns if present.
    if "erc_pct_h4_lo" in frame.columns:
        recs = []
        for t, g in frame.groupby("time"):
            y = g["erc_pct_h4"].to_numpy(dtype=float) if "erc_pct_h4" in g else np.array([])
            lo = g["erc_pct_h4_lo"].to_numpy(dtype=float)
            hi = g["erc_pct_h4_hi"].to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(lo) & np.isfinite(hi)
            recs.append({"time": t, "coverage": float(np.mean((y[ok] >= lo[ok]) & (y[ok] <= hi[ok]))) if ok.any() else np.nan})
        cov = pd.DataFrame(recs)
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(cov["time"], cov["coverage"], color="#e6c15c")
        ax.axhline(0.90, color="white", linestyle="--", linewidth=1)
        ax.set_title("Hindcast conformal coverage, 4-week ERC percentile")
        fig.tight_layout()
        fig.savefig(out / "coverage.png", dpi=140, facecolor="#0c0e12")
        plt.close(fig)

    fires_path = settings.processed_dir / "nifc" / "perimeters_2026.geojson"
    fire_rows: list[dict[str, object]] = []
    if fires_path.exists():
        import geopandas as gpd

        fires = gpd.read_file(fires_path)
        for _, fire in fires.iterrows():
            disc = _discovery_date(fire)
            if disc is None:
                continue
            geom = fire.geometry
            if geom is None or geom.is_empty:
                continue
            lon, lat = geom.centroid.x, geom.centroid.y
            name = str(fire.get("poly_IncidentName") or fire.get("INCIDENTNAME") or fire.get("FIRENAME") or "unnamed")
            acres = fire.get("poly_GISAcres") or fire.get("GISACRES") or fire.get("GISAcres")
            rec: dict[str, object] = {"name": name, "discovery": disc.isoformat(), "lat": lat, "lon": lon, "acres": acres}
            for h in HORIZONS_WEEKS:
                issue = disc - timedelta(days=7 * h)
                # nearest Tuesday on or before
                from cofire.model.dates import previous_tuesday

                issue_t = previous_tuesday(issue)
                snap = frame[frame["time"] == pd.Timestamp(issue_t)]
                if snap.empty:
                    rec[f"h{h}_fire_index"] = None
                    rec[f"h{h}_pct_rank"] = None
                    continue
                cell = _nearest(snap, lat, lon)
                fi = float(cell.get("erc_pct_h4_hat", cell.get("erc_pct_h2_hat", np.nan))) if h == 4 else float(
                    cell.get(f"erc_pct_h{h}_hat", np.nan)
                )
                dist = snap[f"erc_pct_h{h}_hat"].to_numpy(dtype=float) if f"erc_pct_h{h}_hat" in snap else np.array([])
                rec[f"h{h}_fire_index"] = fi
                rec[f"h{h}_pct_rank"] = _percentile_rank(fi, dist)
                rec[f"h{h}_usdm"] = float(cell.get(f"usdm_h{h}_hat", np.nan))
                rec[f"h{h}_issue"] = issue_t.isoformat()
            fire_rows.append(rec)
    pd.DataFrame(fire_rows).to_json(out / "fires.json", orient="records")
    (out / "fires.md").write_text(_fires_md(fire_rows))
    log.info("hindcast fires=%s", len(fire_rows))
    return out


def _nearest(snap: pd.DataFrame, lat: float, lon: float) -> pd.Series:
    d = (snap["lat"] - lat) ** 2 + (snap["lon"] - lon) ** 2
    return snap.loc[d.idxmin()]


def _discovery_date(fire: pd.Series) -> date | None:
    for key in ("attr_FireDiscoveryDateTime", "FIREDISCOVERYDATETIME", "DISCOVERY_DATE", "GDB_TO_DATE"):
        val = fire.get(key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        ts = pd.to_datetime(val, errors="coerce")
        if pd.notna(ts):
            stamp = pd.Timestamp(ts)
            return date(int(stamp.year), int(stamp.month), int(stamp.day))
    return None


def _fires_md(rows: list[dict[str, object]]) -> str:
    lines = [
        "# 2026 perimeters vs pre-discovery fire-spread condition forecasts",
        "",
        "Values are the forecast fire-spread condition index (mean of ERC and BI percentiles when both exist; ERC percentile otherwise) at the fire location, issued 2/4/8 weeks before discovery, and the percentile rank of that forecast versus the domain on the same issue date. No causal claim is made.",
        "",
        "| fire | discovery | acres | 2w rank | 4w rank | 8w rank |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| (none in domain) | — | — | — | — | — |")
    for r in rows:
        lines.append(
            f"| {r.get('name')} | {r.get('discovery')} | {r.get('acres')} | {r.get('h2_pct_rank')} | {r.get('h4_pct_rank')} | {r.get('h8_pct_rank')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run_hindcast()
