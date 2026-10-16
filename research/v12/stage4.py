"""v1.2 Stage 4: lag-aware intervals, the configuration the gate passes.

    python -m research.v12.stage4 run

The reference conformal PID with the real delay (`ahead` = h weeks of rows in
a stream ordered by issue week then cell) and a fixed step size, around
configuration A's continuous point forecast (docs/PREREGISTRATION_V12.md).
Evaluated on 2022 to 2025 in time order, per domain and horizon; the point
forecast is configuration A's continuous arm fitted on 2007 to 2021, which is
out of sample for every row. The first 13 weeks are burn-in. A band may be
drawn for a domain and horizon only if all four criteria pass.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from cofire.v12 import common  # noqa: E402

LOGGER = logging.getLogger("research.v12.stage4")
OUT = common.OUT / "stage4"
TRAIN_END = pd.Timestamp("2021-12-31")
START, END = pd.Timestamp("2022-01-01"), pd.Timestamp("2025-12-31")
BURN_IN_WEEKS = 13
ROLL13_FLOOR = 0.70
COND_TOL = 0.05
MISS_RUN_MAX = 60
TARGET = 0.90


def gate_passes(horizons: tuple[int, ...] = (2, 4, 8)) -> bool:
    """The fixed-step, lagged reference PID passes the delayed-feedback gate."""
    from cofire.ship.leak_gate import Stream, reference_pid_fixed_step, run_gate

    stream = Stream(weeks=40, cells=4)
    for h in horizons:
        r = run_gate(f"fixed-step PID h{h}", reference_pid_fixed_step(h * stream.cells), stream, h)
        if not r.passed:
            raise SystemExit(f"gate failed: fixed-step PID h{h}, first leaking probe {r.first_leak}")
    return True


def width_ratio_ci(width: np.ndarray, clim: np.ndarray, weeks: np.ndarray, n_boot: int = 400) -> tuple[float, float, float]:
    """Ratio of mean band width to mean climatological width, circular block bootstrap over weeks."""
    from arch.bootstrap import CircularBlockBootstrap

    df = pd.DataFrame({"w": pd.DatetimeIndex(weeks), "a": width, "b": clim}).groupby("w")[["a", "b"]].sum().sort_index()
    a, b = df["a"].to_numpy(), df["b"].to_numpy()
    point = float(a.sum() / b.sum())
    block = max(2, round(len(df) ** (1 / 3)))
    idx = np.arange(len(df))
    draws = [float(a[d[0]].sum() / b[d[0]].sum()) for d, _ in CircularBlockBootstrap(block, idx, seed=common.SEED).bootstrap(n_boot)]
    return point, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def evaluate(domain: str, h: int) -> dict[str, Any]:
    from cofire.model.calibration_stages import rolling_min_cov
    from cofire.model.shipping import climatological_width, continuous_predict
    from cofire.model.uncertainty.shipping_pid import longest_miss_run
    from cofire.ship import fit_v11
    from cofire.ship.leak_gate import reference_pid_fixed_step

    f = common.record(domain)
    g = fit_v11.with_targets(f, pd.to_numeric(f["erc_pct"], errors="coerce").to_numpy(float))
    train = fit_v11.embargo(g[g["time"] <= TRAIN_END], TRAIN_END + pd.Timedelta(days=1), h)
    s = g[(g["time"] >= START) & (g["time"] <= END)].sort_values(["time", "cell_id"]).reset_index(drop=True)
    arm = fit_v11.continuous_arms(domain)[h]
    p = np.asarray(continuous_predict(arm, train, h, s), dtype=float)
    y = pd.to_numeric(s[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
    keep = np.isfinite(p) & np.isfinite(y)  # late-2025 labels would land in 2026: not in the record
    s, p, y = s[keep].reset_index(drop=True), p[keep], y[keep]
    weeks = pd.to_datetime(s["time"]).to_numpy()
    n_week = int(pd.Series(weeks).value_counts().max())
    scores = np.abs(y - p)
    radius = reference_pid_fixed_step(h * n_week)(scores)
    covered = scores <= radius
    first = pd.Series(sorted(set(weeks))).iloc[BURN_IN_WEEKS]
    sc = weeks >= np.datetime64(first)
    cat = pd.to_numeric(s["usdm"], errors="coerce").to_numpy(float)
    mild, severe = sc & (np.round(cat) <= 1), sc & (np.round(cat) >= 2)
    clim = climatological_width(train, h, s)
    finite = np.isfinite(radius) & sc
    ratio, lo, hi = width_ratio_ci(2 * np.where(np.isfinite(radius), radius, np.nan)[finite], clim[finite], weeks[finite])
    out: dict[str, Any] = {
        "domain": domain, "horizon": h, "arm": arm, "rows_scored": int(sc.sum()), "ahead_rows": h * n_week,
        "coverage": float(covered[sc].mean()),
        "roll13_min": rolling_min_cov(covered[sc], weeks[sc]),
        "coverage_d0_d1": float(covered[mild].mean()) if mild.any() else float("nan"),
        "coverage_d2_plus": float(covered[severe].mean()) if severe.any() else float("nan"),
        "miss_run": int(longest_miss_run(covered[sc])),
        "radius_min": float(np.nanmin(radius[sc])), "radius_max": float(np.nanmax(radius[sc])),
        "infinite_radius_rows": int((~np.isfinite(radius[sc])).sum()),
        "width_ratio": ratio, "width_ratio_lo": lo, "width_ratio_hi": hi,
    }
    def cond_ok(v: float) -> bool:
        return bool(np.isnan(v) or abs(v - TARGET) <= COND_TOL)  # a stratum with no rows has nothing to fail

    out["pass_roll13"] = bool(out["roll13_min"] >= ROLL13_FLOOR)
    out["pass_conditional"] = cond_ok(out["coverage_d0_d1"]) and cond_ok(out["coverage_d2_plus"])
    out["pass_miss_run"] = bool(out["miss_run"] <= MISS_RUN_MAX)
    out["pass_width"] = bool(np.isfinite(hi) and hi < 1.0)
    out["band_allowed"] = out["pass_roll13"] and out["pass_conditional"] and out["pass_miss_run"] and out["pass_width"]
    LOGGER.info("%s h%d cov=%.4f roll13=%.4f d01=%.3f d2=%.3f run=%d ratio=%.3f [%.3f, %.3f] band=%s", domain, h,
                out["coverage"], out["roll13_min"], out["coverage_d0_d1"], out["coverage_d2_plus"], out["miss_run"],
                ratio, lo, hi, out["band_allowed"])
    return out


def run() -> dict[str, Any]:
    from cofire.ship import domains

    with common.sealed():
        gate_passes()
        rows = [evaluate(d, h) for d in domains.ORDER for h in (2, 4, 8)]
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "intervals.csv", index=False)
    summary = {"gate": "fixed-step lagged reference PID passed at h = 2, 4, 8",
               "pairs": len(df), "band_allowed": int(df["band_allowed"].sum()),
               "pass_counts": {c: int(df[c].sum()) for c in ("pass_roll13", "pass_conditional", "pass_miss_run", "pass_width")},
               "allowed": [f"{r.domain} h{r.horizon}" for r in df.itertuples() if r.band_allowed]}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if sys.argv[1] == "run":
        print(json.dumps(run(), indent=1))
    else:
        raise SystemExit(__doc__)
