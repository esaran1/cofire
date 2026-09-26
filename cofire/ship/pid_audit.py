"""Audit: are the shipped intervals valid for a real-time forecast?

What this found, and why it drives the rendering:

1. Every PID and ACI run in this project streamed rows in (week, cell) order
   and called the controller with `ahead=1`, so each row's interval was
   adjusted by the error of the row before it: another cell in the same issue
   week, whose outcome does not exist until 2 to 8 weeks later. That is
   information a real forecaster cannot have. It affects Stage A, Stage B and
   the look-3 interval results, which are void as real-time evidence.
2. Run with the lag applied to its updates, `ahead = h weeks x cells per
   week`, the configured PID controller is unstable: integrator windup under
   delayed feedback, with radii swinging to large negative and positive values.
   That run is not fully causal either. The delayed-feedback gate later showed
   the reference implementation scales its step size from the most recent 100
   scores regardless of `ahead`, so same-week information still enters through
   the step size (cofire/ship/leak_gate.py).
3. The radius the export applied to every 2026 forecast was the leaky
   controller's final state. Scored on 2024-2025 it covers well under 90%.
4. Split conformal, a fixed 90th percentile of 2022-2023 errors, is valid in
   real time; its results are recorded for comparison.

Everything here uses 2022-2025 only. The sealed 2026 year is not read: look 3
is spent, and a recomputation on it would be a fourth look.

The vendored reference controller uses `np.infty`, removed in NumPy 2, on its
`ahead > 1` path. The file must stay byte-identical, so the alias is restored
here for the duration of the audit. That path had never run in this project.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LOGGER = logging.getLogger("cofire.ship.pid_audit")

OUT = Path("artifacts/audit")
COVERAGE_TARGET = 0.90
ROLL13_FLOOR = 0.70


def _scores(frame: pd.DataFrame, train: pd.DataFrame, arm: str, h: int, lo: Any, hi: Any) -> tuple[np.ndarray, np.ndarray]:
    from cofire.model.shipping import continuous_predict

    t = frame["time"]
    f = frame[(t >= pd.Timestamp(lo)) & (t <= pd.Timestamp(hi))].sort_values(["time", "cell_id"])
    y = pd.to_numeric(f[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
    p = continuous_predict(arm, train, h, f)
    k = np.isfinite(y) & np.isfinite(p)
    return np.abs(y[k] - p[k]), pd.to_datetime(f["time"]).to_numpy()[k]


def run() -> dict[str, Any]:
    if not hasattr(np, "infty"):
        np.infty = np.inf  # type: ignore[attr-defined]
    from cofire.model.calibration_stages import arms, domain_frame, rolling_min_cov
    from cofire.model.uncertainty.shipping_pid import T_BURNIN, longest_miss_run, run_reference_pid

    shown_path = OUT / "shown_radius.json"
    shown = json.loads(shown_path.read_text()) if shown_path.exists() else None
    arm_by_h = arms()
    rows: list[dict[str, Any]] = []

    def record(dom: str, h: int, method: str, covered: np.ndarray, weeks: np.ndarray, radius: float | None) -> None:
        rows.append({
            "domain": dom, "horizon": h, "method": method,
            "coverage": round(float(covered.mean()), 4),
            "roll13_min": round(rolling_min_cov(covered, weeks), 4),
            "miss_run": int(longest_miss_run(covered)),
            "radius": None if radius is None or not np.isfinite(radius) else round(radius, 2),
        })
        LOGGER.info("%s h%d %-28s cov=%.4f roll13=%.4f", dom, h, method, rows[-1]["coverage"], rows[-1]["roll13_min"])

    for dom in ("larimer", "pueblo"):
        frame, st = domain_frame(dom)
        train = frame[frame["time"] <= pd.Timestamp(st.train_end)]
        for h in (2, 4, 8):
            arm = arm_by_h[str(h)]
            s_all, wk_all = _scores(frame, train, arm, h, st.valid_start, st.calibrate_end)
            n_week = int(pd.Series(wk_all).value_counts().max())

            # As tested: ahead=1 over the same stream Stage A used.
            r1 = run_reference_pid(s_all.tolist(), ahead=1)
            sc = np.arange(s_all.size) >= T_BURNIN
            record(dom, h, "PID as tested (ahead=1)", r1.covered[sc], wk_all[sc], None)

            # Real time: outcome of issue t known h weeks later.
            lag = h * n_week
            rl = run_reference_pid(s_all.tolist(), ahead=lag)
            sc = np.arange(s_all.size) >= max(T_BURNIN, lag)
            fin = np.isfinite(rl.radii)
            rows[-1]["unstable"] = False
            record(dom, h, "PID in real time (lagged)", rl.covered[sc], wk_all[sc], None)
            rows[-1]["radius_min"] = round(float(rl.radii[fin].min()), 1)
            rows[-1]["radius_max"] = round(float(rl.radii[fin].max()), 1)
            rows[-1]["unstable"] = bool(rl.radii[fin].min() < 0)

            # Fit on 2022-2023, score on 2024-2025.
            s_fit, _ = _scores(frame, train, arm, h, st.valid_start, st.valid_end)
            s_ev, wk_ev = _scores(frame, train, arm, h, st.calibrate_start, st.calibrate_end)
            n = s_fit.size
            q = float(np.quantile(s_fit, min(1.0, np.ceil((n + 1) * COVERAGE_TARGET) / n)))
            record(dom, h, "split conformal", s_ev <= q, wk_ev, q)
            # The radius the export applied to every 2026 forecast, restored from
            # the last export that carried it. It cannot be recomputed from this
            # stream: the export's stream ran through 2026, so its last labels
            # were sealed-year outcomes, which this audit does not read.
            if shown is not None:
                r_shown = float(shown["radius"][f"{dom}|{h}"])
                record(dom, h, "radius the app showed", s_ev <= r_shown, wk_ev, r_shown)

    frame_out = pd.DataFrame(rows)
    real = frame_out[frame_out["method"] == "PID in real time (lagged)"]
    verdict = {
        "realtime_valid": bool(
            (real["roll13_min"] >= ROLL13_FLOOR).all() and not real["unstable"].any()
        ),
        "reason": (
            "The interval tests were run with same-week updates a real-time "
            "forecaster cannot make. With the honest lag the controller is "
            "unstable, so no calibrated interval can be shown."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    frame_out.to_csv(OUT / "pid_realtime.csv", index=False)
    (OUT / "pid_realtime.json").write_text(json.dumps({"verdict": verdict, "rows": rows}, indent=2))
    return verdict


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
