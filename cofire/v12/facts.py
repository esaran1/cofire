"""The v1.2 results for the app, generated from the stage artifacts only.

    python -m cofire.v12.facts

Writes app/lib/facts_v12.json, which the Method page reads: per stage, the arm
selected, pooled mean Brier against configuration A, how many pairs beat
configuration A under the paired test and how many were adopted; the live arm
for every pair; and stage 4's interval verdict.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from cofire.v12 import common

OUT = Path("app/lib/facts_v12.json")


def _stage(n: int) -> dict[str, Any]:
    p = common.OUT / f"stage{n}"
    s = json.loads((p / "summary.json").read_text())
    t = pd.read_csv(p / "paired_tests.csv") if (p / "paired_tests.csv").exists() else pd.DataFrame()
    met = pd.read_csv(p / "metrics_all_variants.csv") if (p / "metrics_all_variants.csv").exists() else pd.DataFrame()
    return {"summary": s, "tests": t, "metrics": met}


def build() -> dict[str, Any]:
    """The v1.2 results for the Method page, from the stage artifacts: each stage's arms against
    configuration A, the live arms, the survivor recheck, stage 4's interval verdict and the
    preregistration hash.
    """
    prereg = hashlib.sha256(Path("docs/PREREGISTRATION_V12.md").read_bytes()).hexdigest()
    stages: list[dict[str, Any]] = []

    def arm_row(n: int, arm: str, data: dict[str, Any], **extra: Any) -> dict[str, Any]:
        met, t = data["metrics"], data["tests"]
        pairs = met[met["arm"] == "A"][["domain", "target"]]
        a = met[met["arm"] == "A"].set_index(["domain", "target"])["brier"]
        if arm == "S3":
            # The stage arm is the selected drought kappa on drought targets and
            # the selected fire weight on fire targets.
            kd, wf = extra["kappa"], extra["w"]
            sel = met[((met["arm"] == kd) & met["target"].str.startswith("d_"))
                      | ((met["arm"] == wf) & met["target"].str.startswith("f_"))]
            m = sel.set_index(["domain", "target"])["brier"].reindex(a.index)
        else:
            m = met[met["arm"] == arm].set_index(["domain", "target"])["brier"].reindex(a.index)
        ok = m.notna()
        tt = t[t["arm"] == arm] if len(t) else t
        return {"stage": n, "arm": arm, "pairs": int(len(pairs)),
                "mean_brier_A": round(float(a[ok].mean()), 6), "mean_brier_arm": round(float(m[ok].mean()), 6),
                "estimable": int(tt["estimable"].astype(bool).sum()) if len(tt) else 0,
                "beat_A_paired": int(tt["ci_above_zero"].astype(bool).sum()) if len(tt) else 0,
                "qualifying": int(tt["qualifies"].astype(bool).sum()) if len(tt) else 0,
                "adopted": int(tt["adopted"].astype(bool).sum()) if len(tt) and "adopted" in tt else 0, **extra}

    s1 = _stage(1)
    sel = s1["summary"]["selected"]
    for fam, arm in sel.items():
        stages.append(arm_row(1, arm, s1, family=fam, shippable=fam.startswith("S1-static")))
    s2 = _stage(2)
    lam = s2["summary"]["lambda_selected"]
    for arm in sorted(s2["tests"]["arm"].unique()):
        stages.append(arm_row(2, arm, s2, ridge=lam, median_recovered=s2["summary"]["median_recovered"]))
    s3 = _stage(3)
    stages.append(arm_row(3, "S3", s3, kappa=s3["summary"]["kappa_selected"], w=s3["summary"]["w_selected"],
                          survivors_A=s3["summary"]["survivors_configuration_A"],
                          survivors_arm=s3["summary"]["survivors_stage3"]))
    live = json.loads((common.OUT / "live_arms.json").read_text()) if (common.OUT / "live_arms.json").exists() else {"entries": []}
    n_pairs = int(len(s1["metrics"][s1["metrics"]["arm"] == "A"]))
    s4p = common.OUT / "stage4" / "summary.json"
    s4 = json.loads(s4p.read_text()) if s4p.exists() else None
    recheck = common.OUT / "live_survivor_recheck.csv"
    rc = pd.read_csv(recheck).to_dict("records") if recheck.exists() else []
    return {
        "prereg_sha256": prereg,
        "stages": stages,
        "live": {"pairs": n_pairs, "on_configuration_A": n_pairs - len(live["entries"]),
                 "changed": [{k: e[k] for k in ("domain", "target", "arm", "stage", "applies_from", "paired_diff", "reliability", "reliability_A")}
                             for e in live["entries"]],
                 "survivor_recheck": rc},
        "intervals": s4,
    }


def write() -> Path:
    """Build the v1.2 facts, write them to app/lib/facts_v12.json, and return the path."""
    OUT.write_text(json.dumps(build(), indent=1, default=float) + "\n")
    return OUT


if __name__ == "__main__":
    print(write())
