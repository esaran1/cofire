"""v1.2 Stage 1: delayed-feedback logistic recalibration of configuration A.

    python -m cofire.v12.stage1 predict <domain>   # per domain, checkpointed
    python -m cofire.v12.stage1 report             # metrics, selection, tests, adoption

Follows docs/PREREGISTRATION_V12.md exactly. The online variants must pass the
delayed-feedback gate before any of their numbers is written, so `report`
runs the gate first and stops if any variant leaks.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.v12 import common, preds, recal  # noqa: E402

LOGGER = logging.getLogger("cofire.v12.stage1")
OUT = common.OUT / "stage1"
PRED = common.DATA / "stage1"


def horizon_of(target: str) -> int:
    return int(target.rsplit("_h", 1)[1])


def targets_in(frame: pd.DataFrame) -> list[str]:
    return sorted(c[3:] for c in frame.columns if c.startswith("p__"))


def predict(domain: str) -> Path:
    """Every variant's held-out predictions for one domain, all folds."""
    dest = PRED / f"{domain}.parquet"
    if dest.exists():
        return dest
    common.assert_looks()
    rows: list[pd.DataFrame] = []
    warm: list[dict[str, Any]] = []
    for Y in common.FOLDS:
        f = pd.read_parquet(preds.path(domain, Y))
        inner, outer = f[f["role"] == "inner"], f[f["role"] == "outer"]
        outer = outer.sort_values(["time", "cell_id"]).reset_index(drop=True)
        week = pd.factorize(outer["time"], sort=True)[0]
        for target in targets_in(f):
            h = horizon_of(target)
            p_in, y_in = inner[f"p__{target}"].to_numpy(float), inner[f"y__{target}"].to_numpy(float)
            th_a = recal.fit_static(p_in, y_in, slope=False)
            th_ab = recal.fit_static(p_in, y_in, slope=True)
            warm.append({"domain": domain, "fold": Y, "target": target,
                         "a_only": th_a[0], "a": th_ab[0], "b": th_ab[1],
                         "n_inner": int(np.isfinite(p_in * y_in).sum())})
            p = outer[f"p__{target}"].to_numpy(float)
            y = outer[f"y__{target}"].to_numpy(float)
            out = pd.DataFrame({"domain": domain, "fold": Y, "target": target, "time": outer["time"].to_numpy(),
                                "cell_id": outer["cell_id"].to_numpy(), "y": y.astype("float32"),
                                "A": p.astype("float32")})
            for name, v in recal.VARIANTS.items():
                if v == "static-a":
                    q = recal.apply(th_a, p)
                elif v == "static-ab":
                    q = recal.apply(th_ab, p)
                else:
                    assert isinstance(v, recal.Online)
                    q = recal.run_online(v, th_ab if v.slope else th_a, p, y, week, delay=h)
                out[name] = q.astype("float32")
            rows.append(out)
        LOGGER.info("%s fold %d done", domain, Y)
    frame = pd.concat(rows, ignore_index=True)
    PRED.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(dest, index=False)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(warm).to_csv(OUT / f"warm_start_{domain}.csv", index=False)
    common.assert_looks()
    return dest


def _metrics(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    from cofire.model.prob_metrics import brier, brier_decomposition

    m = np.isfinite(p) & np.isfinite(y)
    if m.sum() < 100:
        return {"brier": float("nan"), "reliability": float("nan"), "resolution": float("nan"), "n": int(m.sum())}
    d = brier_decomposition(p[m], y[m])
    return {"brier": brier(p[m], y[m]), "reliability": float(d["reliability"]),
            "resolution": float(d["resolution"]), "n": int(m.sum())}


def paired_job(args: tuple[str, str, str, int]) -> dict[str, Any]:
    """The paired test of one arm against configuration A on one pair."""
    from cofire.model.stats_lib import bootstrap_pvalue, paired_bss_shuffled

    domain, target, arm, n_shuffles = args
    f = pd.read_parquet(PRED / f"{domain}.parquet", columns=["target", "time", "y", "A", arm])
    f = f[f["target"] == target]
    res = paired_bss_shuffled(f[arm].to_numpy(float), f["A"].to_numpy(float), f["y"].to_numpy(float),
                              pd.to_datetime(f["time"]).to_numpy(), n_boot=400, n_shuffles=n_shuffles,
                              seed=common.SEED)
    from cofire.model.prob_metrics import brier

    yy, pa, pq = f["y"].to_numpy(float), f["A"].to_numpy(float), f[arm].to_numpy(float)
    m = np.isfinite(yy) & np.isfinite(pa) & np.isfinite(pq)
    real = 1 - brier(pq[m], yy[m]) / brier(pa[m], yy[m]) if m.any() else float("nan")
    return {"domain": domain, "target": target, "arm": arm, "n_shuffles": n_shuffles,
            "n_positive_weeks": res.n_positive_weeks, "estimable": res.estimable,
            "paired_diff": res.point, "paired_lo": res.lo, "paired_hi": res.hi,
            "pvalue": bootstrap_pvalue(res), "bss_real_vs_A": real}


def run_paired(jobs: list[tuple[str, str, str, int]], workers: int = 4) -> pd.DataFrame:
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    with ctx.Pool(workers) as pool:
        return pd.DataFrame(pool.map(paired_job, jobs, chunksize=1))


def multiplicity(df: pd.DataFrame) -> pd.DataFrame:
    from cofire.model.multiplicity import ALPHA_HOLM, Q, family_of
    from cofire.model.stats_lib import multipletests_bh, multipletests_holm

    df = df.copy()
    est = df["estimable"].astype(bool) & df["pvalue"].notna()
    df["bh_reject"] = False
    if est.any():
        df.loc[est, "bh_reject"] = multipletests_bh(df.loc[est, "pvalue"].tolist(), q=Q)
    df["family"] = df["target"].map(family_of)
    df["holm_reject"] = False
    for _k, grp in df[est].groupby(["domain", "family"]):
        df.loc[grp.index, "holm_reject"] = multipletests_holm(grp["pvalue"].tolist(), alpha=ALPHA_HOLM)
    df["ci_above_zero"] = df["paired_lo"].notna() & (df["paired_lo"] > 0)
    return df


def current_rendering() -> pd.DataFrame:
    """Each pair's live state and reason, from the newest bundle per domain."""
    from cofire.ship import domains

    rows = []
    idx = json.loads(Path("artifacts/ship/domains/index.json").read_text())
    issue = idx["issues"][-1]
    for d in domains.ORDER:
        b = json.loads((Path("artifacts/ship/domains") / d / f"{issue}.json").read_text())
        for t, (state, reason) in b["decisions"]["targets"].items():
            rows.append({"domain": d, "target": t, "state": state, "reason": reason or ""})
    return pd.DataFrame(rows)


def report() -> dict[str, Any]:
    from cofire.ship import domains
    from cofire.v12 import gate

    common.assert_looks()
    failed = [r for r in gate.check_all() if not r.passed]
    if failed:
        r = failed[0]
        raise SystemExit(f"gate failed: {r.name} h{r.horizon} first leaking probe {r.first_leak}")

    # Metrics for every variant and every pair.
    mrows = []
    for d in domains.ORDER:
        f = pd.read_parquet(PRED / f"{d}.parquet")
        for target, g in f.groupby("target"):
            y = g["y"].to_numpy(float)
            for arm in ["A", *recal.VARIANTS]:
                mrows.append({"domain": d, "target": target, "arm": arm, **_metrics(g[arm].to_numpy(float), y)})
    met = pd.DataFrame(mrows)
    OUT.mkdir(parents=True, exist_ok=True)
    met.to_csv(OUT / "metrics_all_variants.csv", index=False)

    # Selection: per family, the grid value with the lowest pooled Brier
    # averaged with equal weight over every pair.
    mean = met.groupby("arm")["brier"].mean()
    selected = {fam: min(members, key=lambda k: mean[k]) for fam, members in recal.FAMILIES.items()}
    static = min(("S1-static-a", "S1-static-ab"), key=lambda k: mean[k])

    # Paired tests for every selected configuration.
    pairs = met[met["arm"] == "A"][["domain", "target"]].drop_duplicates().to_records(index=False)
    jobs = [(str(d), str(t), arm, 20) for arm in sorted(set(selected.values())) for d, t in pairs]
    tests = run_paired(jobs)
    tests = pd.concat([multiplicity(g) for _a, g in tests.groupby("arm")], ignore_index=True)
    tests = tests.merge(met.rename(columns={"arm": "arm"}), on=["domain", "target", "arm"], how="left")
    a_rel = met[met["arm"] == "A"].set_index(["domain", "target"])["reliability"]
    tests["reliability_A"] = [a_rel.get((d, t), np.nan) for d, t in zip(tests["domain"], tests["target"], strict=True)]
    tests["reliability_no_worse"] = tests["reliability"] <= tests["reliability_A"]
    tests["qualifies"] = (tests["estimable"].astype(bool) & tests["ci_above_zero"] & tests["bh_reject"]
                          & tests["holm_reject"] & tests["reliability_no_worse"])

    # Surprisingly strong: rerun with 100 shuffles before the rule is applied.
    strong = tests[tests["qualifies"] & (tests["bss_real_vs_A"] > 0.10)]
    rerun = run_paired([(r.domain, r.target, r.arm, 100) for r in strong.itertuples()]) if len(strong) else pd.DataFrame()
    if len(rerun):
        for r in rerun.itertuples():
            m = (tests["domain"] == r.domain) & (tests["target"] == r.target) & (tests["arm"] == r.arm)
            tests.loc[m, ["paired_diff_100", "paired_lo_100", "paired_hi_100"]] = [r.paired_diff, r.paired_lo, r.paired_hi]
            tests.loc[m, "qualifies"] = tests.loc[m, "qualifies"] & (r.paired_lo > 0)
    tests["eligible_for_adoption"] = tests["arm"] == static
    tests["adopted"] = tests["qualifies"] & tests["eligible_for_adoption"]
    tests.to_csv(OUT / "paired_tests.csv", index=False)

    # Pairs on the regional base rate today because of reliability, at h4 and h8,
    # that the adoption rule would move back to per-cell odds.
    cur = current_rendering()
    val = pd.read_csv("artifacts/v11/survivors_v11.csv")[["domain", "target", "n_positive_weeks"]]
    rel_fail = cur[(cur["state"] == "base_rate") & cur["reason"].str.contains("reliability")]
    rel_fail = rel_fail[rel_fail["target"].str.endswith(("_h4", "_h8"))]
    ad = tests[tests["adopted"]]
    moving = rel_fail.merge(ad, on=["domain", "target"]).merge(val, on=["domain", "target"], how="left",
                                                                 suffixes=("", "_validation"))
    moving = moving[(moving["reliability"] <= 0.05) & (moving["n_positive_weeks_validation"] >= 12)]

    summary = {
        "gate": "every online variant passed at its real delay (h = 2, 4, 8)",
        "selected": selected,
        "static_eligible_arm": static,
        "pooled_mean_brier": {k: round(float(v), 6) for k, v in mean.items()},
        "pairs": int(len(pairs)),
        "estimable": {a: int(g["estimable"].astype(bool).sum()) for a, g in tests.groupby("arm")},
        "qualifying": {a: int(g["qualifies"].sum()) for a, g in tests.groupby("arm")},
        "adopted": int(tests["adopted"].sum()),
        "base_rate_h4_h8_for_reliability_now": int(len(rel_fail)),
        "base_rate_h4_h8_moving_to_per_cell": int(len(moving)),
        "surprisingly_strong_reruns": int(len(rerun)),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    common.assert_looks()
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if sys.argv[1] == "predict":
        print(predict(sys.argv[2]))
    elif sys.argv[1] == "report":
        print(json.dumps(report(), indent=1))
    else:
        raise SystemExit(__doc__)
