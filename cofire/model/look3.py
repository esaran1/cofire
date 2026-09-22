"""Look 3 on the sealed 2026 holdout. Run once, or not at all.

This script is the only path by which 2026 outcomes enter the project. It:

1. verifies the four preconditions in `docs/PREREGISTRATION_LOOK3.md` and
   refuses to proceed if any fails;
2. builds 2026 features through the same builder the training record used,
   with the window extended to the holdout only here. `features_a.build`
   deliberately stops at `calibrate_end`, so the sealed year cannot enter the
   feature store by any routine rebuild;
3. computes exactly the preregistered tests and nothing else;
4. writes `artifacts/look3/` and records the look.

It is not rerun. If it crashes after writing results, the results stand; if it
crashes before, the traceback is reported and the work stops. Both cases are
handled by writing results once, at the end, in one place.

The environment variable `COFIRE_ALLOW_LOOK=3` is required. A look at sealed
data should take a deliberate act, not an accidental invocation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.calibration_stages import rolling_min_cov  # noqa: E402
from cofire.model.config import Settings, get_settings  # noqa: E402
from cofire.model.freeze import (  # noqa: E402
    HOLDOUT_YEAR,
    config_hash,
    freeze_conditions,
    record_look,
)
from cofire.model.prob_metrics import brier, brier_decomposition  # noqa: E402
from cofire.model.shipping import (  # noqa: E402
    _drought_prediction,
    _fire_prediction,
    continuous_predict,
)
from cofire.model.stats_lib import reliability_sklearn  # noqa: E402
from cofire.model.targets import HORIZONS, all_event_targets  # noqa: E402
from cofire.model.uncertainty.shipping_pid import (  # noqa: E402
    T_BURNIN,
    longest_miss_run,
    run_reference_pid,
)

LOGGER = logging.getLogger("cofire.look3")

OUT = Path("artifacts/look3")
DOMAINS = ("larimer", "pueblo")

# The preregistered criteria. Stated here as constants so the code and the
# document cannot drift apart silently.
ROLL13_FLOOR = 0.70
COND_COVERAGE_TOL = 0.05
COND_COVERAGE_TARGET = 0.90
MISS_RUN_BOUND = 60
RELIABILITY_MAX = 0.05
LAST_ISSUE = date(2026, 9, 22)


@dataclass
class Criterion:
    name: str
    scope: str
    observed: float
    threshold: str
    passed: bool


def build_holdout(dom: str) -> tuple[pd.DataFrame, Settings]:
    """Configuration A's features extended through the holdout year.

    The only place the window reaches 2026. `features_a.build_template` and
    `weekly_usdm` both stop at `calibrate_end`, so this rebuilds with the
    window widened rather than reaching into the sealed store.
    """
    import xarray as xr

    from cofire.model.data import DateRange
    from cofire.model.data.usdm import UsdmSource
    from cofire.model.dates import tuesdays
    from cofire.model.features_a import (
        GridTemplate,
        add_horizons,
        erc_percentile,
        weekly_erc,
    )

    os.environ["COFIRE_SUBSET_NAME"] = dom
    get_settings.cache_clear()
    st = get_settings()

    grid_dir = st.processed_dir / "gridmet"
    cubes = sorted(grid_dir.glob("weekly_*.nc"))
    with xr.open_dataset(cubes[0]) as ds:
        lat = np.asarray(ds["lat"].values, dtype=float)
        lon = np.asarray(ds["lon"].values, dtype=float)
    weeks = pd.DatetimeIndex(list(tuesdays(st.train_start, LAST_ISSUE)))
    template = GridTemplate(lat=lat, lon=lon, weeks=weeks)

    erc = weekly_erc(template, st)
    src = UsdmSource(st)
    src._rasterize_zips(
        st.raw_dir / "usdm", template.as_dataset(),
        DateRange(start=st.train_start, end=LAST_ISSUE),
    )
    with xr.open_dataset(src._raster_path()) as ds:
        usdm = ds[next(iter(ds.data_vars))].load()

    common = np.intersect1d(erc["time"].values, usdm["time"].values)
    erc, usdm = erc.sel(time=common), usdm.sel(time=common)
    # The percentile pools stay fitted on the training window, as everywhere
    # else. The holdout is scored against a frozen training distribution.
    pct = erc_percentile(erc, pd.Timestamp(st.train_end))

    times = pd.DatetimeIndex(erc["time"].values)
    rows = []
    for i, la in enumerate(np.asarray(erc["lat"].values, dtype=float)):
        for j, lo in enumerate(np.asarray(erc["lon"].values, dtype=float)):
            rows.append(
                pd.DataFrame(
                    {
                        "time": times, "cell_id": f"{la:.4f}_{lo:.4f}",
                        "lat": la, "lon": lo,
                        "erc": erc.values[:, i, j],
                        "usdm": usdm.values[:, i, j],
                        "erc_pct": pct.values[:, i, j],
                    }
                )
            )
    frame = pd.concat(rows, ignore_index=True)
    frame["woy"] = frame["time"].dt.isocalendar().week.astype(int)
    frame["month"] = frame["time"].dt.month
    doy = frame["time"].dt.dayofyear.to_numpy(dtype=float)
    frame["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    frame["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    frame = add_horizons(frame, HORIZONS)
    frame = all_event_targets(frame, HORIZONS)
    return frame, st


def interval_tests(frame: pd.DataFrame, st: Settings, dom: str) -> tuple[list[dict[str, object]], list[Criterion]]:
    """Tests 1 to 4, per horizon, plus the PID against ACI comparison."""
    from cofire.model.calibration_stages import arms
    from cofire.model.uncertainty.pid import aci_stream

    arm_by_h = arms()
    t = pd.to_datetime(frame["time"])
    train = frame[t <= pd.Timestamp(st.train_end)]
    # The controller streams in time order from the end of training, and is
    # scored on 2026 only. Its warm-up is the validation and calibration
    # splits, which is the state it would be in operationally.
    stream = frame[t >= pd.Timestamp(st.valid_start)].sort_values(["time", "cell_id"])

    rows: list[dict[str, object]] = []
    crits: list[Criterion] = []
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

        holdout = pd.DatetimeIndex(weeks).year == HOLDOUT_YEAR
        holdout &= np.arange(s.size) >= int(T_BURNIN)
        if not holdout.any():
            continue
        for impl, cov, rad in (
            ("reference_pid", pid.covered, pid.radii), ("aci", aci_cov, aci_q)
        ):
            d01 = (usdm < 2) & holdout
            d2p = (usdm >= 2) & holdout
            rec = {
                "domain": dom, "horizon": h, "impl": impl,
                "n": int(holdout.sum()),
                "coverage": round(float(cov[holdout].mean()), 4),
                "width": round(float(2 * np.mean(rad[holdout])), 2),
                "miss_run": longest_miss_run(cov[holdout]),
                "roll13_min": round(rolling_min_cov(cov[holdout], weeks[holdout]), 4),
                "cov_d01": round(float(cov[d01].mean()), 4) if d01.any() else float("nan"),
                "cov_d2p": round(float(cov[d2p].mean()), 4) if d2p.any() else float("nan"),
                "n_d01": int(d01.sum()), "n_d2p": int(d2p.sum()),
            }
            rows.append(rec)
            if impl != "reference_pid":
                continue
            scope = f"{dom} h{h}"
            coverage = float(cov[holdout].mean())
            roll13 = rolling_min_cov(cov[holdout], weeks[holdout])
            run_len = longest_miss_run(cov[holdout])
            crits.append(Criterion("1 long-run coverage (sanity)", scope,
                                   round(coverage, 4), "reported only", True))
            crits.append(Criterion("2 min rolling 13-week coverage", scope,
                                   round(roll13, 4), f">= {ROLL13_FLOOR}",
                                   bool(roll13 >= ROLL13_FLOOR)))
            for label, sel in (("D0-D1", d01), ("D2+", d2p)):
                val = float(cov[sel].mean()) if sel.any() else float("nan")
                # A stratum with no rows cannot fail a test it was not measured on.
                ok = (
                    True if not sel.any() or not np.isfinite(val)
                    else abs(val - COND_COVERAGE_TARGET) <= COND_COVERAGE_TOL
                )
                crits.append(Criterion(f"3 coverage | {label}", scope, round(val, 4),
                                       f"within {COND_COVERAGE_TOL} of {COND_COVERAGE_TARGET}", ok))
            crits.append(Criterion("4 longest miss run", scope, float(run_len),
                                   f"<= {MISS_RUN_BOUND}",
                                   bool(run_len <= MISS_RUN_BOUND)))
    return rows, crits


def reliability_tests(frame: pd.DataFrame, st: Settings, dom: str) -> tuple[list[dict[str, object]], list[dict[str, object]], list[Criterion]]:
    """Test 5 and the diagram of test 6, per shipped probabilistic target."""
    from cofire.model.shipping import load as load_choices

    choices = load_choices(out_dir=Path("artifacts/rerun_a"))
    t = pd.to_datetime(frame["time"])
    train = frame[t <= pd.Timestamp(st.train_end)]
    hold = frame[t.dt.year == HOLDOUT_YEAR]

    rows: list[dict[str, object]] = []
    diagram: list[dict[str, object]] = []
    crits: list[Criterion] = []
    for (target, h), c in sorted(choices.items()):
        if target not in hold.columns:
            continue
        y = pd.to_numeric(hold[target], errors="coerce").to_numpy(float)
        if not np.isfinite(y).any():
            continue
        pred = (
            _drought_prediction(h, train, target, hold)
            if c.family == "markov"
            else _fire_prediction(c.family, train, target, hold)
        )
        m = np.isfinite(pred) & np.isfinite(y)
        if m.sum() < 100:
            continue
        dec = brier_decomposition(pred[m], y[m])
        rel = float(dec["reliability"])
        n_pos_weeks = int(
            pd.DataFrame({"w": pd.to_datetime(hold["time"]).to_numpy()[m], "y": y[m]})
            .groupby("w")["y"].max().gt(0).sum()
        )
        rows.append(
            {
                "domain": dom, "target": target, "horizon": h, "family": c.family,
                "n": int(m.sum()), "n_positive_weeks": n_pos_weeks,
                "base_rate": round(float(y[m].mean()), 5),
                "brier": round(brier(pred[m], y[m]), 5),
                "reliability": round(rel, 6),
                "resolution": round(float(dec["resolution"]), 6),
            }
        )
        crits.append(
            Criterion("5 reliability term", f"{dom} {target}", round(rel, 6),
                      f"<= {RELIABILITY_MAX}", bool(np.isfinite(rel) and rel <= RELIABILITY_MAX))
        )
        frac, mean_pred = reliability_sklearn(pred[m], y[m], n_bins=10)
        for obs, exp in zip(frac.tolist(), mean_pred.tolist(), strict=True):
            diagram.append(
                {"domain": dom, "target": target, "horizon": h,
                 "forecast": round(exp, 5), "observed": round(obs, 5)}
            )
    return rows, diagram, crits


def width_ratio_2026(frame: pd.DataFrame, st: Settings, dom: str) -> list[dict[str, object]]:
    """Test 7: reported with its CI, and by rule it changes no rendering."""
    from cofire.model.calibration_stages import arms
    from cofire.model.shipping import climatological_width
    from cofire.model.stats_lib import circular_block_bootstrap

    arm_by_h = arms()
    t = pd.to_datetime(frame["time"])
    train = frame[t <= pd.Timestamp(st.train_end)]
    stream = frame[t >= pd.Timestamp(st.valid_start)].sort_values(["time", "cell_id"])
    rows: list[dict[str, object]] = []
    for h in HORIZONS:
        arm = arm_by_h[str(h)]
        y = pd.to_numeric(stream[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
        p = continuous_predict(arm, train, h, stream)
        ww = climatological_width(train, h, stream)
        k = np.isfinite(y) & np.isfinite(p) & np.isfinite(ww)
        s = np.abs(y[k] - p[k])
        weeks = pd.to_datetime(stream["time"]).to_numpy()[k]
        q = run_reference_pid(s).radii
        hold = pd.DatetimeIndex(weeks).year == HOLDOUT_YEAR
        if not hold.any():
            continue
        qh, wh, weeks_h = q[hold], ww[k][hold], weeks[hold]

        def ratio(sel: np.ndarray, qh: np.ndarray = qh, wh: np.ndarray = wh,
                  weeks_h: np.ndarray = weeks_h) -> float:
            m = np.isin(weeks_h, sel)
            if not m.any() or np.mean(wh[m]) <= 0:
                return float("nan")
            return float(2 * np.mean(qh[m]) / np.mean(wh[m]))

        res = circular_block_bootstrap(
            ratio, weeks_h, np.ones_like(qh), n_boot=400, min_positive_weeks=0
        )
        rows.append(
            {
                "domain": dom, "horizon": h,
                "pid_width": round(float(2 * np.mean(qh)), 2),
                "clim_width": round(float(np.mean(wh)), 2),
                "ratio": round(res.point, 4),
                "ratio_lo": round(res.lo, 4), "ratio_hi": round(res.hi, 4),
            }
        )
    return rows


def run() -> Path:
    """The look. Everything is computed before anything is written."""
    if os.environ.get("COFIRE_ALLOW_LOOK", "").strip() != "3":
        raise SystemExit(
            "look 3 on the sealed 2026 holdout requires COFIRE_ALLOW_LOOK=3. "
            "See docs/PREREGISTRATION_LOOK3.md."
        )

    prereg = Path("docs/PREREGISTRATION_LOOK3.md")
    import hashlib

    prereg_sha = hashlib.sha256(prereg.read_bytes()).hexdigest()
    freeze_commit = (
        Path("artifacts/FREEZE_COMMIT").read_text().strip()
        if Path("artifacts/FREEZE_COMMIT").exists()
        else ""
    )
    cfg_in_doc = ""
    for line in prereg.read_text().splitlines():
        if "**Config hash** sha256" in line:
            cfg_in_doc = line.split("`")[1]
            break

    report = freeze_conditions(freeze_commit, cfg_in_doc)
    LOGGER.info("preconditions:\n%s", report.render())
    if not report.ok:
        raise SystemExit(
            "preconditions for look 3 are not met; the look is not taken:\n"
            + report.render()
        )

    cov_rows: list[dict[str, object]] = []
    rel_rows: list[dict[str, object]] = []
    diagram: list[dict[str, object]] = []
    ratio_rows: list[dict[str, object]] = []
    crits: list[Criterion] = []
    for dom in DOMAINS:
        frame, st = build_holdout(dom)
        n_2026 = int((pd.to_datetime(frame["time"]).dt.year == HOLDOUT_YEAR).sum())
        LOGGER.info("%s: %d holdout rows built", dom, n_2026)
        if n_2026 == 0:
            raise SystemExit(f"{dom}: no {HOLDOUT_YEAR} rows were built")
        c_rows, c_crits = interval_tests(frame, st, dom)
        r_rows, r_diag, r_crits = reliability_tests(frame, st, dom)
        cov_rows += c_rows
        rel_rows += r_rows
        diagram += r_diag
        ratio_rows += width_ratio_2026(frame, st, dom)
        crits += c_crits + r_crits

    # Everything computed. Write once.
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cov_rows).to_csv(OUT / "coverage.csv", index=False)
    pd.DataFrame(rel_rows).to_csv(OUT / "reliability.csv", index=False)
    pd.DataFrame(diagram).to_csv(OUT / "reliability_diagram.csv", index=False)
    pd.DataFrame(ratio_rows).to_csv(OUT / "width_ratio.csv", index=False)
    pd.DataFrame([asdict(c) for c in crits]).to_csv(OUT / "criteria.csv", index=False)

    cfg = config_hash()
    n_looks = record_look(HOLDOUT_YEAR, cfg, "look 3, preregistered confirmatory tests")
    (OUT / "provenance.json").write_text(
        json.dumps(
            {
                "holdout_year": HOLDOUT_YEAR,
                "look_index": n_looks,
                "config_hash": cfg,
                "preregistration_sha256": prereg_sha,
                "freeze_commit": freeze_commit,
                "criteria_passed": int(sum(c.passed for c in crits)),
                "criteria_total": len(crits),
            },
            indent=2,
        )
    )
    failed = [c for c in crits if not c.passed]
    LOGGER.info(
        "look %d recorded. %d of %d criteria pass.%s",
        n_looks, len(crits) - len(failed), len(crits),
        "" if not failed else "\nFAILED:\n" + "\n".join(
            f"  {c.name} [{c.scope}]: {c.observed} (needed {c.threshold})" for c in failed
        ),
    )
    return OUT


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
