"""v1.2 Stage 3: partial pooling of configuration A across the five domains.

    python -m research.v12.stage3 predict      # all domains, checkpointed per fold
    python -m research.v12.stage3 report

Drought (docs/PREREGISTRATION_V12.md): configuration A's Markov estimator with
its support gates and fallback order kept, and only the Dirichlet prior
changed. Each row is centred on the equal-weight mean of the five domains'
normalized rows for the same condition, with strength kappa effective weeks
converted to row counts by the domain's number of cells; kappa from 4, 16, 64,
256.

Fire: the damped logistic's two coefficients shrunk toward a pooled fit (all
five domains, each weighted equally): (1 - w) * own + w * pooled, w from 0,
0.25, 0.5, 0.75, 1. At w = 0 this is configuration A.
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
from cofire.v12 import common  # noqa: E402

LOGGER = logging.getLogger("research.v12.stage3")
OUT = common.OUT / "stage3"
PRED = common.DATA / "stage3"
KAPPAS = (4, 16, 64, 256)
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _keys_counts(mk: Any, frame: pd.DataFrame) -> dict[tuple[Any, ...], tuple[np.ndarray, int]]:
    """Raw row counts and week support for every condition configuration A uses."""
    from cofire.model.targets import N_CATEGORIES, _season

    now = pd.to_numeric(frame["usdm"], errors="coerce").to_numpy(dtype=float)
    fut = pd.to_numeric(frame[f"usdm_h{mk.horizon}"], errors="coerce").to_numpy(dtype=float)
    t = pd.to_datetime(frame["time"])
    ok = np.isfinite(now) & np.isfinite(fut)
    ci = np.clip(np.round(now[ok]), 0, N_CATEGORIES - 1).astype(int)
    fi = np.clip(np.round(fut[ok]), 0, N_CATEGORIES - 1).astype(int)
    mi, wi = t.dt.month.to_numpy()[ok], t.to_numpy()[ok]
    seasons = np.array([_season(m) for m in mi])
    out: dict[tuple[Any, ...], tuple[np.ndarray, int]] = {}
    for c in range(N_CATEGORIES):
        m = ci == c
        out[("cat", c)] = mk._counts_and_support(ci, fi, wi, m)  # noqa: SLF001
        for sea in ("DJF", "MAM", "JJA", "SON"):
            out[("season", c, sea)] = mk._counts_and_support(ci, fi, wi, m & (seasons == sea))  # noqa: SLF001
        for mo in range(1, 13):
            out[("month", c, mo)] = mk._counts_and_support(ci, fi, wi, m & (mi == mo))  # noqa: SLF001
    return out


class PooledMarkov:
    """Configuration A's Markov rows with the prior recentred and strengthened."""

    def __init__(self, own: Any, counts: dict[tuple[Any, ...], tuple[np.ndarray, int]],
                 centres: dict[tuple[Any, ...], np.ndarray], strength_rows: float) -> None:
        from cofire.model.targets import MarkovBaseline

        self.mk = MarkovBaseline(horizon=own.horizon)
        self.mk.global_row = own.global_row
        for key, (cnt, nw) in counts.items():
            if nw < self.mk.min_weeks:
                continue  # configuration A's support gate, unchanged
            centre = centres.get(key, own.global_row)
            post = cnt + centre * strength_rows
            row = np.asarray(post / post.sum(), dtype=float)
            if key[0] == "cat":
                self.mk.by_cat[key[1]] = row
            elif key[0] == "season":
                self.mk.by_cat_season[(key[1], key[2])] = row
            else:
                self.mk.by_cat_month[(key[1], key[2])] = row

    def predict_events(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        return dict(self.mk.predict_events(frame))


def _centres(per_domain: dict[str, dict[tuple[Any, ...], tuple[np.ndarray, int]]], min_weeks: int) -> dict[tuple[Any, ...], np.ndarray]:
    """Equal-weight mean of normalized rows over domains with support for the key."""
    keys = set().union(*[set(v) for v in per_domain.values()])
    out: dict[tuple[Any, ...], np.ndarray] = {}
    for k in keys:
        rows = [c / c.sum() for d in per_domain.values() if k in d
                for c, nw in [d[k]] if nw >= min_weeks and c.sum() > 0]
        if rows:
            out[k] = np.mean(rows, axis=0)
    return out


def _fire_coefs(train: pd.DataFrame, target: str, weight: np.ndarray | None = None) -> tuple[float, float, float] | None:
    """The damped logistic exactly as configuration A fits it, coefficients exposed."""
    from sklearn.linear_model import LogisticRegression

    x = pd.to_numeric(train["erc_pct"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(train[target], errors="coerce").to_numpy(dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 50 or len(np.unique(y[m])) < 2:
        return None
    lr = LogisticRegression(max_iter=400)
    lr.fit(x[m].reshape(-1, 1), y[m], sample_weight=None if weight is None else weight[m])
    return float(lr.intercept_[0]), float(lr.coef_[0, 0]), float(np.nanmedian(x[m]))


def predict_fold(Y: int) -> Path:
    from cofire.model.targets import HORIZONS, MarkovBaseline, target_names
    from cofire.ship import domains, fit_v11

    dest = PRED / f"fold_{Y}.parquet"
    if dest.exists():
        return dest
    common.assert_looks()
    frames, cells = {}, {}
    for d in domains.ORDER:
        period = common.record(d)
        frames[d] = common.frame_without(period, (Y,))
        cells[d] = int(period["cell_id"].nunique())
    held = {d: g[pd.to_datetime(g["time"]).dt.year == Y].reset_index(drop=True) for d, g in frames.items()}
    res = {d: held[d][["time", "cell_id"]].assign(domain=d, fold=Y) for d in domains.ORDER}
    for h in HORIZONS:
        train = {d: common.embargo_many(g[pd.to_datetime(g["time"]).dt.year != Y], (Y,), h) for d, g in frames.items()}
        # Drought.
        own = {d: MarkovBaseline(horizon=h).fit(train[d]) for d in domains.ORDER}
        counts = {d: _keys_counts(own[d], train[d]) for d in domains.ORDER}
        centres = _centres(counts, own[domains.ORDER[0]].min_weeks)
        drought = [t for t in target_names((h,)) if t.startswith("d_")]
        for d in domains.ORDER:
            a = own[d].predict_events(held[d])
            for t in drought:
                res[d][f"y__{t}"] = pd.to_numeric(held[d][t], errors="coerce").to_numpy("float32")
                res[d][f"A__{t}"] = np.asarray(a[t], dtype="float32")
            for k in KAPPAS:
                pk = PooledMarkov(own[d], counts[d], centres, k * cells[d]).predict_events(held[d])
                for t in drought:
                    res[d][f"S3@{k}__{t}"] = np.asarray(pk[t], dtype="float32")
        # Fire.
        for t in [t for t in target_names((h,)) if t.startswith("f_")]:
            pooled_rows = pd.concat([train[d] for d in domains.ORDER], ignore_index=True)
            wts = np.concatenate([np.full(len(train[d]), 1.0 / len(train[d])) for d in domains.ORDER])
            pool = _fire_coefs(pooled_rows, t, wts * len(pooled_rows))
            for d in domains.ORDER:
                fam = fit_v11.load_choices(d)[(t, h)].family
                assert fam == "damped", f"{d} {t}: stage 3 shrinks the damped logistic, live family is {fam}"
                res[d][f"y__{t}"] = pd.to_numeric(held[d][t], errors="coerce").to_numpy("float32")
                res[d][f"A__{t}"] = np.asarray(fit_v11.predict_event("damped", h, train[d], t, held[d]), dtype="float32")
                ownc = _fire_coefs(train[d], t)
                xi = pd.to_numeric(held[d]["erc_pct"], errors="coerce").to_numpy(float)
                if ownc is not None:
                    xi = np.where(np.isfinite(xi), xi, ownc[2])
                for w in WEIGHTS:
                    if ownc is None or pool is None:
                        p = res[d][f"A__{t}"].to_numpy(float)
                    else:
                        b0 = (1 - w) * ownc[0] + w * pool[0]
                        b1 = (1 - w) * ownc[1] + w * pool[1]
                        p = 1.0 / (1.0 + np.exp(-(b0 + b1 * xi)))
                    res[d][f"S3@w{w}__{t}"] = p.astype("float32")
    frame = pd.concat(res.values(), ignore_index=True)
    PRED.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(dest, index=False)
    LOGGER.info("fold %d done", Y)
    common.assert_looks()
    return dest


def long_tables() -> dict[str, Path]:
    """One long table per domain from the fold files, for the shared evaluator."""
    from cofire.ship import domains

    folds = pd.concat([pd.read_parquet(PRED / f"fold_{Y}.parquet") for Y in common.FOLDS], ignore_index=True)
    out: dict[str, Path] = {}
    for d in domains.ORDER:
        f = folds[folds["domain"] == d]
        parts = []
        for t in sorted(c[3:] for c in f.columns if c.startswith("y__")):
            arms = {c.split("__")[0]: f[c] for c in f.columns if c.endswith(f"__{t}") and c.startswith("S3@")}
            part = pd.DataFrame({"domain": d, "fold": f["fold"], "target": t, "time": f["time"],
                                 "y": f[f"y__{t}"], "A": f[f"A__{t}"]})
            for k in KAPPAS:
                part[f"S3-drought@{k}"] = arms.get(f"S3@{k}", np.nan)
            for w in WEIGHTS:
                part[f"S3-fire@{w}"] = arms.get(f"S3@w{w}", np.nan)
            parts.append(part)
        path = PRED / f"{d}.parquet"
        pd.concat(parts, ignore_index=True).to_parquet(path, index=False)
        out[d] = path
    return out


def survivors(kappa: int, w: float) -> pd.DataFrame:
    """The validation survivor test (survivors_v11's protocol) with the stage-3 arm."""
    from cofire.model.erc_pct import erc_percentile_reference
    from cofire.model.multiplicity import ALPHA_HOLM, Q, family_of
    from cofire.model.stats_lib import (
        bootstrap_pvalue,
        multipletests_bh,
        multipletests_holm,
        paired_bss_shuffled,
    )
    from cofire.model.targets import (
        HORIZONS,
        MarkovBaseline,
        fire_transition_baseline,
        seasonal_climatology_baseline,
        target_names,
    )
    from cofire.ship import build_v11, domains, fit_v11

    train_end = pd.Timestamp("2021-12-31")
    frames, valid, cells = {}, {}, {}
    for d in domains.ORDER:
        f = build_v11.load(d)
        upto = f[f["time"] <= pd.Timestamp("2023-12-31")].reset_index(drop=True)
        pct = erc_percentile_reference(upto, (upto["time"] <= train_end).to_numpy())
        g = fit_v11.with_targets(upto, pct)
        frames[d] = g[g["time"] <= train_end]
        valid[d] = g[g["time"] >= pd.Timestamp("2022-01-01")].reset_index(drop=True)
        cells[d] = int(upto["cell_id"].nunique())
    rows = []
    for h in HORIZONS:
        clean = {d: fit_v11.embargo(frames[d], train_end + pd.Timedelta(days=1), h) for d in domains.ORDER}
        own = {d: MarkovBaseline(horizon=h).fit(clean[d]) for d in domains.ORDER}
        counts = {d: _keys_counts(own[d], clean[d]) for d in domains.ORDER}
        centres = _centres(counts, own[domains.ORDER[0]].min_weeks)
        dpred = {d: PooledMarkov(own[d], counts[d], centres, kappa * cells[d]).predict_events(valid[d]) for d in domains.ORDER}
        for t in target_names((h,)):
            fire = t.startswith("f_")
            if fire:
                pooled_rows = pd.concat([clean[d] for d in domains.ORDER], ignore_index=True)
                wts = np.concatenate([np.full(len(clean[d]), 1.0 / len(clean[d])) for d in domains.ORDER])
                pool = _fire_coefs(pooled_rows, t, wts * len(pooled_rows))
            for d in domains.ORDER:
                y = pd.to_numeric(valid[d][t], errors="coerce").to_numpy(float)
                if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
                    continue
                if fire:
                    ownc = _fire_coefs(clean[d], t)
                    xi = pd.to_numeric(valid[d]["erc_pct"], errors="coerce").to_numpy(float)
                    if ownc is None or pool is None:
                        pred = fit_v11.predict_event("damped", h, clean[d], t, valid[d])
                    else:
                        xi = np.where(np.isfinite(xi), xi, ownc[2])
                        b0, b1 = (1 - w) * ownc[0] + w * pool[0], (1 - w) * ownc[1] + w * pool[1]
                        pred = 1.0 / (1.0 + np.exp(-(b0 + b1 * xi)))
                    ref = fire_transition_baseline(clean[d], t, valid[d])
                else:
                    pred = np.asarray(dpred[d][t], dtype=float)
                    ref = seasonal_climatology_baseline(clean[d], t, valid[d])
                res = paired_bss_shuffled(np.asarray(pred, float), np.asarray(ref, float), y,
                                          pd.to_datetime(valid[d]["time"]).to_numpy(), n_boot=400, n_shuffles=20)
                rows.append({"domain": d, "target": t, "family": family_of(t), "estimable": res.estimable,
                             "n_positive_weeks": res.n_positive_weeks, "paired_diff": res.point,
                             "paired_lo": res.lo, "paired_hi": res.hi, "pvalue": bootstrap_pvalue(res),
                             "ci_above_zero": bool(np.isfinite(res.lo) and res.lo > 0)})
    df = pd.DataFrame(rows)
    est = df["estimable"].astype(bool) & df["pvalue"].notna()
    df["bh_reject"] = False
    df.loc[est, "bh_reject"] = multipletests_bh(df.loc[est, "pvalue"].tolist(), q=Q)
    df["holm_reject"] = False
    for _k, grp in df[est].groupby(["domain", "family"]):
        df.loc[grp.index, "holm_reject"] = multipletests_holm(grp["pvalue"].tolist(), alpha=ALPHA_HOLM)
    df["survivor"] = df["estimable"].astype(bool) & df["ci_above_zero"] & df["bh_reject"] & df["holm_reject"]
    return df


def report() -> dict[str, Any]:
    from research.v12 import evaluate

    common.assert_looks()
    tables = long_tables()
    drought_arms = [f"S3-drought@{k}" for k in KAPPAS]
    fire_arms = [f"S3-fire@{w}" for w in WEIGHTS]
    met = evaluate.metrics(tables, drought_arms + fire_arms)
    met = met[~met["brier"].isna() | (met["arm"] == "A")]
    OUT.mkdir(parents=True, exist_ok=True)
    met.to_csv(OUT / "metrics_all_variants.csv", index=False)
    sel_d, mean_d = evaluate.select(met[met["target"].str.startswith("d_")], {"drought": drought_arms})
    sel_f, mean_f = evaluate.select(met[met["target"].str.startswith("f_")], {"fire": fire_arms})
    kd, wf = sel_d["drought"], sel_f["fire"]

    # One stage arm: the selected drought kappa on drought pairs, fire weight on fire pairs.
    for path in tables.values():
        f = pd.read_parquet(path)
        f["S3"] = np.where(f["target"].str.startswith("d_"), f[kd], f[wf])
        f.to_parquet(path, index=False)
    met_s3 = evaluate.metrics(tables, ["S3"])
    met_all = pd.concat([met, met_s3[met_s3["arm"] == "S3"]], ignore_index=True)
    pairs = met[met["arm"] == "A"][["domain", "target"]].drop_duplicates()
    jobs = [(str(tables[d]), d, t, "S3", 20) for d, t in pairs.itertuples(index=False)]
    tests = evaluate.adoption(evaluate.run_paired(jobs), met_all, tables)
    tests["adopted"] = tests["qualifies"]
    tests.to_csv(OUT / "paired_tests.csv", index=False)

    surv = survivors(int(kd.split("@")[1]), float(wf.split("@")[1]))
    surv.to_csv(OUT / "survivors_stage3.csv", index=False)
    base = pd.read_csv("artifacts/v11/survivors_v11.csv")
    base_surv = set(map(tuple, base[base["survivor"].astype(bool)][["domain", "target"]].values))
    s3_surv = set(map(tuple, surv[surv["survivor"]][["domain", "target"]].values))
    rel = met_all[met_all["arm"].isin(["A", "S3"])].pivot_table(index="domain", columns="arm", values="reliability", aggfunc="mean")
    moving = evaluate.moving_to_per_cell(tests[tests["adopted"]])
    summary = {
        "kappa_selected": kd, "w_selected": wf,
        "pooled_mean_brier_drought": {k: round(float(v), 6) for k, v in mean_d.items() if k in drought_arms + ["A"]},
        "pooled_mean_brier_fire": {k: round(float(v), 6) for k, v in mean_f.items() if k in fire_arms + ["A"]},
        "estimable": int(tests["estimable"].astype(bool).sum()),
        "ci_above_zero": int(tests["ci_above_zero"].sum()),
        "qualifying": int(tests["qualifies"].sum()),
        "adopted": int(tests["adopted"].sum()),
        "survivors_configuration_A": len(base_surv), "survivors_stage3": len(s3_surv),
        "survivors_gained": sorted(f"{d} {t}" for d, t in s3_surv - base_surv),
        "survivors_lost": sorted(f"{d} {t}" for d, t in base_surv - s3_surv),
        "estimable_validation_pairs_configuration_A": int(base["estimable"].astype(bool).sum()),
        "estimable_validation_pairs_stage3": int(surv["estimable"].astype(bool).sum()),
        "mean_reliability_by_domain": {d: {a: round(float(v), 5) for a, v in r.items()} for d, r in rel.iterrows()},
        "base_rate_h4_h8_moving_to_per_cell": int(len(moving)),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    common.assert_looks()
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if sys.argv[1] == "predict":
        for Y in common.FOLDS:
            print(predict_fold(Y))
    elif sys.argv[1] == "report":
        print(json.dumps(report(), indent=1))
    else:
        raise SystemExit(__doc__)
