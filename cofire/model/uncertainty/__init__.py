"""Head-to-head: conformal vs bootstrap coverage and width.

Reports honestly on the calibrate split and on the 2026 hindcast, including a
stratification by USDM category and by month, plus a 2026 coverage-over-weeks
plot against the 0.90 line.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cofire.model.config import COVERAGE_TARGET, HORIZONS_WEEKS, get_settings


def _cover_width(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> tuple[float, float, int]:
    ok = np.isfinite(y) & np.isfinite(lo) & np.isfinite(hi)
    if ok.sum() == 0:
        return float("nan"), float("nan"), 0
    cover = float(np.mean((y[ok] >= lo[ok]) & (y[ok] <= hi[ok])))
    width = float(np.mean(hi[ok] - lo[ok]))
    return cover, width, int(ok.sum())


def evaluate_split(frame: pd.DataFrame, method: str) -> dict[str, object]:
    """method is 'conformal' (lo/hi) or 'bootstrap' (boot_lo/boot_hi)."""
    rows: list[dict[str, object]] = []
    for h in HORIZONS_WEEKS:
        y = frame[f"erc_pct_h{h}"].to_numpy(dtype=float) if f"erc_pct_h{h}" in frame.columns else np.array([])
        if method == "conformal":
            lo = frame[f"erc_pct_h{h}_lo"].to_numpy(dtype=float)
            hi = frame[f"erc_pct_h{h}_hi"].to_numpy(dtype=float)
        else:
            lo = frame[f"erc_pct_h{h}_boot_lo"].to_numpy(dtype=float)
            hi = frame[f"erc_pct_h{h}_boot_hi"].to_numpy(dtype=float)
        cover, width, n = _cover_width(y, lo, hi)
        rows.append({"horizon": h, "stratum": "overall", "coverage": cover, "width": width, "n": n})
        if "usdm" in frame.columns:
            for cat, chunk_idx in frame.groupby("usdm").groups.items():
                c, w, nn = _cover_width(y[list(chunk_idx)], lo[list(chunk_idx)], hi[list(chunk_idx)])
                rows.append({"horizon": h, "stratum": f"usdm={int(cat)}", "coverage": c, "width": w, "n": nn})
        months = pd.to_datetime(frame["time"]).dt.month
        for month in sorted(months.unique()):
            idx = np.where(months.to_numpy() == month)[0]
            c, w, nn = _cover_width(y[idx], lo[idx], hi[idx])
            rows.append({"horizon": h, "stratum": f"month={int(month)}", "coverage": c, "width": w, "n": nn})
    return {"method": method, "rows": rows}


def weekly_coverage(frame: pd.DataFrame, method: str, horizon: int = 4) -> pd.DataFrame:
    y = frame[f"erc_pct_h{horizon}"].to_numpy(dtype=float)
    if method == "conformal":
        lo = frame[f"erc_pct_h{horizon}_lo"].to_numpy(dtype=float)
        hi = frame[f"erc_pct_h{horizon}_hi"].to_numpy(dtype=float)
    else:
        lo = frame[f"erc_pct_h{horizon}_boot_lo"].to_numpy(dtype=float)
        hi = frame[f"erc_pct_h{horizon}_boot_hi"].to_numpy(dtype=float)
    tmp = pd.DataFrame({"time": pd.to_datetime(frame["time"]), "y": y, "lo": lo, "hi": hi})
    recs = []
    for t, g in tmp.groupby("time"):
        c, w, n = _cover_width(g["y"].to_numpy(), g["lo"].to_numpy(), g["hi"].to_numpy())
        recs.append({"time": t, "coverage": c, "width": w, "n": n})
    return pd.DataFrame(recs)


def write_comparison(
    cal_conf: pd.DataFrame,
    cal_boot: pd.DataFrame,
    hc_conf: pd.DataFrame | None,
    hc_boot: pd.DataFrame | None,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "nominal": COVERAGE_TARGET,
        "calibrate": {
            "conformal": evaluate_split(cal_conf, "conformal"),
            "bootstrap": evaluate_split(cal_boot, "bootstrap"),
        },
    }
    if hc_conf is not None and hc_boot is not None and len(hc_conf) and len(hc_boot):
        payload["hindcast"] = {
            "conformal": evaluate_split(hc_conf, "conformal"),
            "bootstrap": evaluate_split(hc_boot, "bootstrap"),
        }
        fig, ax = plt.subplots(figsize=(8, 3.4))
        wc = weekly_coverage(hc_conf, "conformal")
        wb = weekly_coverage(hc_boot, "bootstrap")
        ax.plot(wc["time"], wc["coverage"], color="#e6c15c", label="conformal")
        ax.plot(wb["time"], wb["coverage"], color="#ff5a2a", label="bootstrap")
        ax.axhline(COVERAGE_TARGET, color="#f2f0ea", linestyle="--", linewidth=1, label="0.90 target")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("empirical coverage")
        ax.set_title("2026 hindcast coverage (ERC percentile, 4-week horizon)")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(out_dir / "coverage_2026.png", dpi=140, facecolor="#0c0e12")
        plt.close(fig)
        wc.to_csv(out_dir / "coverage_2026_conformal.csv", index=False)
        wb.to_csv(out_dir / "coverage_2026_bootstrap.csv", index=False)
    (out_dir / "comparison.json").write_text(json.dumps(payload, indent=2, default=str))
    md = _markdown(payload)
    (out_dir / "comparison.md").write_text(md)
    return out_dir / "comparison.md"


def _overall(block: object, method: str, horizon: int = 4) -> tuple[float, float]:
    if not isinstance(block, dict):
        return float("nan"), float("nan")
    blob = block.get(method)
    if not isinstance(blob, dict):
        return float("nan"), float("nan")
    for row in blob.get("rows", []):
        if row.get("stratum") == "overall" and int(row.get("horizon", -1)) == horizon:
            return float(row.get("coverage", float("nan"))), float(row.get("width", float("nan")))
    return float("nan"), float("nan")


def _markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Conformal vs bootstrap",
        "",
        f"Nominal coverage target: **{COVERAGE_TARGET:.2f}**.",
        "Bootstrap is a 300-draw residual bootstrap on the calibrate-split residuals.",
        "Conformal `qhat` is frozen on the same split; ACI updates alpha online.",
        "Neither method is tuned on the 2026 hindcast.",
        "",
        "2026 is treated as a distribution-shift test. Coverage is reported, not retuned.",
        "",
    ]
    cal = payload.get("calibrate")
    hc = payload.get("hindcast")
    cc, cw = _overall(cal, "conformal")
    bc, bw = _overall(cal, "bootstrap")
    lines.append(
        f"On the 2024–2025 calibration split, conformal 4-week ERC coverage is {cc:.3f} "
        f"(target {COVERAGE_TARGET:.2f}, mean width {cw:.2f}); bootstrap coverage is {bc:.3f} (mean width {bw:.2f})."
    )
    if isinstance(hc, dict):
        hcc, hcw = _overall(hc, "conformal")
        hbc, hbw = _overall(hc, "bootstrap")
        lines.append(
            f"On the 2026 hindcast, conformal 4-week ERC coverage is {hcc:.3f} (mean width {hcw:.2f}); "
            f"bootstrap coverage is {hbc:.3f} (mean width {hbw:.2f})."
        )
        miss = abs(hcc - COVERAGE_TARGET) if np.isfinite(hcc) else float("nan")
        if np.isfinite(miss) and miss > 0.03:
            lines.append(
                f"Conformal hindcast coverage misses the 0.90 target by {100.0 * miss:.1f} points. "
                "Whether the ACI learning rate (0.01) is too slow for weekly steps is a pre-registered follow-up, "
                "not a post-hindcast fix."
            )
        elif np.isfinite(hcc) and np.isfinite(hbc) and abs(hcc - COVERAGE_TARGET) <= 0.03 and abs(hbc - COVERAGE_TARGET) <= 0.03:
            lines.append("Both methods held near 0.90 on 2026. The conformal-vs-bootstrap contrast is not the story here.")
        elif np.isfinite(hcc) and np.isfinite(hbc) and abs(hcc - COVERAGE_TARGET) <= 0.03 < abs(hbc - COVERAGE_TARGET):
            lines.append("Conformal held near 0.90 on 2026; bootstrap did not.")
        elif np.isfinite(hcc) and np.isfinite(hbc) and abs(hbc - COVERAGE_TARGET) <= 0.03 < abs(hcc - COVERAGE_TARGET):
            lines.append("Bootstrap held near 0.90 on 2026; conformal did not.")
    else:
        lines.append("Hindcast coverage is not in this file yet.")
    lines.append("")
    for split in ("calibrate", "hindcast"):
        block = payload.get(split)
        if not isinstance(block, dict):
            lines.append(f"## {split}")
            lines.append("No rows available.")
            lines.append("")
            continue
        lines.append(f"## {split}")
        lines.append("| method | horizon | stratum | coverage | mean width | n |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for method, blob in block.items():
            if not isinstance(blob, dict):
                continue
            for row in blob.get("rows", []):
                stratum = str(row["stratum"])
                if stratum != "overall" and not stratum.startswith("usdm=") and not stratum.startswith("month="):
                    continue
                cov = row["coverage"]
                cov_s = "nan" if not isinstance(cov, (int, float)) or cov != cov else f"{float(cov):.3f}"
                w = row["width"]
                w_s = "nan" if not isinstance(w, (int, float)) or w != w else f"{float(w):.2f}"
                lines.append(
                    f"| {method} | {row['horizon']} | {row['stratum']} | {cov_s} | {w_s} | {row['n']} |"
                )
        lines.append("")
    lines.append("Numbers are empirical. If conformal holds 0.90 where bootstrap drops, that is the result; the reverse is also reportable.")
    lines.append("")
    return "\n".join(lines)


def default_out_dir() -> Path:
    return get_settings().artifacts_dir / "uncertainty"
