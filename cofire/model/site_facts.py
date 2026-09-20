"""Emit the figures the landing page quotes, straight from artifacts.

The landing page must not hard-code numbers. Every figure it shows is written
here from the artifact tree, so a re-run updates the page and a stale claim is
impossible. Nothing is rounded up, dramatised, or invented.

Writes app/lib/facts.json.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any

from cofire.model.config import get_settings


def _load_multiregime(art: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in sorted((art / "uncertainty" / "multiregime_checkpoints").glob("*.json")):
        rows.extend(json.loads(f.read_text()))
    if not rows:
        return {}
    h4 = [r for r in rows if r.get("horizon") == 4]
    by: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    for r in h4:
        by[(str(r.get("domain")), str(r.get("label")))].append(float(r["coverage"]))
    domains: dict[str, Any] = {}
    for (dom, lab), vals in by.items():
        mean = sum(vals) / len(vals)
        entry = domains.setdefault(dom, {"variants": []})
        entry["variants"].append({"label": lab, "mean": round(mean, 3), "worst": round(min(vals), 3)})
    for entry in domains.values():
        entry["variants"].sort(key=lambda v: -v["mean"])
        best = entry["variants"][0]
        base = next((v for v in entry["variants"] if v["label"] == "base"), best)
        entry["best"] = best
        entry["baseline"] = base
        entry["improvement"] = round(best["mean"] - base["mean"], 3)
        entry["gap_to_target"] = round(0.90 - best["mean"], 3)
        entry["n_variants"] = len(entry["variants"])
    return domains


def _load_lodo(art: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for dom, pat in (("larimer", "checkpoints"), ("pueblo", "checkpoints_pueblo")):
        rows: list[dict[str, Any]] = []
        for f in sorted((art / "lodo" / pat).glob("fold_*.json")):
            rows.extend(json.loads(f.read_text()))
        erc = [r for r in rows if r.get("target") == "erc_pct"]
        if not erc:
            continue
        lvl = [r["skill"] for r in erc if r["parameterisation"] == "level"]
        dlt = [r["skill"] for r in erc if r["parameterisation"] == "delta"]
        out[dom] = {
            "n_folds": len({r["year"] for r in erc}),
            "level_mean_skill": round(sum(lvl) / len(lvl), 4) if lvl else None,
            "delta_mean_skill": round(sum(dlt) / len(dlt), 4) if dlt else None,
        }
    return out


def build_facts() -> dict[str, Any]:
    settings = get_settings()
    art = settings.artifacts_dir

    facts: dict[str, Any] = {
        "generated_from": "artifacts/",
        "note": "Every figure on the landing page is written here from artifacts. Do not hard-code numbers in components.",
    }

    metrics_path = art / "metrics.json"
    if metrics_path.exists():
        m = json.loads(metrics_path.read_text())
        facts["shipping_arm"] = m.get("shipping_arm")
        facts["git_sha"] = m.get("git_sha")
        facts["manifest_hash"] = m.get("manifest_hash")
        facts["resolution_m"] = m.get("resolution_m")
        facts["n_train"] = m.get("n_train")
        eff = m.get("effective_n") or {}
        facts["effective_n"] = {
            "usdm": round(float(eff.get("usdm_n_eff", 0)), 1) if eff.get("usdm_n_eff") else None,
            "erc": round(float(eff.get("erc_n_eff", 0)), 1) if eff.get("erc_n_eff") else None,
        }

    log = art / "hindcast" / "run_log.json"
    if log.exists():
        looks = json.loads(log.read_text())
        facts["hindcast_looks"] = len(looks)
        facts["config_hash"] = looks[-1]["config_hash"] if looks else None

    facts["calibration"] = _load_multiregime(art)
    facts["lodo"] = _load_lodo(art)

    pool = art / "uncertainty" / "regime_pool.json"
    if pool.exists():
        p = json.loads(pool.read_text())
        facts["pool"] = {
            "years": p.get("pool_years"),
            "usdm_min": round(float(p["usdm_min"]), 3),
            "usdm_max": round(float(p["usdm_max"]), 3),
            "measured_coverage": round(float(p["measured_coverage"]), 3),
        }

    fires = art / "hindcast" / "fires.json"
    ctrl = art / "hindcast" / "control.json"
    if fires.exists():
        fl = json.loads(fires.read_text())
        ind = [f for f in fl if f.get("in_domain")]
        facts["fires"] = {
            "total": len(fl),
            "in_domain": len(ind),
            "in_domain_acres": round(sum(float(f["acres"]) for f in ind)),
            "largest": max((f["name"] for f in ind), key=lambda n: 0) if ind else None,
        }
        if ind:
            big = max(ind, key=lambda f: float(f["acres"]))
            facts["fires"]["largest"] = big["name"]
            facts["fires"]["largest_acres"] = round(float(big["acres"]))
        if ctrl.exists():
            c = json.loads(ctrl.read_text())
            facts["fires"]["control_mean_rank"] = c.get("mean_pct_rank")

    return facts


def write_facts(out: Path | None = None) -> Path:
    facts = build_facts()
    path = out or Path("app/lib/facts.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(facts, indent=2) + "\n")
    return path


if __name__ == "__main__":
    print(write_facts())
