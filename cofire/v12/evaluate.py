"""Shared scoring for every v1.2 stage: metrics, selection, the paired test
against configuration A, multiplicity and the adoption rule.

Input is a long table per domain (one row per held-out cell-week and target)
with columns domain, target, time, y, A and one column per arm. Everything
follows docs/PREREGISTRATION_V12.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.v12 import common  # noqa: E402

RELIABILITY_MAX = 0.05
STRONG_BSS = 0.10


def metrics_one(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    from cofire.model.prob_metrics import brier, brier_decomposition

    m = np.isfinite(p) & np.isfinite(y)
    if m.sum() < 100:
        return {"brier": float("nan"), "reliability": float("nan"), "resolution": float("nan"), "n": int(m.sum())}
    d = brier_decomposition(p[m], y[m])
    return {"brier": brier(p[m], y[m]), "reliability": float(d["reliability"]),
            "resolution": float(d["resolution"]), "n": int(m.sum())}


def metrics(tables: dict[str, Path], arms: list[str]) -> pd.DataFrame:
    rows = []
    for d, path in tables.items():
        f = pd.read_parquet(path, columns=["target", "y", "A", *arms])
        for target, g in f.groupby("target"):
            y = g["y"].to_numpy(float)
            for arm in ["A", *arms]:
                rows.append({"domain": d, "target": target, "arm": arm, **metrics_one(g[arm].to_numpy(float), y)})
    return pd.DataFrame(rows)


def select(met: pd.DataFrame, families: dict[str, list[str]], pairs_filter: Any = None) -> tuple[dict[str, str], pd.Series]:
    """Per family, the member with the lowest pooled Brier averaged with equal
    weight over every pair it applies to."""
    m = met if pairs_filter is None else met[pairs_filter(met)]
    mean = m.groupby("arm")["brier"].mean()
    return {fam: min(members, key=lambda k: mean[k]) for fam, members in families.items()}, mean


def paired_job(args: tuple[str, str, str, str, int]) -> dict[str, Any]:
    from cofire.model.prob_metrics import brier
    from cofire.model.stats_lib import bootstrap_pvalue, paired_bss_shuffled

    path, domain, target, arm, n_shuffles = args
    f = pd.read_parquet(path, columns=["target", "time", "y", "A", arm])
    f = f[f["target"] == target]
    yy, pa, pq = f["y"].to_numpy(float), f["A"].to_numpy(float), f[arm].to_numpy(float)
    res = paired_bss_shuffled(pq, pa, yy, pd.to_datetime(f["time"]).to_numpy(), n_boot=400,
                              n_shuffles=n_shuffles, seed=common.SEED)
    m = np.isfinite(yy) & np.isfinite(pa) & np.isfinite(pq)
    real = 1 - brier(pq[m], yy[m]) / brier(pa[m], yy[m]) if m.any() and brier(pa[m], yy[m]) > 0 else float("nan")
    return {"domain": domain, "target": target, "arm": arm, "n_shuffles": n_shuffles,
            "n_positive_weeks": res.n_positive_weeks, "estimable": bool(res.estimable),
            "paired_diff": res.point, "paired_lo": res.lo, "paired_hi": res.hi,
            "pvalue": bootstrap_pvalue(res), "bss_real_vs_A": real}


def run_paired(jobs: list[tuple[str, str, str, str, int]], workers: int = 6) -> pd.DataFrame:
    import multiprocessing as mp

    if not jobs:
        return pd.DataFrame()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers) as pool:
        return pd.DataFrame(pool.map(paired_job, jobs, chunksize=1))


def multiplicity(df: pd.DataFrame) -> pd.DataFrame:
    """BH at q = 0.10 across the arm's estimable pairs, Holm within domain and family."""
    from cofire.model.multiplicity import ALPHA_HOLM, Q, family_of
    from cofire.model.stats_lib import multipletests_bh, multipletests_holm

    df = df.copy().reset_index(drop=True)
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


def adoption(tests: pd.DataFrame, met: pd.DataFrame, tables: dict[str, Path]) -> pd.DataFrame:
    """The owner's rule, plus the 100-shuffle rerun of surprisingly strong pairs."""
    tests = pd.concat([multiplicity(g) for _a, g in tests.groupby("arm")], ignore_index=True)
    tests = tests.merge(met, on=["domain", "target", "arm"], how="left")
    a = met[met["arm"] == "A"].set_index(["domain", "target"])
    tests["brier_A"] = [a["brier"].get((d, t), np.nan) for d, t in zip(tests["domain"], tests["target"], strict=True)]
    tests["reliability_A"] = [a["reliability"].get((d, t), np.nan) for d, t in zip(tests["domain"], tests["target"], strict=True)]
    tests["reliability_no_worse"] = tests["reliability"] <= tests["reliability_A"]
    tests["qualifies"] = (tests["estimable"].astype(bool) & tests["ci_above_zero"] & tests["bh_reject"]
                          & tests["holm_reject"] & tests["reliability_no_worse"])
    strong = tests[tests["qualifies"] & (tests["bss_real_vs_A"] > STRONG_BSS)]
    rerun = run_paired([(str(tables[r.domain]), r.domain, r.target, r.arm, 100) for r in strong.itertuples()])
    tests["paired_lo_100"] = np.nan
    tests["paired_diff_100"] = np.nan
    for r in rerun.itertuples() if len(rerun) else []:
        m = (tests["domain"] == r.domain) & (tests["target"] == r.target) & (tests["arm"] == r.arm)
        tests.loc[m, "paired_diff_100"] = r.paired_diff
        tests.loc[m, "paired_lo_100"] = r.paired_lo
        tests.loc[m, "qualifies"] = tests.loc[m, "qualifies"] & (r.paired_lo > 0)
    return tests


def current_rendering() -> pd.DataFrame:
    """Each pair's live rendering state and reason, from the newest bundle."""
    import json

    from cofire.ship import domains

    root = Path("artifacts/ship/domains")
    issue = json.loads((root / "index.json").read_text())["issues"][-1]
    rows = []
    for d in domains.ORDER:
        b = json.loads((root / d / f"{issue}.json").read_text())
        for t, (state, reason) in b["decisions"]["targets"].items():
            rows.append({"domain": d, "target": t, "state": state, "reason": reason or ""})
    return pd.DataFrame(rows)


def moving_to_per_cell(adopted: pd.DataFrame) -> pd.DataFrame:
    """h4 and h8 pairs on the regional base rate today because of reliability
    that an adopted arm would render as per-cell odds."""
    cur = current_rendering()
    val = pd.read_csv("artifacts/v11/survivors_v11.csv")[["domain", "target", "n_positive_weeks"]].rename(
        columns={"n_positive_weeks": "validation_positive_weeks"})
    fail = cur[(cur["state"] == "base_rate") & cur["reason"].str.contains("reliability")
               & cur["target"].str.endswith(("_h4", "_h8"))]
    m = fail.merge(adopted, on=["domain", "target"]).merge(val, on=["domain", "target"], how="left")
    return m[(m["reliability"] <= RELIABILITY_MAX) & (m["validation_positive_weeks"] >= 12)]


def base_rate_reliability_pairs() -> pd.DataFrame:
    cur = current_rendering()
    return cur[(cur["state"] == "base_rate") & cur["reason"].str.contains("reliability")
               & cur["target"].str.endswith(("_h4", "_h8"))]
