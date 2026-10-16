"""v1.1 Stage 4: configuration A fitted for the new domains, leak-free.

The frozen predictors are used unchanged (`MarkovBaseline` for drought, the
damped logistic and ERC-decile transition table for fire, the damped regression
and decile mean for the continuous percentile). What is new is the selection,
which the frozen `shipping.choose` would run with two leaks the sweep found:

* every fold recomputes `erc_pct` from that fold's training years only, so the
  held-out year never enters its own percentile pools;
* every fold drops training rows whose h-week label lands in the held-out year.

Folds per domain are every training year whose footprint-mean USDM category
exceeds that domain's median over 2007 to 2021. Selection is pooled across all
five domains on the years that are folds in every domain; each domain is fitted
on its own rows and scored on its own held-out rows, and the arms are compared
on the mean of the five per-domain scores, so Larimer's 480 cells do not
outvote Denver's 52.

Larimer and Pueblo keep their frozen families. The pooled choice is written for
the new domains to `artifacts/v11/choices.json`, beside its fit window.

    python -m cofire.ship.fit_v11 lodo <domain>   # checkpointed per domain
    python -m cofire.ship.fit_v11 choose
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.ship import build_v11, domains  # noqa: E402

LOGGER = logging.getLogger("cofire.ship.fit_v11")
OUT = Path("artifacts/v11")
TRAIN_START = pd.Timestamp("2007-01-01")
TRAIN_END = pd.Timestamp("2021-12-31")
FIRE_ARMS = ("transition", "damped")
CONT_ARMS = ("damped_regression", "decile_mean")


def folds(frames: dict[str, pd.DataFrame] | None = None) -> dict[str, Any]:
    """The fold years per domain (training years whose mean USDM category is above the domain's 2007
    to 2021 median) and the years that are folds in every domain.
    """
    out: dict[str, Any] = {"rule": "training years whose footprint-mean USDM category exceeds the domain's 2007-2021 median"}
    per: dict[str, list[int]] = {}
    for d in domains.ORDER:
        f = frames[d] if frames else build_v11.load(d)
        f = f[f["time"] <= TRAIN_END]
        m = f.groupby(f["time"].dt.year)["usdm"].mean()
        med = float(m.median())
        per[d] = [int(y) for y, v in m.items() if v > med]
        out[d] = {"median": round(med, 4), "folds": per[d],
                  "annual_mean": {int(y): round(float(v), 4) for y, v in m.items()}}
    out["shared"] = sorted(set.intersection(*map(set, per.values())))
    return out


def with_targets(frame: pd.DataFrame, pct: np.ndarray) -> pd.DataFrame:
    """A copy of the frame with `erc_pct` replaced by `pct` and the horizon and event target columns
    added.
    """
    from cofire.model.features_a import add_horizons
    from cofire.model.targets import HORIZONS, all_event_targets

    g = frame.copy()
    g["erc_pct"] = pct
    return all_event_targets(add_horizons(g, HORIZONS), HORIZONS)


def embargo(train: pd.DataFrame, before: pd.Timestamp, h: int) -> pd.DataFrame:
    """Drop rows dated before `before` whose h-week label lands on or after it."""
    t = pd.to_datetime(train["time"])
    return train[~((t < before) & (t + pd.Timedelta(weeks=h) >= before))]


def predict_event(family: str, h: int, train: pd.DataFrame, target: str, index: pd.DataFrame) -> np.ndarray:
    """Event probabilities for `index` from one family fitted on `train`: the frozen Markov drought
    predictor for markov, else the frozen fire predictor.
    """
    from cofire.model.shipping import _drought_prediction, _fire_prediction

    if family == "markov":
        return np.asarray(_drought_prediction(h, train, target, index), dtype=float)
    return np.asarray(_fire_prediction(family, train, target, index), dtype=float)


def lodo(domain: str) -> Path:
    """Held-out predictions summary for every fold this domain needs."""
    from cofire.model.erc_pct import erc_percentile_reference
    from cofire.model.prob_metrics import brier
    from cofire.model.shipping import continuous_predict
    from cofire.model.targets import HORIZONS, target_names

    fl = json.loads((OUT / "folds.json").read_text())
    years = sorted(set(fl[domain]["folds"]) | set(fl["shared"]))
    ck = OUT / "lodo" / f"{domain}.csv"
    ck.parent.mkdir(parents=True, exist_ok=True)
    done = pd.read_csv(ck) if ck.exists() else pd.DataFrame(columns=["year"])
    rows = done.to_dict("records")

    f = build_v11.load(domain)
    period = f[(f["time"] >= TRAIN_START) & (f["time"] <= TRAIN_END)].reset_index(drop=True)
    yr = period["time"].dt.year
    for year in years:
        if year in set(done["year"].astype(int)):
            continue
        pct = erc_percentile_reference(period, (yr != year).to_numpy())
        g = with_targets(period, pct)
        gy = g["time"].dt.year
        held = g[gy == year]
        start = pd.Timestamp(f"{year}-01-01")
        for h in HORIZONS:
            fit = embargo(g[gy != year], start, h)
            lab = pd.to_datetime(fit["time"]) + pd.Timedelta(weeks=h)
            assert not ((pd.to_datetime(fit["time"]) < start) & (lab >= start)).any()
            for target in target_names((h,)):
                y = pd.to_numeric(held[target], errors="coerce").to_numpy(float)
                arms = FIRE_ARMS if target.startswith("f_gt") else ("markov",)
                for arm in arms:
                    p = predict_event(arm, h, fit, target, held)
                    m = np.isfinite(p) & np.isfinite(y)
                    rows.append({"domain": domain, "year": year, "target": target, "horizon": h,
                                 "arm": arm, "n": int(m.sum()), "sum_sq": float(((p[m] - y[m]) ** 2).sum()),
                                 "brier": brier(p[m], y[m]) if m.any() else np.nan})
            yc = pd.to_numeric(held[f"erc_pct_h{h}"], errors="coerce").to_numpy(float)
            for arm in CONT_ARMS:
                p = continuous_predict(arm, fit, h, held)
                m = np.isfinite(p) & np.isfinite(yc)
                rows.append({"domain": domain, "year": year, "target": f"erc_pct_h{h}", "horizon": h,
                             "arm": arm, "n": int(m.sum()), "sum_sq": float(np.abs(p[m] - yc[m]).sum()),
                             "brier": float(np.mean(np.abs(p[m] - yc[m]))) if m.any() else np.nan})
        pd.DataFrame(rows).to_csv(ck, index=False)
        LOGGER.info("%s fold %d checkpointed", domain, year)
    return ck


def _score(df: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Per domain, target, arm: error pooled over the given held-out years."""
    d = df[df["year"].isin(years)]
    g = d.groupby(["domain", "target", "horizon", "arm"], as_index=False)[["sum_sq", "n"]].sum()
    g["score"] = g["sum_sq"] / g["n"].where(g["n"] > 0)
    return g


def choose() -> dict[str, Any]:
    """Pick, for each target, the arm with the lowest mean per-domain score on the shared folds;
    write the choices and continuous arms with their fit-window sidecars, and the score tables,
    under artifacts/v11, and return them.
    """
    from cofire.model.fit_window import TRAIN_ONLY, FitWindow, checked_load, write_sidecar
    from cofire.model.shipping import load as load_frozen

    fl = json.loads((OUT / "folds.json").read_text())
    shared = fl["shared"]
    df = pd.concat([pd.read_csv(OUT / "lodo" / f"{d}.csv") for d in domains.ORDER], ignore_index=True)
    pooled = _score(df, shared)
    own = pd.concat([_score(df[df["domain"] == d], fl[d]["folds"]) for d in domains.ORDER], ignore_index=True)

    # Arms compared on the mean of the five per-domain scores.
    mean = pooled.groupby(["target", "horizon", "arm"], as_index=False)["score"].mean()
    choices: list[dict[str, Any]] = []
    cont: dict[str, str] = {}
    for (target, h), grp in mean.groupby(["target", "horizon"]):
        best = grp.loc[grp["score"].idxmin()]
        if str(target).startswith("erc_pct"):
            cont[str(int(h))] = str(best["arm"])
            continue
        choices.append({"target": target, "horizon": int(h), "family": str(best["arm"]), "pooled": False,
                        "lodo_brier": round(float(best["score"]), 6), "reliability": float("nan"),
                        "resolution": float("nan")})

    frozen = load_frozen(out_dir=Path("artifacts/rerun_a"))
    fire = mean[mean["target"].str.startswith("f_gt")].pivot_table(
        index=["target", "horizon"], columns="arm", values="score").reset_index()
    fire["pooled_choice"] = np.where(fire["damped"] <= fire["transition"], "damped", "transition")
    fire["frozen_choice"] = [frozen[(t, int(h))].family if (t, int(h)) in frozen else ""
                             for t, h in zip(fire["target"], fire["horizon"], strict=True)]

    OUT.mkdir(parents=True, exist_ok=True)
    window = FitWindow(date(2007, 1, 1), date(2021, 12, 31), TRAIN_ONLY)
    cpath = OUT / "choices.json"
    cpath.write_text(json.dumps(choices, indent=2))
    write_sidecar(cpath, window, "v1.1 choices for the new domains")
    apath = OUT / "continuous_arms.json"
    apath.write_text(json.dumps(cont, indent=2))
    write_sidecar(apath, window, "v1.1 continuous arms for the new domains")
    for p in (cpath, apath):
        checked_load(p, strict=True)
    pooled.to_csv(OUT / "lodo_shared_folds.csv", index=False)
    own.to_csv(OUT / "lodo_own_folds.csv", index=False)
    fire.to_csv(OUT / "fire_family.csv", index=False)
    return {"choices": choices, "continuous": cont, "fire": fire}


def load_choices(domain: str) -> dict[tuple[str, int], Any]:
    """Frozen families for Larimer and Pueblo; v1.1 families for the new domains.

    Both go through the strict fit-window check.
    """
    from cofire.model.fit_window import checked_load
    from cofire.model.shipping import load as load_frozen

    out_dir = OUT if domain in domains.NEW else Path("artifacts/rerun_a")
    checked_load(out_dir / "choices.json", strict=True)
    return load_frozen(out_dir=out_dir)


def continuous_arms(domain: str) -> dict[int, str]:
    """The continuous ERC arm per horizon for a domain, from the v1.1 or the frozen choices, through
    the strict fit-window check.
    """
    from cofire.model.fit_window import checked_load

    out_dir = OUT if domain in domains.NEW else Path("artifacts/rerun_a")
    p = out_dir / "continuous_arms.json"
    checked_load(p, strict=True)
    return {int(k): str(v) for k, v in json.loads(p.read_text()).items()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = sys.argv[1]
    if cmd == "folds":
        fl = folds()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "folds.json").write_text(json.dumps(fl, indent=1) + "\n")
        print({d: fl[d]["folds"] for d in domains.ORDER}, "shared", fl["shared"])
    elif cmd == "lodo":
        print(lodo(sys.argv[2]))
    elif cmd == "choose":
        r = choose()
        print(r["fire"].to_string(index=False))
        print("continuous", r["continuous"])
    else:
        raise SystemExit(__doc__)
