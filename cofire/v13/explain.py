"""What lies behind each live probability: the tables for v1.3's explanations.

For every domain, from exactly the training rows the export fits on (2007 to
2021, asserted), this writes `artifacts/v13/explain/<domain>.json` (committed: it depends only on the
training years and the frozen model, and the static site build has no data
stores to recompute it):

* **drought**, per horizon: for every current category (0 to 4) and month,
  the row the live Markov model uses (month, season, category or persistence
  fallback, with its support gate), the row itself, and the per-year counts of
  where cells in that state stood h weeks later. Any drought target's
  probability is a sum over the row; the counts reproduce it as
  (counts + prior) / (total + prior strength).
* **fire**, per horizon and threshold: the damped logistic's two coefficients
  (the live model is a smooth curve over the dryness percentile, not a table),
  and, as illustration, per-year counts of training cell-weeks in the same
  10-point dryness band and season with what happened h weeks later.
* **live**: any adopted v1.2 arm (a logit recalibration applied from a date).

The app uses these for the frequency sentences, "weeks like this one" and
"why did this change". Nothing here reads 2026; the training window is
asserted to end in 2021.

    python -m cofire.v13.explain
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

LOGGER = logging.getLogger("cofire.v13.explain")
TRAIN_START, TRAIN_END = pd.Timestamp("2007-01-01"), pd.Timestamp("2021-12-31")
OUT = Path("artifacts/v13/explain")
THRESHOLDS = (80, 90, 97)


def training_frame(domain: str) -> pd.DataFrame:
    """The rows the export trains on: the configuration A store, 2007 to 2021, with targets."""
    from cofire.ship import build_v11, fit_v11

    f = build_v11.load(domain)
    f = f[f["time"] <= pd.Timestamp("2023-12-31")].reset_index(drop=True)  # labels for late 2021 need 2022 rows
    g = fit_v11.with_targets(f, pd.to_numeric(f["erc_pct"], errors="coerce").to_numpy(float))
    train = g[(g["time"] >= TRAIN_START) & (g["time"] <= TRAIN_END)].reset_index(drop=True)
    assert pd.to_datetime(train["time"]).max() <= TRAIN_END, "explanations must come from training years only"
    assert pd.to_datetime(train["time"]).dt.year.min() >= 2007
    return train


def _key_for(mk: Any, c: int, month: int) -> tuple[str, Any]:
    """Which row the live model uses for (category, month), as model.row does."""
    from cofire.model.targets import _season

    if (c, month) in mk.by_cat_month:
        return "month", month
    sea = _season(month)
    if (c, sea) in mk.by_cat_season:
        return "season", sea
    if c in mk.by_cat:
        return "category", None
    return "persistence", None


def drought_tables(train: pd.DataFrame, h: int) -> dict[str, Any]:
    from cofire.model.targets import N_CATEGORIES, MarkovBaseline, _season

    mk = MarkovBaseline(horizon=h).fit(train)
    now = pd.to_numeric(train["usdm"], errors="coerce").to_numpy(float)
    fut = pd.to_numeric(train[f"usdm_h{h}"], errors="coerce").to_numpy(float)
    t = pd.to_datetime(train["time"])
    ok = np.isfinite(now) & np.isfinite(fut)
    ci = np.clip(np.round(now[ok]), 0, N_CATEGORIES - 1).astype(int)
    fi = np.clip(np.round(fut[ok]), 0, N_CATEGORIES - 1).astype(int)
    mi = t.dt.month.to_numpy()[ok]
    yi = t.dt.year.to_numpy()[ok]
    seasons = np.array([_season(m) for m in mi])
    rows: dict[str, Any] = {}
    for c in range(N_CATEGORIES):
        for month in range(1, 13):
            kind, val = _key_for(mk, c, month)
            row = [float(x) for x in mk.row(c, month)]
            cases: dict[str, list[int]] = {}
            if kind != "persistence":
                m = ci == c
                if kind == "month":
                    m &= mi == month
                elif kind == "season":
                    m &= seasons == val
                for y in sorted(set(yi[m].tolist())):
                    sel = m & (yi == y)
                    cases[str(int(y))] = [int(x) for x in np.bincount(fi[sel], minlength=N_CATEGORIES)]
            rows[f"{c},{month}"] = {"key": kind, "season": _season(month), "row": row, "cases": cases}
    return {"global_row": [float(x) for x in mk.global_row], "prior_strength": float(mk.prior_strength),
            "persistence_weight": float(mk.persistence_weight), "rows": rows}


def fire_tables(train: pd.DataFrame, h: int) -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression

    from cofire.model.targets import SEASONS

    out: dict[str, Any] = {}
    x = pd.to_numeric(train["erc_pct"], errors="coerce").to_numpy(float)
    season = pd.to_datetime(train["time"]).dt.month.map(SEASONS).to_numpy()
    year = pd.to_datetime(train["time"]).dt.year.to_numpy()
    band = np.clip(np.floor(np.nan_to_num(x, nan=-1) / 10), -1, 9).astype(int)
    for thr in THRESHOLDS:
        target = f"f_gt{thr}_h{h}"
        y = pd.to_numeric(train[target], errors="coerce").to_numpy(float)
        m = np.isfinite(x) & np.isfinite(y)
        lr = LogisticRegression(max_iter=400).fit(x[m].reshape(-1, 1), y[m])  # exactly as the live model
        cases: dict[str, dict[str, dict[str, list[int]]]] = {}
        for s in ("DJF", "MAM", "JJA", "SON"):
            for b in range(10):
                sel = m & (season == s) & (band == b)
                if not sel.any():
                    continue
                per = {}
                for yr in sorted(set(year[sel].tolist())):
                    ss = sel & (year == yr)
                    per[str(int(yr))] = [int(ss.sum()), int(y[ss].sum())]
                cases.setdefault(s, {})[str(b)] = per
        out[str(thr)] = {"intercept": float(lr.intercept_[0]), "slope": float(lr.coef_[0, 0]),
                         "fill": float(np.nanmedian(x[m])), "cases": cases}
    return out


def build(domain: str) -> dict[str, Any]:
    from cofire.v12 import live

    train = training_frame(domain)
    return {
        "domain": domain,
        "train": [str(TRAIN_START.date()), str(TRAIN_END.date())],
        "drought": {str(h): drought_tables(train, h) for h in (2, 4, 8)},
        "fire": {str(h): fire_tables(train, h) for h in (2, 4, 8)},
        "live": [{k: e[k] for k in ("target", "horizon", "a", "b", "applies_from")}
                 for e in live.load() if e["domain"] == domain],
    }


def write(out: Path = OUT) -> list[Path]:
    from cofire.ship import domains

    paths = []
    for d in domains.ORDER:
        p = out / f"{d}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(build(d), separators=(",", ":")))
        paths.append(p)
        LOGGER.info("%s: %d bytes", d, p.stat().st_size)
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for path in write():
        print(path)
