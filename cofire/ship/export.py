"""Export forecasts from the frozen configuration, scoring nothing.

What makes this not a look at the holdout: it reads issue-time features and
emits predictions and interval radii. It never reads a realized `*_h{2,4,8}`
outcome, never computes a metric, and never updates controller state from an
outcome. `assert_no_scoring` checks the first of those structurally, by
dropping the realized columns before anything downstream can see them.

The PID radius shown for a 2026 issue comes from the controller's state at the
end of the calibration split, frozen. Running the controller forward through
2026 would require observing 2026 outcomes, which is exactly what this path
must not do.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.ship.rendering import (  # noqa: E402
    BASE_RATE,
    all_decisions,
)

LOGGER = logging.getLogger("cofire.ship.export")

OUT = Path("artifacts/ship")
DOMAINS = ("larimer", "pueblo")
LAST_ISSUE = pd.Timestamp("2026-09-22")
HORIZONS = (2, 4, 8)

# Realized outcomes. Present in the built frame because the builder emits
# labels for every split; this module drops them before use.
def realized_columns(frame: pd.DataFrame) -> list[str]:
    import re

    pat = re.compile(r"^(erc_pct|usdm|d_|f_).*_h\d+$")
    return [c for c in frame.columns if pat.match(c)]


def assert_no_scoring(frame: pd.DataFrame) -> None:
    left = realized_columns(frame)
    if left:
        raise AssertionError(
            f"realized outcome columns survived into the export frame: {left[:6]}. "
            "The export path must not be able to read a holdout outcome."
        )


def build_export() -> pd.DataFrame:
    """Every issue through 2026-09-22, both domains, from the frozen model."""
    from cofire.model.calibration_stages import arms
    from cofire.model.look3 import build_holdout
    from cofire.model.shipping import (
        _drought_prediction,
        _fire_prediction,
        climatological_median,
        climatological_width,
        continuous_predict,
    )
    from cofire.model.shipping import load as load_choices
    from cofire.model.uncertainty.shipping_pid import run_reference_pid

    choices = load_choices(out_dir=Path("artifacts/rerun_a"))
    arm_by_h = arms()
    decisions = all_decisions()
    out_frames: list[pd.DataFrame] = []

    for dom in DOMAINS:
        frame, st = build_holdout(dom)
        frame["time"] = pd.to_datetime(frame["time"])
        t = frame["time"]
        train = frame[t <= pd.Timestamp(st.train_end)]
        issues = frame[(t > pd.Timestamp(st.calibrate_end)) & (t <= LAST_ISSUE)].copy()
        if issues.empty:
            raise SystemExit(f"{dom}: no issues after {st.calibrate_end}")

        base = issues[["time", "cell_id", "lat", "lon", "erc", "erc_pct", "usdm", "woy"]].copy()
        base["domain"] = dom
        per_issue: dict[str, np.ndarray] = {}

        # Continuous ERC percentile, one column set per horizon.
        for h in HORIZONS:
            arm = arm_by_h[str(h)]
            pred = continuous_predict(arm, train, h, issues)
            per_issue[f"erc_pct_h{h}_point"] = pred
            # The interval radius is the controller's frozen state at the end
            # of calibration, not re-derived from 2026 outcomes.
            cal = frame[
                (t >= pd.Timestamp(st.valid_start)) & (t <= pd.Timestamp(st.calibrate_end))
            ].sort_values(["time", "cell_id"])
            y_cal = pd.to_numeric(cal[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
            p_cal = continuous_predict(arm, train, h, cal)
            k = np.isfinite(y_cal) & np.isfinite(p_cal)
            radius = float(run_reference_pid(np.abs(y_cal[k] - p_cal[k])).radii[-1])
            per_issue[f"erc_pct_h{h}_radius"] = np.full(len(issues), radius)
            per_issue[f"erc_pct_h{h}_clim_median"] = climatological_median(train, h, issues)
            per_issue[f"erc_pct_h{h}_clim_width"] = climatological_width(train, h, issues)

        # Probabilistic targets.
        for (target, h), c in sorted(choices.items()):
            pred = (
                _drought_prediction(h, train, target, issues)
                if c.family == "markov"
                else _fire_prediction(c.family, train, target, issues)
            )
            per_issue[f"{target}_p"] = pred

        for col, vals in per_issue.items():
            base[col] = vals
        out_frames.append(base)

    export = pd.concat(out_frames, ignore_index=True)
    assert_no_scoring(export)
    export = attach_rendering(export, decisions)
    return export


def attach_rendering(frame: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """Store the rendering state and reason per target, horizon and domain.

    Applied here rather than in the app so that the rule lives in one place and
    the export is self-describing: a reader of the parquet can see what each
    number is allowed to be shown as, and why.
    """
    out = frame.copy()
    for _, d in decisions.iterrows():
        dom, target, h, state, reason = (
            str(d["domain"]), str(d["target"]), int(d["horizon"]),
            str(d["state"]), str(d["reason"]),
        )
        m = out["domain"] == dom
        if target == "erc_pct":
            key = f"erc_pct_h{h}"
        else:
            key = target
            if f"{key}_p" not in out.columns:
                continue
        out.loc[m, f"{key}_state"] = state
        out.loc[m, f"{key}_reason"] = reason

    # A base-rate target shows one number for the whole domain, so compute it
    # once per domain and write it to every cell: identical by construction
    # rather than identical by coincidence.
    for col in [c for c in out.columns if c.endswith("_state")]:
        key = col[: -len("_state")]
        pcol = f"{key}_p"
        if pcol not in out.columns:
            continue
        for dom in DOMAINS:
            m = (out["domain"] == dom) & (out[col] == BASE_RATE)
            if m.any():
                out.loc[m, pcol] = float(np.nanmean(out.loc[m, pcol].to_numpy(float)))
    return out


def write(out_dir: Path = OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = build_export()
    path = out_dir / "forecast_issues.parquet"
    frame.to_parquet(path, index=False)
    states = {
        c[: -len("_state")]: frame[c].dropna().unique().tolist()
        for c in frame.columns if c.endswith("_state")
    }
    LOGGER.info(
        "%d rows, %d issues %s..%s, %d cells, %d targets with a rendering state",
        len(frame), frame["time"].nunique(),
        frame["time"].min().date(), frame["time"].max().date(),
        frame["cell_id"].nunique(), len(states),
    )
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write())
