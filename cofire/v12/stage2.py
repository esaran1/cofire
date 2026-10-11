"""v1.2 Stage 2: the event rate from slow climate state, as a logit offset.

    python -m cofire.v12.stage2 predict <domain>   # checkpointed per domain
    python -m cofire.v12.stage2 report

Fixed specification (docs/PREREGISTRATION_V12.md): one ridge-penalized
logistic per target, horizon and domain on domain-week event counts, with
ONI, PDO, April 1 SWE as percent of median (April to October issue weeks, 0
otherwise) and the season, standardized on the fold's training weeks.
Ridge weight chosen once from 0.1, 1, 10, 100 on the pooled folds.

    S2-offset     sigmoid(logit p_A + logit r_hat - logit r_A)
    S2-offset+S1  S2-offset, then the static stage-1 variant selected in
                  stage 1, warm-started on nested out-of-fold S2-offset
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
from scipy.optimize import minimize  # noqa: E402

from cofire.v12 import common, preds, recal, snotel  # noqa: E402

LOGGER = logging.getLogger("cofire.v12.stage2")
OUT = common.OUT / "stage2"
PRED = common.DATA / "stage2"
LAMBDAS = (0.1, 1.0, 10.0, 100.0)
PREDICTORS = ("oni", "pdo", "swe", "sin_doy", "cos_doy")


def climate(times: pd.Series) -> pd.DataFrame:
    """ONI and PDO as published by each issue date: a month's value is
    available from the 15th of the following month."""
    ci = pd.read_parquet("data/cache/climate_indices.parquet")
    ci["available"] = (pd.to_datetime(ci["time"]) + pd.offsets.MonthBegin(1) + pd.Timedelta(days=14)).astype("datetime64[ns]")
    t = pd.DataFrame({"time": pd.to_datetime(times.unique()).astype("datetime64[ns]")}).sort_values("time")
    out = t.copy()
    for col in ("oni", "pdo"):
        s = ci.dropna(subset=[col]).sort_values("available")[["available", col]]
        out = pd.merge_asof(out, s, left_on="time", right_on="available", direction="backward").drop(columns="available")
    doy = out["time"].dt.dayofyear.to_numpy(float)
    out["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    out["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    return out


def swe_percent(domain: str, training_years: tuple[int, ...]) -> dict[int, float]:
    """Domain April 1 SWE as percent of median, per year. Each station's median
    is from its own April 1 values in `training_years`."""
    st = json.loads(snotel.STATIONS.read_text())["domains"][domain]["stations"]
    a = pd.read_csv(snotel.APR1)
    a = a[a["station"].isin(st)].dropna(subset=["swe_in"])
    med = a[a["year"].isin(training_years)].groupby("station")["swe_in"].median()
    a = a[a["station"].isin(med[med > 0].index)].copy()
    a["pct"] = 100.0 * a["swe_in"] / a["station"].map(med)
    return {int(y): float(v) for y, v in a.groupby("year")["pct"].mean().items()}


def design(weeks: pd.DataFrame, swe: dict[int, float]) -> pd.DataFrame:
    d = weeks.copy()
    t = pd.to_datetime(d["time"])
    warm = t.dt.month.between(4, 10)
    d["swe"] = np.where(warm, t.dt.year.map(swe).astype(float), 0.0)
    return d


def fit_ridge(x: np.ndarray, k: np.ndarray, n: np.ndarray, lam: float) -> np.ndarray:
    """Mean per-cell binomial deviance over domain-weeks + lam * ||beta||^2
    (intercept unpenalized). Columns of x are already standardized."""
    X = np.column_stack([np.ones(len(x)), x])
    w = 1.0 / len(x)

    def f(b: np.ndarray) -> tuple[float, np.ndarray]:
        z = X @ b
        r = recal.sigmoid(z)
        rr = np.clip(r, 1e-9, 1 - 1e-9)
        frac = k / n
        dev = -2 * (frac * np.log(rr) + (1 - frac) * np.log(1 - rr))
        g = 2 * X.T @ ((r - frac) * w)
        pen = lam * float(b[1:] @ b[1:])
        gp = np.concatenate([[0.0], 2 * lam * b[1:]])
        return float(dev.sum() * w) + pen, g + gp

    rate = np.clip(k.sum() / n.sum(), 1e-4, 1 - 1e-4)
    b0 = np.zeros(X.shape[1])
    b0[0] = np.log(rate / (1 - rate))
    return np.asarray(minimize(f, b0, jac=True, method="L-BFGS-B").x, dtype=float)


def domain_weeks(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    y = pd.to_numeric(frame[target], errors="coerce")
    g = frame.assign(_y=y).dropna(subset=["_y"]).groupby("time")["_y"].agg(["sum", "count"]).reset_index()
    g["time"] = pd.to_datetime(g["time"]).astype("datetime64[ns]")
    return g.rename(columns={"sum": "k", "count": "n"})


class LevelModel:
    """Standardize on training weeks, fit, predict r_hat for any weeks."""

    def __init__(self, train_weeks: pd.DataFrame, lam: float) -> None:
        x = train_weeks[list(PREDICTORS)].to_numpy(float)
        self.mu = np.nanmean(x, axis=0)
        sd = np.nanstd(x, axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        xs = np.nan_to_num((x - self.mu) / self.sd)
        self.beta = fit_ridge(xs, train_weeks["k"].to_numpy(float), train_weeks["n"].to_numpy(float), lam)

    def predict(self, weeks: pd.DataFrame) -> np.ndarray:
        x = np.nan_to_num((weeks[list(PREDICTORS)].to_numpy(float) - self.mu) / self.sd)
        return recal.sigmoid(self.beta[0] + x @ self.beta[1:])


def _train_weeks(g: pd.DataFrame, excluded: tuple[int, ...], target: str, h: int) -> pd.DataFrame:
    gy = pd.to_datetime(g["time"]).dt.year
    fit = common.embargo_many(g[~gy.isin(excluded)], excluded, h)
    return domain_weeks(fit, target)


def predict(domain: str) -> Path:
    """Held-out rows: the S2 rate, S2-offset and S2-offset+S1 (both static
    variants), for every ridge weight. Nested warm starts are fitted in place
    and only their parameters kept."""
    from cofire.model.targets import HORIZONS, target_names

    dest = PRED / f"{domain}.parquet"
    if dest.exists():
        return dest
    common.assert_looks()
    period = common.record(domain)
    clim = climate(period["time"])
    parts_dir = PRED / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    for Y in common.FOLDS:
        part = parts_dir / f"{domain}_{Y}.parquet"
        if part.exists():
            continue  # checkpointed: a killed run resumes at the next fold
        out_rows: list[pd.DataFrame] = []
        warm: list[dict[str, Any]] = []
        f = pd.read_parquet(preds.path(domain, Y))
        train_years = tuple(y for y in common.YEARS if y != Y)
        g = common.frame_without(period, (Y,))
        cw = design(clim, swe_percent(domain, train_years))
        cw_t = cw.set_index("time")
        inner_years = [y for y in common.YEARS if y != Y]
        inner_frames = {y: common.frame_without(period, (Y, y)) for y in inner_years}
        inner_cw = {y: design(clim, swe_percent(domain, tuple(z for z in train_years if z != y))) for y in inner_years}
        outer_all = f[f["role"] == "outer"]
        inner_all = f[f["role"] == "inner"]
        for h in HORIZONS:
            for target in target_names((h,)):
                tw = _train_weeks(g, (Y,), target, h).merge(cw, on="time")
                outer = outer_all[["time", "cell_id", f"p__{target}", f"y__{target}"]].copy()
                outer.columns = ["time", "cell_id", "A", "y"]
                outer["time"] = pd.to_datetime(outer["time"]).astype("datetime64[ns]")
                lA = recal.logit(outer["A"].to_numpy(float))
                rA = outer.groupby("time")["A"].transform("mean").to_numpy(float)
                res = outer.assign(domain=domain, fold=Y, target=target)
                inner = inner_all[["time", "year", f"p__{target}", f"y__{target}"]].copy()
                inner.columns = ["time", "year", "A", "y"]
                inner["time"] = pd.to_datetime(inner["time"]).astype("datetime64[ns]")
                inner_tw = {y: _train_weeks(gi, (Y, y), target, h).merge(inner_cw[y], on="time")
                            for y, gi in inner_frames.items()}
                for lam in LAMBDAS:
                    ok = len(tw) >= 50 and tw["k"].sum() > 0
                    rate = (LevelModel(tw, lam).predict(cw_t.loc[pd.to_datetime(outer["time"])].reset_index())
                            if ok else np.full(len(outer), np.nan))
                    s2 = recal.sigmoid(lA + recal.logit(rate) - recal.logit(rA))
                    res[f"rhat@{lam}"] = rate.astype("float32")
                    res[f"S2-offset@{lam}"] = s2.astype("float32")
                    # Nested S2-offset on each inner year, from a level model fitted without Y and y.
                    q_in = np.full(len(inner), np.nan)
                    for y in inner_years:
                        sel = (inner["year"] == y).to_numpy()
                        twi = inner_tw[y]
                        if not sel.any() or len(twi) < 50 or twi["k"].sum() == 0:
                            continue
                        wk = inner_cw[y].set_index("time").loc[pd.to_datetime(inner.loc[sel, "time"])].reset_index()
                        ri = LevelModel(twi, lam).predict(wk)
                        sub = inner.loc[sel]
                        rAi = sub.groupby("time")["A"].transform("mean").to_numpy(float)
                        q_in[sel] = recal.sigmoid(recal.logit(sub["A"].to_numpy(float)) + recal.logit(ri) - recal.logit(rAi))
                    yi = inner["y"].to_numpy(float)
                    th_a = recal.fit_static(q_in, yi, slope=False)
                    th_ab = recal.fit_static(q_in, yi, slope=True)
                    res[f"S2+S1-static-a@{lam}"] = recal.apply(th_a, s2).astype("float32")
                    res[f"S2+S1-static-ab@{lam}"] = recal.apply(th_ab, s2).astype("float32")
                    warm.append({"domain": domain, "fold": Y, "target": target, "lambda": lam,
                                 "a_only": th_a[0], "a": th_ab[0], "b": th_ab[1]})
                res["train_rate"] = np.float32(tw["k"].sum() / tw["n"].sum() if len(tw) else np.nan)
                out_rows.append(res)
        pd.concat(out_rows, ignore_index=True).to_parquet(part.with_suffix(".part"), index=False)
        part.with_suffix(".part").replace(part)
        pd.DataFrame(warm).to_csv(parts_dir / f"warm_{domain}_{Y}.csv", index=False)
        LOGGER.info("%s fold %d done", domain, Y)
    frame = pd.concat([pd.read_parquet(parts_dir / f"{domain}_{Y}.parquet") for Y in common.FOLDS], ignore_index=True)
    frame.to_parquet(dest, index=False)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.concat([pd.read_csv(parts_dir / f"warm_{domain}_{Y}.csv") for Y in common.FOLDS]).to_csv(
        OUT / f"warm_start_{domain}.csv", index=False)
    common.assert_looks()
    return dest


def report() -> dict[str, Any]:
    from cofire.model.prob_metrics import brier
    from cofire.ship import domains
    from cofire.v12 import evaluate

    common.assert_looks()
    s1 = json.loads((common.OUT / "stage1" / "summary.json").read_text())
    static = s1["static_eligible_arm"].replace("S1-", "")
    tables = {d: PRED / f"{d}.parquet" for d in domains.ORDER}
    offset = [f"S2-offset@{lam}" for lam in LAMBDAS]
    combo = [f"S2+S1-{static}@{lam}" for lam in LAMBDAS]
    met = evaluate.metrics(tables, offset + combo)
    OUT.mkdir(parents=True, exist_ok=True)
    met.to_csv(OUT / "metrics_all_variants.csv", index=False)

    # The ridge weight is chosen once, on S2-offset; S2+S1 uses the same weight.
    selected, mean = evaluate.select(met, {"S2-offset": offset})
    lam = selected["S2-offset"].split("@")[1]
    arms = [f"S2-offset@{lam}", f"S2+S1-{static}@{lam}"]
    pairs = met[met["arm"] == "A"][["domain", "target"]].drop_duplicates()
    jobs = [(str(tables[d]), d, t, arm, 20) for arm in arms for d, t in pairs.itertuples(index=False)]
    tests = evaluate.adoption(evaluate.run_paired(jobs), met, tables)
    # Within the stage, the larger paired difference wins a pair both arms qualify for.
    tests["adopted"] = False
    for (_d, _t), g in tests[tests["qualifies"]].groupby(["domain", "target"]):
        tests.loc[g["paired_diff"].idxmax(), "adopted"] = True
    tests.to_csv(OUT / "paired_tests.csv", index=False)

    # Base-rate cost recovered, by the oracle decomposition's definitions.
    rec = []
    for d, path in tables.items():
        f = pd.read_parquet(path, columns=["fold", "target", "y", "train_rate", f"rhat@{lam}"])
        for target, g in f.groupby("target"):
            m = g["y"].notna() & g[f"rhat@{lam}"].notna() & g["train_rate"].notna()
            g = g[m]
            if g.empty:
                continue
            y = g["y"].to_numpy(float)
            true = g.groupby("fold")["y"].transform("mean").to_numpy(float)
            b_train = brier(g["train_rate"].to_numpy(float), y)
            b_oracle = brier(true, y)
            b_rhat = brier(g[f"rhat@{lam}"].to_numpy(float), y)
            cost = b_train - b_oracle
            rec.append({"domain": d, "target": target, "brier_train_constant": b_train,
                        "brier_oracle_constant": b_oracle, "brier_rhat_constant": b_rhat,
                        "base_rate_cost": cost,
                        "recovered": (b_train - b_rhat) / cost if cost > 1e-9 else np.nan})
    recovered = pd.DataFrame(rec)
    recovered.to_csv(OUT / "base_rate_recovered.csv", index=False)
    moving = evaluate.moving_to_per_cell(tests[tests["adopted"]])
    summary = {
        "lambda_selected": float(lam), "static_stage1_arm": s1["static_eligible_arm"],
        "pooled_mean_brier": {k: round(float(v), 6) for k, v in met.groupby("arm")["brier"].mean().items()},
        "estimable": {a: int(g["estimable"].astype(bool).sum()) for a, g in tests.groupby("arm")},
        "ci_above_zero": {a: int(g["ci_above_zero"].sum()) for a, g in tests.groupby("arm")},
        "qualifying": {a: int(g["qualifies"].sum()) for a, g in tests.groupby("arm")},
        "adopted": int(tests["adopted"].sum()),
        "median_recovered": float(recovered["recovered"].median()),
        "pairs_with_positive_recovery": int((recovered["recovered"] > 0).sum()),
        "pairs_recovery_estimated": int(recovered["recovered"].notna().sum()),
        "base_rate_h4_h8_moving_to_per_cell": int(len(moving)),
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
