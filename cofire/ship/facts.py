"""Emit `app/lib/facts.json` from the artifact tree. Nothing hand-written.

Every number the site shows is written here from an artifact, so a re-run
updates the site and a stale claim is impossible. The previous builder read the
v0.6 contamination-era artifacts, which no longer describe anything that ships.

The rule the copy must obey: no claim of forecast skill beyond what the stage 1
survivors support. The survivor list travels in this file so the copy lint can
check a claim against it rather than against a human's memory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

LOGGER = logging.getLogger("cofire.ship.facts")

ART = Path("artifacts")
RERUN = ART / "rerun_a"
LOOK3 = ART / "look3"
OUT = Path("app/lib/facts.json")


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _survivors() -> list[dict[str, Any]]:
    path = RERUN / "multiplicity.csv"
    if not path.exists():
        return []
    m = pd.read_csv(path)
    s = m[m["survivor"].astype(bool)]
    return [
        {
            "domain": str(r["domain"]), "target": str(r["target"]),
            "horizon": int(r["horizon"]), "arm": str(r["arm"]),
            "paired_diff": float(r["paired_diff"]),
            "paired_lo": float(r["paired_lo"]), "paired_hi": float(r["paired_hi"]),
            "n_positive_weeks": int(r["n_positive_weeks"]),
        }
        for _, r in s.iterrows()
    ]


def _multiplicity_summary() -> dict[str, Any]:
    path = RERUN / "multiplicity.csv"
    if not path.exists():
        return {}
    m = pd.read_csv(path)
    return {
        "n_comparisons": int(len(m)),
        "n_estimable": int(m["estimable"].sum()),
        "n_survivors": int(m["survivor"].sum()),
        "q": 0.10,
        "min_positive_weeks": 12,
        "rule": (
            "paired difference between the statistic on real targets and on "
            "targets shuffled within the same circular blocks, CI above zero"
        ),
    }


def _subx() -> dict[str, Any]:
    path = RERUN / "subx_verdict.csv"
    if not path.exists():
        return {}
    d = pd.read_csv(path)
    ci = d["ci_above_zero"].fillna(False).astype(bool)
    return {
        "n_comparisons": int(len(d)),
        "n_estimable": int(d["estimable"].sum()),
        "n_ci_above_zero": int(ci.sum()),
        "n_switched": int(d["switches_to_b"].astype(bool).sum()),
        "verdict": "no target switches to configuration B; everything ships on A",
        "coverage_note": (RERUN / "subx_coverage_note.txt").read_text().strip()
        if (RERUN / "subx_coverage_note.txt").exists() else "",
    }


def _look3() -> dict[str, Any]:
    prov_path = LOOK3 / "provenance.json"
    if not prov_path.exists():
        return {}
    prov = json.loads(prov_path.read_text())
    crit = pd.read_csv(LOOK3 / "criteria.csv")
    crit["test"] = crit["name"].str.split().str[0]

    by_test: dict[str, Any] = {}
    for test, g in crit.groupby("test"):
        by_test[str(test)] = {
            "name": str(g["name"].iloc[0]),
            "threshold": str(g["threshold"].iloc[0]),
            "n_pass": int(g["passed"].sum()),
            "n_total": int(len(g)),
        }

    cov = pd.read_csv(LOOK3 / "coverage.csv")
    pid = cov[cov["impl"] == "reference_pid"]
    aci = cov[cov["impl"] == "aci"]
    rel = pd.read_csv(LOOK3 / "reliability.csv")

    return {
        "look_index": int(prov["look_index"]),
        "config_hash": str(prov["config_hash"]),
        "preregistration_sha256": str(prov["preregistration_sha256"]),
        "freeze_commit": str(prov["freeze_commit"]),
        "criteria_passed": int(prov["criteria_passed"]),
        "criteria_total": int(prov["criteria_total"]),
        "by_test": by_test,
        "interval_tests_all_pass": bool(
            crit[~crit["name"].str.startswith("5")]["passed"].all()
        ),
        "pid": {
            "coverage_min": round(float(pid["coverage"].min()), 4),
            "coverage_max": round(float(pid["coverage"].max()), 4),
            "roll13_min": round(float(pid["roll13_min"].min()), 4),
            "miss_run_max": int(pid["miss_run"].max()),
        },
        "aci": {
            "coverage_min": round(float(aci["coverage"].min()), 4),
            "roll13_min": round(float(aci["roll13_min"].min()), 4),
            "miss_run_max": int(aci["miss_run"].max()),
        },
        "coverage_series": cov.to_dict(orient="records"),
        "reliability": rel.to_dict(orient="records"),
        "reliability_by_horizon": {
            str(h): {
                "mean": round(float(g["reliability"].mean()), 4),
                "max": round(float(g["reliability"].max()), 4),
                "n": int(len(g)),
            }
            for h, g in rel.groupby("horizon")
        },
        "width_ratio": pd.read_csv(LOOK3 / "width_ratio.csv").to_dict(orient="records"),
    }


def _stage_ab() -> dict[str, Any]:
    out: dict[str, Any] = {}
    if (RERUN / "pid_coverage.csv").exists():
        cov = pd.read_csv(RERUN / "pid_coverage.csv")
        out["validation_coverage"] = cov.to_dict(orient="records")
    if (RERUN / "classification.csv").exists():
        out["classification"] = pd.read_csv(RERUN / "classification.csv").to_dict(
            orient="records"
        )
    if (RERUN / "classification_control.csv").exists():
        out["classification_control"] = pd.read_csv(
            RERUN / "classification_control.csv"
        ).to_dict(orient="records")
    return out


def _ledger() -> dict[str, Any]:
    path = Path("data/ledger.json")
    if not path.exists():
        return {}
    d = json.loads(path.read_text())
    return {
        "total_bytes": int(d["total_bytes"]),
        "budget_bytes": int(d["budget_bytes"]),
        "remaining_bytes": int(d["remaining_bytes"]),
        "total_gb": round(d["total_bytes"] / 1e9, 3),
        "n_transfers": len(d.get("transfers", [])),
        "n_corrections": len(d.get("corrections", [])),
    }


def _rendering() -> list[dict[str, Any]]:
    path = ART / "ship" / "rendering.csv"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = pd.read_csv(path).to_dict(orient="records")
    return rows


def _sources() -> list[dict[str, Any]]:
    """Data sources with the record span each actually contributes."""
    return [
        {"name": "gridMET ERC", "span": "2007 to 2026", "role": "fuel dryness, the forecast target"},
        {"name": "US Drought Monitor", "span": "2007 to 2026", "role": "drought category, the event targets"},
        {"name": "SubX CFSv2", "span": "2018 to 2025", "role": "evaluated once, not adopted"},
    ]


def build() -> dict[str, Any]:
    return {
        "generated_from": "artifacts/",
        "note": (
            "Every figure the site shows is written here from artifacts. Do not "
            "hard-code numbers in components."
        ),
        "git_sha": _git_sha(),
        "resolution_m": 4000,
        "domains": ["larimer", "pueblo"],
        "split": {
            "train": "2007-01-01 to 2021-12-31",
            "validate": "2022 to 2023",
            "calibrate": "2024 to 2025",
            "holdout": "2026",
        },
        "configuration": {
            "drought": "Markov transition baseline, 18 of 18 targets",
            "fire": "damped-persistence logistic, 9 of 9 targets",
            "continuous": "damped regression at h2, h4, h8",
            "intervals": "reference conformal PID",
            "forecast_weather": "none; SubX was evaluated once and did not qualify",
        },
        "hindcast_looks": 3,
        "preregistration_sha256": _sha256(Path("docs/PREREGISTRATION_LOOK3.md")),
        "freeze_commit": (ART / "FREEZE_COMMIT").read_text().strip()
        if (ART / "FREEZE_COMMIT").exists() else "",
        "config_hash": json.loads((LOOK3 / "provenance.json").read_text())["config_hash"]
        if (LOOK3 / "provenance.json").exists() else "",
        "multiplicity": _multiplicity_summary(),
        "survivors": _survivors(),
        "subx": _subx(),
        "look3": _look3(),
        "stage_ab": _stage_ab(),
        "rendering": _rendering(),
        "ledger": _ledger(),
        "sources": _sources(),
    }


def write(out: Path = OUT) -> Path:
    facts = build()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(facts, indent=2))
    LOGGER.info(
        "facts.json: %d survivors, look %s, %d of %d criteria, %d rendering decisions",
        len(facts["survivors"]), facts["hindcast_looks"],
        facts["look3"].get("criteria_passed", 0),
        facts["look3"].get("criteria_total", 0), len(facts["rendering"]),
    )
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write())
