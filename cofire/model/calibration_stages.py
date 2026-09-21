"""Stages A and B: PID coverage, and the width-ratio classification.

Promoted into the repository so that the code producing the shipped intervals
and the rendering decision is inside the configuration hash. Stage A and B were
first run from scratch scripts, which meant the numbers in the preregistration
came from code the hash did not cover.

One correction on promotion. The original Stage A streamed the calibration
split ahead of the validation split, so the controller warmed up on 2024 and
2025 and was then scored on 2022 and 2023, which runs backwards in time. The
controller's warm-up state is not fitted on outcomes it is scored against, so
this was not leakage, but a conformal controller is an online method and
scoring it on data preceding its warm-up is not what it does in production.
`stage_a` now streams in time order and scores the portion after the burn-in.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.config import Settings, get_settings  # noqa: E402
from cofire.model.features_a import add_horizons  # noqa: E402
from cofire.model.features_a import load as load_a
from cofire.model.shipping import (  # noqa: E402
    DOMAIN_FOLDS,
    climatological_median,
    climatological_width,
    continuous_predict,
)
from cofire.model.stats_lib import circular_block_bootstrap  # noqa: E402
from cofire.model.targets import HORIZONS  # noqa: E402
from cofire.model.uncertainty.pid import aci_stream  # noqa: E402
from cofire.model.uncertainty.shipping_pid import (  # noqa: E402
    longest_miss_run,
    run_reference_pid,
)

LOGGER = logging.getLogger("cofire.calibration_stages")

OUT = Path("artifacts/rerun_a")
DOMAINS = ("larimer", "pueblo")
ROLL_WINDOW = 13


def arms() -> dict[str, str]:
    return dict(json.loads((OUT / "continuous_arms.json").read_text()))


def rolling_min_cov(
    covered: np.ndarray, weeks: np.ndarray, window: int = ROLL_WINDOW
) -> float:
    """Minimum coverage over any `window` consecutive weeks.

    The local test. Long-run coverage is close to guaranteed by the
    controller's construction; what can fail is a stretch where the interval is
    wrong week after week, which is what a user would experience.
    """
    df = pd.DataFrame({"w": pd.DatetimeIndex(weeks), "c": np.asarray(covered, dtype=float)})
    per = df.groupby("w")["c"].mean().sort_index()
    if len(per) < window:
        return float("nan")
    return float(per.rolling(window).mean().min())


def domain_frame(dom: str) -> tuple[pd.DataFrame, Settings]:
    os.environ["COFIRE_SUBSET_NAME"] = dom
    get_settings.cache_clear()
    st = get_settings()
    frame = add_horizons(
        load_a(st).assign(time=lambda d: pd.to_datetime(d["time"])), HORIZONS
    )
    return frame, st


def coverage_row(
    covered: np.ndarray,
    radii: np.ndarray,
    weeks: np.ndarray,
    usdm: np.ndarray,
    scored: np.ndarray,
    **meta: object,
) -> dict[str, object]:
    """One row of coverage results, scored on `scored` rows only."""
    d01 = (usdm < 2) & scored
    d2p = (usdm >= 2) & scored
    return {
        **meta,
        "coverage": round(float(covered[scored].mean()), 4),
        "width": round(float(2 * np.mean(radii[scored])), 2),
        "miss_run": longest_miss_run(covered[scored]),
        "roll13_min": round(rolling_min_cov(covered[scored], weeks[scored]), 4),
        "cov_d01": round(float(covered[d01].mean()), 4) if d01.any() else float("nan"),
        "cov_d2p": round(float(covered[d2p].mean()), 4) if d2p.any() else float("nan"),
        "n_d01": int(d01.sum()),
        "n_d2p": int(d2p.sum()),
    }


def stage_a(out_name: str = "pid_coverage.csv") -> Path:
    """Reference PID against ACI on the shipped continuous forecast.

    The stream runs in time order: validation then calibration, with the
    validation portion after the controller's burn-in scored. Both arms see one
    stream and one set of rows.
    """
    arm_by_h = arms()
    rows: list[dict[str, object]] = []
    for dom in DOMAINS:
        frame, st = domain_frame(dom)
        t = frame["time"]
        train = frame[t <= pd.Timestamp(st.train_end)]
        stream = frame[t >= pd.Timestamp(st.valid_start)].sort_values(["time", "cell_id"])
        for h in HORIZONS:
            arm = arm_by_h[str(h)]
            y = pd.to_numeric(stream[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
            p = continuous_predict(arm, train, h, stream)
            k = np.isfinite(y) & np.isfinite(p)
            s = np.abs(y[k] - p[k])
            weeks = pd.to_datetime(stream["time"]).to_numpy()[k]
            usdm = pd.to_numeric(stream["usdm"], errors="coerce").to_numpy(float)[k]

            pid = run_reference_pid(s)
            aci_q, aci_cov = aci_stream(s)
            # Score everything after the burn-in the controller declares.
            scored = np.zeros(s.size, dtype=bool)
            from cofire.model.uncertainty.shipping_pid import T_BURNIN

            scored[int(T_BURNIN) :] = True

            rows.append(
                coverage_row(
                    pid.covered, pid.radii, weeks, usdm, scored,
                    domain=dom, horizon=h, arm=arm, impl="reference_pid",
                )
            )
            rows.append(
                coverage_row(
                    aci_cov, aci_q, weeks, usdm, scored,
                    domain=dom, horizon=h, arm=arm, impl="aci",
                )
            )
            LOGGER.info(
                "%-8s h=%d pid cov=%.4f roll13=%.4f run=%d | aci cov=%.4f roll13=%.4f run=%d",
                dom, h, rows[-2]["coverage"], rows[-2]["roll13_min"], rows[-2]["miss_run"],
                rows[-1]["coverage"], rows[-1]["roll13_min"], rows[-1]["miss_run"],
            )
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / out_name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _fold_stack(dom: str, h: int, arm: str) -> tuple[np.ndarray, ...]:
    """Pooled out-of-fold predictions, climatology and targets for one horizon."""
    frame, st = domain_frame(dom)
    t = frame["time"]
    tr_all = frame[t <= pd.Timestamp(st.train_end)]
    ty = pd.to_datetime(tr_all["time"])
    parts: list[list[np.ndarray]] = [[], [], [], [], []]
    for yr in DOMAIN_FOLDS[dom]:
        tr, te = tr_all[ty.dt.year != yr], tr_all[ty.dt.year == yr]
        if tr.empty or te.empty:
            continue
        y = pd.to_numeric(te[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
        p = continuous_predict(arm, tr, h, te)
        mm = climatological_median(tr, h, te)
        ww = climatological_width(tr, h, te)
        k = np.isfinite(y) & np.isfinite(p) & np.isfinite(mm) & np.isfinite(ww)
        for lst, arr in zip(
            parts, (p[k], mm[k], y[k], ww[k], pd.to_datetime(te["time"]).to_numpy()[k]),
            strict=True,
        ):
            lst.append(arr)
    return tuple(np.concatenate(lst) for lst in parts)


def stage_b(out_name: str = "classification.csv") -> Path:
    """Width ratio against the climatological range, per domain and horizon.

    An interval is worth showing only if it is narrower than the historical
    spread the user could read off a climatology. The ratio's upper CI bound
    must fall below 1.0.
    """
    arm_by_h = arms()
    rows: list[dict[str, object]] = []
    for dom in DOMAINS:
        for h in HORIZONS:
            arm = arm_by_h[str(h)]
            p, mm, y, ww, weeks = _fold_stack(dom, h, arm)
            if y.size == 0:
                continue
            pid = run_reference_pid(np.abs(y - p))
            q = pid.radii
            diff = np.abs(mm - y) - np.abs(p - y)
            ones = np.ones_like(y)

            def mae_stat(sel: np.ndarray, diff: np.ndarray = diff,
                         weeks: np.ndarray = weeks) -> float:
                k = np.isin(weeks, sel)
                return float(np.mean(diff[k])) if k.any() else float("nan")

            def ratio_stat(sel: np.ndarray, q: np.ndarray = q, ww: np.ndarray = ww,
                           weeks: np.ndarray = weeks) -> float:
                k = np.isin(weeks, sel)
                if not k.any() or np.mean(ww[k]) <= 0:
                    return float("nan")
                return float(2 * np.mean(q[k]) / np.mean(ww[k]))

            mres = circular_block_bootstrap(mae_stat, weeks, ones, n_boot=400,
                                            min_positive_weeks=0)
            rres = circular_block_bootstrap(ratio_stat, weeks, ones, n_boot=400,
                                            min_positive_weeks=0)
            informative = bool(np.isfinite(rres.hi) and rres.hi < 1.0)
            rows.append(
                {
                    "domain": dom, "horizon": h, "arm": arm,
                    "mae_model": round(float(np.mean(np.abs(p - y))), 3),
                    "mae_clim": round(float(np.mean(np.abs(mm - y))), 3),
                    "mae_gain": round(mres.point, 3),
                    "mae_lo": round(mres.lo, 4), "mae_hi": round(mres.hi, 4),
                    "pid_width": round(pid.mean_width, 2),
                    "clim_width": round(float(np.mean(ww)), 2),
                    "ratio": round(rres.point, 4),
                    "ratio_lo": round(rres.lo, 4), "ratio_hi": round(rres.hi, 4),
                    "classification": "informative" if informative else "climatological",
                    "show_point": bool(mres.lo > 0),
                }
            )
            LOGGER.info(
                "%-8s h=%d ratio %.3f [%.3f,%.3f] -> %s",
                dom, h, rres.point, rres.lo, rres.hi,
                "INFORMATIVE" if informative else "climatological",
            )
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / out_name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    stage = sys.argv[1] if len(sys.argv) > 1 else "a"
    print(stage_a() if stage == "a" else stage_b())
