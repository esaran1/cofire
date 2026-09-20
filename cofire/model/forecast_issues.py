"""Emit 2026 forecasts and intervals WITHOUT scoring them. INTENDED FOR HAND-REWRITE.

Why this is not a look at the holdout
-------------------------------------
A "look" is reading realized holdout outcomes and learning something from them.
Concretely, in this codebase that is:

  * `attach_intervals(..., update_aci=True)`, which calls `cal.observe(y, lo, hi)`
    and feeds the hit/miss back into alpha, and
  * `write_comparison`, `_score_fires`, `_append_hindcast_metrics` and the
    coverage plot, all of which compute MAE / coverage / skill against realized
    values.

This module does none of that. It takes the forecasts that `train.py` already
produced by a forward pass on issue-time features, attaches intervals whose
width comes entirely from the **calibrate-split** residual pool frozen in
`make calibrate`, and writes them for the app to display. No realized 2026
outcome is read, compared, or learned from, so the look counter must not move.
That invariant is asserted, not assumed: see `run_forecast_issues`.

The scoring path lives in `cofire.model.hindcast` and is deliberately never
imported here. `assert_scoring_not_invoked` proves it at runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from cofire.model.config import get_settings
from cofire.model.conformal import ConformalCalibrator, attach_intervals
from cofire.model.log import setup_logging
from cofire.model.uncertainty.bootstrap import attach_bootstrap, load_bootstrap

# Columns holding realized holdout outcomes. They exist in the predictions
# parquet because the feature builder emits labels for every split, but this
# module must never read them.
REALIZED_COLS = tuple(f"{t}_h{h}" for t in ("usdm", "erc_pct") for h in (2, 4, 8))

# Modules that perform scoring. Importing any of them here would be a bug.
SCORING_MODULES = ("cofire.model.hindcast",)


def look_count(settings: object) -> int:
    path = Path(getattr(settings, "artifacts_dir", Path("artifacts"))) / "hindcast" / "run_log.json"
    if not path.exists():
        return 0
    return len(json.loads(path.read_text()))


def assert_scoring_not_invoked() -> None:
    """Fail loudly if a scoring module was imported into this process."""
    for mod in SCORING_MODULES:
        if mod in sys.modules:
            raise AssertionError(
                f"{mod} is imported; the forecast path must not reach the scoring path. "
                "Run `python -m cofire.model.forecast_issues` in its own process."
            )


def _drop_realized(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove realized-outcome columns so nothing downstream can read them.

    This is the structural guarantee: with these columns gone, ACI cannot
    observe, and no metric can be computed, even by accident.
    """
    return frame.drop(columns=[c for c in REALIZED_COLS if c in frame.columns])


def run_forecast_issues() -> Path:
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    assert_scoring_not_invoked()

    looks_before = look_count(settings)

    arm_path = settings.artifacts_dir / "shipping_arm.txt"
    arm = arm_path.read_text().strip() if arm_path.exists() else "lightgbm"
    pred_dir = settings.artifacts_dir / "predictions"
    src = pred_dir / f"{arm}_hindcast.parquet"
    if not src.exists():
        raise SystemExit(f"no forecasts at {src} - run `make train` first")

    frame = pd.read_parquet(src)
    frame["time"] = pd.to_datetime(frame["time"])
    # Strip realized outcomes before anything else touches the frame.
    frame = _drop_realized(frame)
    assert not any(c in frame.columns for c in REALIZED_COLS), "realized outcomes survived the drop"

    cal_dir = settings.artifacts_dir / "calibration"
    conformal = ConformalCalibrator.load(cal_dir)
    alpha_before = {k: v.alpha for k, v in conformal.erc.items()}

    # update_aci=False is the whole point: intervals come from the frozen
    # calibrate-split pool and no outcome is observed.
    out = attach_intervals(frame, conformal, update_aci=False)

    alpha_after = {k: v.alpha for k, v in conformal.erc.items()}
    assert alpha_before == alpha_after, "ACI state changed; the calibrator learned from the holdout"

    boot = load_bootstrap(cal_dir)
    out = attach_bootstrap(out, boot, arm)

    dest = pred_dir / f"{arm}_forecast_issues.parquet"
    out.to_parquet(dest, index=False)

    looks_after = look_count(settings)
    assert looks_after == looks_before, (
        f"look counter moved {looks_before} -> {looks_after}; this stage must not score the holdout"
    )

    log.info(
        "forecast_issues: %s rows, %s issues, %s cells -> %s (looks unchanged at %s)",
        len(out),
        out["time"].nunique(),
        out["cell_id"].nunique(),
        dest,
        looks_after,
    )
    return dest


if __name__ == "__main__":
    print(run_forecast_issues())
