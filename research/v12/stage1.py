"""v1.2 Stage 1: delayed-feedback logistic recalibration of configuration A.

    python -m research.v12.stage1 predict <domain>   # per domain, checkpointed
    python -m research.v12.stage1 report             # metrics, selection, tests, adoption

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
from cofire.v12 import common, recal  # noqa: E402

from research.v12 import preds

LOGGER = logging.getLogger("research.v12.stage1")
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


def report() -> dict[str, Any]:
    from cofire.ship import domains

    from research.v12 import evaluate, gate

    common.assert_looks()
    failed = [r for r in gate.check_all() if not r.passed]
    if failed:
        r = failed[0]
        raise SystemExit(f"gate failed: {r.name} h{r.horizon} first leaking probe {r.first_leak}")

    tables = {d: PRED / f"{d}.parquet" for d in domains.ORDER}
    arms = list(recal.VARIANTS)
    met = evaluate.metrics(tables, arms)
    OUT.mkdir(parents=True, exist_ok=True)
    met.to_csv(OUT / "metrics_all_variants.csv", index=False)

    selected, mean = evaluate.select(met, recal.FAMILIES)
    static = min(("S1-static-a", "S1-static-ab"), key=lambda k: mean[k])
    pairs = met[met["arm"] == "A"][["domain", "target"]].drop_duplicates()
    jobs = [(str(tables[d]), d, t, arm, 20) for arm in sorted(set(selected.values()))
            for d, t in pairs.itertuples(index=False)]
    tests = evaluate.adoption(evaluate.run_paired(jobs), met, tables)
    tests["eligible_for_adoption"] = tests["arm"] == static
    tests["adopted"] = tests["qualifies"] & tests["eligible_for_adoption"]
    tests.to_csv(OUT / "paired_tests.csv", index=False)
    moving = evaluate.moving_to_per_cell(tests[tests["adopted"]])
    summary = {
        "gate": "every online variant passed at its real delay (h = 2, 4, 8); each fails with the delay shortened",
        "selected": selected,
        "static_eligible_arm": static,
        "pooled_mean_brier": {k: round(float(v), 6) for k, v in mean.items()},
        "pairs": int(len(pairs)),
        "estimable": {a: int(g["estimable"].astype(bool).sum()) for a, g in tests.groupby("arm")},
        "ci_above_zero": {a: int(g["ci_above_zero"].sum()) for a, g in tests.groupby("arm")},
        "qualifying": {a: int(g["qualifies"].sum()) for a, g in tests.groupby("arm")},
        "adopted": int(tests["adopted"].sum()),
        "base_rate_h4_h8_for_reliability_now": int(len(evaluate.base_rate_reliability_pairs())),
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
