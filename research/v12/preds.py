"""Configuration A on the v1.2 folds: held-out and nested out-of-fold predictions.

For each domain and held-out year Y (docs/PREREGISTRATION_V12.md):

* **outer**: configuration A fitted on 2007 to 2025 without Y (embargoed, its
  own `erc_pct` pools), predicting Y;
* **inner**: for every other year y, configuration A fitted without Y and y
  (embargoed at both, pools from the remaining years), predicting y. These
  feed any adjustment fitted to configuration A's outputs, so Y's data never
  enters a model whose predictions shape Y's adjustment.

Families are the live ones: Markov for drought, `fit_v11.load_choices` for
fire. One parquet per domain and fold under data/v12/preds/, so a killed run
resumes where it stopped.

    python -m research.v12.preds <domain> [fold ...]
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from cofire.v12 import common  # noqa: E402

LOGGER = logging.getLogger("research.v12.preds")
KEEP = ("time", "cell_id", "lat", "lon", "usdm", "erc_pct")


def path(domain: str, fold: int) -> Path:
    return common.DATA / "preds" / f"{domain}_{fold}.parquet"


def _predict_year(g: pd.DataFrame, excluded: tuple[int, ...], target_year: int,
                  choices: dict[tuple[str, int], Any]) -> pd.DataFrame:
    """Configuration A fitted without `excluded`, predicting `target_year`."""
    from cofire.model.targets import HORIZONS, target_names
    from cofire.ship import fit_v11

    gy = pd.to_datetime(g["time"]).dt.year
    held = g[gy == target_year]
    out = held[list(KEEP)].copy()
    out["year"] = target_year
    for h in HORIZONS:
        fit = common.embargo_many(g[~gy.isin(excluded)], excluded, h)
        drought = [t for t in target_names((h,)) if t.startswith("d_")]
        mk = None
        for target in target_names((h,)):
            out[f"y__{target}"] = pd.to_numeric(held[target], errors="coerce").astype("float32")
            if target in drought:
                if mk is None:
                    from cofire.model.targets import MarkovBaseline

                    mk = MarkovBaseline(horizon=h).fit(fit).predict_events(held)
                p = mk.get(target, np.full(len(held), np.nan))
            else:
                fam = choices[(target, h)].family
                p = fit_v11.predict_event(fam, h, fit, target, held)
            out[f"p__{target}"] = np.asarray(p, dtype="float32")
    return out


def run(domain: str, folds: tuple[int, ...] = common.FOLDS) -> list[Path]:
    from cofire.ship import fit_v11

    common.assert_looks()
    choices = fit_v11.load_choices(domain)
    period = common.record(domain)
    done: list[Path] = []
    for Y in folds:
        dest = path(domain, Y)
        if dest.exists():
            done.append(dest)
            continue
        parts = [_predict_year(common.frame_without(period, (Y,)), (Y,), Y, choices).assign(role="outer")]
        for y in common.YEARS:
            if y == Y:
                continue
            g = common.frame_without(period, (Y, y))
            parts.append(_predict_year(g, (Y, y), y, choices).assign(role="inner"))
        frame = pd.concat(parts, ignore_index=True)
        frame["fold"] = Y
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        frame.to_parquet(tmp, index=False)
        tmp.replace(dest)
        LOGGER.info("%s fold %d: %d rows", domain, Y, len(frame))
        done.append(dest)
    common.assert_looks()
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    dom = sys.argv[1]
    fl = tuple(int(x) for x in sys.argv[2:]) or common.FOLDS
    for p in run(dom, fl):
        print(p)
