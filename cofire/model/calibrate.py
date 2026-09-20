"""Calibrate conformal + bootstrap on 2024–2025 only. Does not score 2026."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cofire.model.config import get_settings
from cofire.model.conformal import ConformalCalibrator, attach_intervals
from cofire.model.log import setup_logging
from cofire.model.uncertainty import write_comparison
from cofire.model.uncertainty.bootstrap import attach_bootstrap, fit_bootstrap, save_bootstrap


def _load(pred_dir: Path, arm: str, split: str) -> pd.DataFrame:
    path = pred_dir / f"{arm}_{split}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def run_calibrate() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    arm = (
        (settings.artifacts_dir / "shipping_arm.txt").read_text().strip()
        if (settings.artifacts_dir / "shipping_arm.txt").exists()
        else "lightgbm"
    )
    pred_dir = settings.artifacts_dir / "predictions"
    cal = _load(pred_dir, arm, "calibrate")
    if cal.empty:
        arm = "lightgbm"
        cal = _load(pred_dir, arm, "calibrate")
    if cal.empty:
        raise SystemExit("no calibrate predictions — run `make train` first")
    conformal = ConformalCalibrator()
    conformal.fit(cal)
    cal_conf = attach_intervals(cal, conformal, update_aci=False)
    boot = fit_bootstrap(cal, arm)
    cal_boot = attach_bootstrap(cal, boot, arm)
    conformal.save(settings.artifacts_dir / "calibration")
    save_bootstrap(boot, settings.artifacts_dir / "calibration")
    cal_conf.to_parquet(pred_dir / f"{arm}_calibrate_intervals.parquet", index=False)
    md = write_comparison(
        cal_conf,
        cal_boot,
        None,
        None,
        settings.artifacts_dir / "uncertainty",
    )
    log.info("calibrate-only comparison %s (arm=%s); 2026 not scored", md, arm)
    return md


if __name__ == "__main__":
    run_calibrate()
