"""Which arm is live for each target, and the live parameters of adopted arms.

The adoption rule (docs/PREREGISTRATION_V12.md) is applied to every stage's
report; a pair that qualifies in two stages goes to the larger paired
difference. Only static stage-1 recalibration can be adopted before the
2027-01-12 unseal, because an online arm would update on 2026 outcomes.

A live static recalibration is fitted on the shipped configuration A's
predictions for 2022 to 2025, years the shipped model was not trained on, and
written with its fit window (scope: calibration). It applies only to issues
published after adoption (`applies_from`), so no published forecast changes.

    python -m cofire.v12.live adopt
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from cofire.v12 import common, recal

LOGGER = logging.getLogger("cofire.v12.live")
LIVE = common.OUT / "live_arms.json"
FIT_START, FIT_END = pd.Timestamp("2022-01-01"), pd.Timestamp("2025-12-31")
TRAIN_END = pd.Timestamp("2021-12-31")


def adoptions() -> pd.DataFrame:
    """Every adopted pair across the stage reports, conflicts resolved."""
    rows = []
    for stage in (1, 2, 3):
        p = common.OUT / f"stage{stage}" / "paired_tests.csv"
        if not p.exists():
            raise RuntimeError(f"stage {stage} has not reported")
        t = pd.read_csv(p)
        a = t[t["adopted"].astype(bool)].assign(stage=stage)
        rows.append(a[["stage", "domain", "target", "arm", "paired_diff", "paired_lo", "paired_hi", "reliability", "reliability_A"]])
    allrows = pd.concat(rows, ignore_index=True)
    if allrows.empty:
        return allrows
    return allrows.loc[allrows.groupby(["domain", "target"])["paired_diff"].idxmax()].reset_index(drop=True)


def shipped_predictions(domain: str, target: str, h: int, lo: pd.Timestamp, hi: pd.Timestamp) -> tuple[np.ndarray, np.ndarray]:
    """The shipped configuration A (trained 2007 to 2021, embargoed) predicting `lo` to `hi`."""
    from cofire.ship import build_v11, fit_v11

    f = build_v11.load(domain)
    f = f[f["time"] <= FIT_END].reset_index(drop=True)
    g = fit_v11.with_targets(f, pd.to_numeric(f["erc_pct"], errors="coerce").to_numpy(float))
    train = fit_v11.embargo(g[g["time"] <= TRAIN_END], TRAIN_END + pd.Timedelta(days=1), h)
    rows = g[(g["time"] >= lo) & (g["time"] <= hi)]
    fam = fit_v11.load_choices(domain)[(target, h)].family
    p = fit_v11.predict_event(fam, h, train, target, rows)
    y = pd.to_numeric(rows[target], errors="coerce").to_numpy(float)
    return np.asarray(p, dtype=float), y


def adopt(applies_from: str) -> dict[str, Any]:
    from cofire.model.fit_window import THROUGH_CALIBRATION, FitWindow, checked_load, write_sidecar

    common.assert_looks()
    ad = adoptions()
    entries = []
    for r in ad.itertuples():
        if not str(r.arm).startswith("S1-static"):
            raise RuntimeError(f"{r.domain} {r.target}: only static stage-1 arms can go live before the unseal")
        h = int(str(r.target).rsplit("_h", 1)[1])
        p, y = shipped_predictions(str(r.domain), str(r.target), h, FIT_START, FIT_END)
        slope = str(r.arm) == "S1-static-ab"
        a, b = recal.fit_static(p, y, slope=slope)
        entries.append({"domain": r.domain, "target": r.target, "horizon": h, "arm": r.arm, "stage": int(r.stage),
                        "a": a, "b": b, "paired_diff": r.paired_diff, "paired_lo": r.paired_lo,
                        "reliability": r.reliability, "reliability_A": r.reliability_A,
                        "applies_from": applies_from, "n_fit_rows": int(np.isfinite(p * y).sum())})
    LIVE.write_text(json.dumps({"applies_from": applies_from, "fit_window": [str(FIT_START.date()), str(FIT_END.date())],
                                "entries": entries}, indent=1) + "\n")
    write_sidecar(LIVE, FitWindow(date(2022, 1, 1), date(2025, 12, 31), THROUGH_CALIBRATION),
                  "v1.2 live stage-1 recalibration")
    checked_load(LIVE, strict=True)
    common.assert_looks()
    return {"entries": entries}


def load() -> list[dict[str, Any]]:
    """The live adopted arms, through the strict fit-window loader; empty if none."""
    from cofire.model.fit_window import checked_load

    if not LIVE.exists():
        return []
    checked_load(LIVE, strict=True)
    return list(json.loads(LIVE.read_text())["entries"])


def apply(domain: str, target: str, h: int, times: pd.Series, p: np.ndarray, entries: list[dict[str, Any]] | None = None) -> np.ndarray:
    """Configuration A's prediction, or the adopted arm's for issues on or after `applies_from`."""
    for e in entries if entries is not None else load():
        if e["domain"] == domain and e["target"] == target and int(e["horizon"]) == h:
            q = recal.apply((float(e["a"]), float(e["b"])), np.asarray(p, dtype=float))
            on = (pd.to_datetime(times) >= pd.Timestamp(e["applies_from"])).to_numpy()
            return np.where(on, q, p)
    return np.asarray(p, dtype=float)


def survivor_recheck() -> pd.DataFrame:
    """Each adopted pair's survivor status under the leak-free validation test.

    The recalibration evaluated on 2022 to 2023 must not have seen those years,
    so it is fitted on nested out-of-fold predictions from the training years
    (each year predicted by configuration A fitted without it, embargoed, with
    its own percentile pools), then applied to configuration A's validation
    predictions. The pair's p-value replaces its configuration A value in the
    five-domain table, and BH and Holm are rerun over the whole family.
    """
    from cofire.model.multiplicity import ALPHA_HOLM, Q
    from cofire.model.stats_lib import (
        bootstrap_pvalue,
        multipletests_bh,
        multipletests_holm,
        paired_bss_shuffled,
    )
    from cofire.model.targets import fire_transition_baseline, seasonal_climatology_baseline
    from cofire.ship import build_v11, fit_v11

    table = pd.read_csv("artifacts/v11/survivors_v11.csv")
    out = []
    for e in load():
        d, target, h = e["domain"], e["target"], int(e["horizon"])
        f = build_v11.load(d)
        upto = f[f["time"] <= pd.Timestamp("2023-12-31")].reset_index(drop=True)
        g = fit_v11.with_targets(upto, pd.to_numeric(upto["erc_pct"], errors="coerce").to_numpy(float))
        train = g[g["time"] <= TRAIN_END]
        valid = g[g["time"] >= pd.Timestamp("2022-01-01")]
        clean = fit_v11.embargo(train, TRAIN_END + pd.Timedelta(days=1), h)
        fam = fit_v11.load_choices(d)[(target, h)].family
        pv = np.asarray(fit_v11.predict_event(fam, h, clean, target, valid), dtype=float)
        # Nested out-of-fold predictions on the training years only.
        period = f[f["time"] <= TRAIN_END].reset_index(drop=True)
        ps, ys = [], []
        for y in range(2007, 2022):
            gi = common.frame_without(period, (y,))
            yr = pd.to_datetime(gi["time"]).dt.year
            fit = common.embargo_many(gi[yr != y], (y,), h)
            held = gi[yr == y]
            ps.append(np.asarray(fit_v11.predict_event(fam, h, fit, target, held), dtype=float))
            ys.append(pd.to_numeric(held[target], errors="coerce").to_numpy(float))
        th = recal.fit_static(np.concatenate(ps), np.concatenate(ys), slope=str(e["arm"]) == "S1-static-ab")
        q = recal.apply(th, pv)
        yv = pd.to_numeric(valid[target], errors="coerce").to_numpy(float)
        ref = (fire_transition_baseline(clean, target, valid) if target.startswith("f_")
               else seasonal_climatology_baseline(clean, target, valid))
        res = paired_bss_shuffled(q, np.asarray(ref, float), yv, pd.to_datetime(valid["time"]).to_numpy(), n_boot=400, n_shuffles=20)
        t2 = table.copy()
        m = (t2["domain"] == d) & (t2["target"] == target)
        t2.loc[m, ["paired_diff", "paired_lo", "paired_hi", "pvalue"]] = [res.point, res.lo, res.hi, bootstrap_pvalue(res)]
        t2.loc[m, "ci_above_zero"] = bool(np.isfinite(res.lo) and res.lo > 0)
        est = t2["estimable"].astype(bool) & t2["pvalue"].notna()
        t2["bh_reject"] = False
        t2.loc[est, "bh_reject"] = multipletests_bh(t2.loc[est, "pvalue"].tolist(), q=Q)
        t2["holm_reject"] = False
        for _k, grp in t2[est].groupby(["domain", "family"]):
            t2.loc[grp.index, "holm_reject"] = multipletests_holm(grp["pvalue"].tolist(), alpha=ALPHA_HOLM)
        t2["survivor_new"] = t2["estimable"].astype(bool) & t2["ci_above_zero"].astype(bool) & t2["bh_reject"] & t2["holm_reject"]
        row = t2[m].iloc[0]
        others_changed = int((t2.loc[~m, "survivor_new"] != t2.loc[~m, "survivor"].astype(bool)).sum())
        out.append({"domain": d, "target": target, "arm": e["arm"], "warm_a": th[0], "warm_b": th[1],
                    "paired_diff": res.point, "paired_lo": res.lo, "paired_hi": res.hi,
                    "survivor_with_configuration_A": bool(table.loc[m, "survivor"].iloc[0]),
                    "survivor_with_live_arm": bool(row["survivor_new"]),
                    "other_pairs_whose_status_changed": others_changed})
    df = pd.DataFrame(out)
    df.to_csv(common.OUT / "live_survivor_recheck.csv", index=False)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if sys.argv[1] == "adopt":
        print(json.dumps(adopt(sys.argv[2]), indent=1, default=str))
    elif sys.argv[1] == "survivors":
        print(survivor_recheck().to_string(index=False))
    else:
        raise SystemExit(__doc__)
