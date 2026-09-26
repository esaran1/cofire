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


def _woy(times: pd.Series) -> np.ndarray:
    weeks: np.ndarray = (
        pd.to_datetime(times).dt.isocalendar().week.astype(int).clip(1, 52).to_numpy()
    )
    return weeks


def regional_base_rate(train: pd.DataFrame, target: str, index: pd.DataFrame) -> np.ndarray:
    """How often the event happened in this county at this time of year.

    The training-era (train split only) share of cell-weeks where `target`
    occurred, pooled over the whole domain and over weeks of year within the
    project's usual +/- 3 week window of each issue. One number per issue,
    identical across cells.

    This replaces the average of the model's own 2026 predictions over every
    issue, which is not a base rate and mixed seasons: it showed a 64% chance
    of Larimer reaching D2 within four weeks on 22 September, where the record
    for late September says 11%.
    """
    from cofire.model.erc_pct import window_weeks

    y = pd.to_numeric(train[target], errors="coerce")
    tw = _woy(train["time"])
    ok = np.isfinite(y.to_numpy(dtype=float))
    rate_by_woy: dict[int, float] = {}
    for w in range(1, 53):
        m = ok & np.isin(tw, window_weeks(w))
        rate_by_woy[w] = float(y.to_numpy(dtype=float)[m].mean()) if m.any() else float("nan")
    return np.array([rate_by_woy[int(w)] for w in _woy(index["time"])])


def climatological_bounds(
    train: pd.DataFrame, horizon: int, index: pd.DataFrame, lo: float = 5.0, hi: float = 95.0
) -> tuple[np.ndarray, np.ndarray]:
    """The actual 5th and 95th percentiles of the typical range, per cell and week.

    Same pooling as `climatological_width`: a cell's training values within
    +/- 3 weeks of year, at least 10 of them, else the domain-wide pool. The
    Place Card used to draw the range as median +/- half the width, which is
    only right for a symmetric distribution; these are the real bounds.
    """
    from cofire.model.erc_pct import window_weeks

    col = f"erc_pct_h{horizon}"
    v = pd.to_numeric(train[col], errors="coerce").to_numpy(dtype=float)
    cells = train["cell_id"].astype(str).to_numpy()
    tw = _woy(train["time"])
    ok = np.isfinite(v)
    pools: dict[tuple[str, int], np.ndarray] = {}
    frame = pd.DataFrame({"c": cells[ok], "w": tw[ok], "v": v[ok]})
    by = {(c, int(w)): g["v"].to_numpy() for (c, w), g in frame.groupby(["c", "w"])}
    g_lo, g_hi = np.percentile(v[ok], lo), np.percentile(v[ok], hi)
    out_lo = np.full(len(index), g_lo)
    out_hi = np.full(len(index), g_hi)
    icells = index["cell_id"].astype(str).to_numpy()
    iw = _woy(index["time"])
    for i, (c, w) in enumerate(zip(icells, iw, strict=True)):
        key = (c, int(w))
        if key not in pools:
            parts = [by[(c, x)] for x in window_weeks(int(w)) if (c, x) in by]
            pools[key] = np.concatenate(parts) if parts else np.array([])
        pool = pools[key]
        if pool.size >= 10:
            out_lo[i], out_hi[i] = np.percentile(pool, lo), np.percentile(pool, hi)
    return out_lo, out_hi


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
            # No interval radius is carried into the export. It used to be the
            # last state of a PID controller run with same-week updates, which
            # the delayed-feedback gate shows leaks, and nothing renders a band.
            per_issue[f"erc_pct_h{h}_clim_median"] = climatological_median(train, h, issues)
            per_issue[f"erc_pct_h{h}_clim_width"] = climatological_width(train, h, issues)
            b_lo, b_hi = climatological_bounds(train, h, issues)
            per_issue[f"erc_pct_h{h}_clim_lo"] = b_lo
            per_issue[f"erc_pct_h{h}_clim_hi"] = b_hi

        # Probabilistic targets.
        for (target, h), c in sorted(choices.items()):
            pred = (
                _drought_prediction(h, train, target, issues)
                if c.family == "markov"
                else _fire_prediction(c.family, train, target, issues)
            )
            per_issue[f"{target}_p"] = pred
            per_issue[f"{target}_base_rate"] = regional_base_rate(train, target, issues)

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

    # A base-rate target shows the regional base rate: how often the event
    # happened in this county at this time of year in the training record.
    # Identical across cells by construction, and seasonal, so it moves with
    # the issue date instead of being one number for the whole year.
    for col in [c for c in out.columns if c.endswith("_state")]:
        key = col[: -len("_state")]
        pcol, bcol = f"{key}_p", f"{key}_base_rate"
        if pcol not in out.columns or bcol not in out.columns:
            continue
        m = out[col] == BASE_RATE
        out[pcol] = out[pcol].astype("float64")
        out.loc[m, pcol] = out.loc[m, bcol].astype("float64")
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
