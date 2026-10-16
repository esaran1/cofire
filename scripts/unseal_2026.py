"""The 2026 unseal (look 4): exactly the scoring in docs/PREREGISTRATION_UNSEAL.md.

    COFIRE_ALLOW_LOOK=4 uv run python scripts/unseal_2026.py

Not to be run before 2027-01-12, and run once. Every precondition in the
preregistration is checked first, and if any fails the script stops and
reads nothing from 2026:
- the date;
- the deliberate flag;
- the frozen model's files and configuration hash;
- both preregistrations' hashes;
- the look counter;
- a new output directory;
- a clean working tree.

Only then are the published forecasts read, each after its sha256 matches
the manifest. Then the 2026 outcomes are built, everything is scored,
everything is written to a new directory at once, and the look is recorded.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PREREG = Path("docs/PREREGISTRATION_UNSEAL.md")
PREREG_SHA256 = "639912a642ae788188aadfd60e5a813a0ff4b5fc767d06c49431769b218dc53d"
LOOK3_PREREG = Path("docs/PREREGISTRATION_LOOK3.md")
LOOK3_PREREG_SHA256 = "c5ca907cae475c94f85928e129514593a3e1b9496c80cac45b0e68f9314a9d9a"
CONFIG_HASH = "ed0c2079a5bc0eee1d0aa11869d3bc5eb0af671b9f30ee0c5114c3b9ca7be157"
SEAL = Path("app/lib/seal.json")
FREEZE_COMMIT = Path("artifacts/FREEZE_COMMIT")
MANIFEST = Path("artifacts/forecasts/manifest.json")
OUT = Path("artifacts/unseal_2026")
HOLDOUT_YEAR = 2026
LAST_TARGET_WEEK = pd.Timestamp("2026-12-29")
LOOKS_BEFORE = 3
RELIABILITY_MAX = 0.05
MIN_N = 100
SCORED_STATES = ("probability", "base_rate")


@dataclass
class Check:
    """One precondition, with what was observed and what was required."""

    name: str
    ok: bool
    observed: str
    required: str


@dataclass
class Hooks:
    """What the preconditions consult, replaceable in tests so no real clock or repository state is needed."""

    config_hash: Callable[[], str] = field(default_factory=lambda: _freeze().config_hash)
    model_matches: Callable[[str], tuple[bool, list[str]]] = field(default_factory=lambda: _freeze().model_files_match)
    look_count: Callable[[], int] = field(default_factory=lambda: _freeze().look_count)
    tree_clean: Callable[[], bool] = field(default_factory=lambda: _freeze().working_tree_clean)


def _freeze() -> Any:
    from cofire.model import freeze

    return freeze


def sha256(path: Path) -> str:
    """The sha256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unseal_date() -> datetime:
    """The unseal date from app/lib/seal.json, as midnight UTC."""
    d = json.loads(SEAL.read_text())["unseal_date"]
    return datetime.fromisoformat(f"{d}T00:00:00+00:00")


def preconditions(now: datetime, env: Mapping[str, str], out: Path = OUT, hooks: Hooks | None = None) -> list[Check]:
    """Every precondition in the preregistration, in order; nothing here reads 2026 outcomes."""
    h = hooks or Hooks()
    checks: list[Check] = []
    when = unseal_date()
    checks.append(Check("the unseal date has come", now >= when, now.isoformat(), f"on or after {when.date()} (UTC)"))
    flag = env.get("COFIRE_ALLOW_LOOK", "").strip()
    checks.append(Check("COFIRE_ALLOW_LOOK=4 is set", flag == "4", flag or "unset", "4"))
    commit = FREEZE_COMMIT.read_text().strip() if FREEZE_COMMIT.exists() else ""
    same, changed = h.model_matches(commit) if commit else (False, ["no FREEZE_COMMIT"])
    checks.append(Check("cofire/model/ matches FREEZE_COMMIT", same, "no file differs" if same else f"differs: {changed}", f"no diff against {commit[:12]}"))
    cfg = h.config_hash()
    checks.append(Check("configuration hash matches", cfg == CONFIG_HASH, cfg[:16], CONFIG_HASH[:16]))
    for path, pinned in ((LOOK3_PREREG, LOOK3_PREREG_SHA256), (PREREG, PREREG_SHA256)):
        got = sha256(path) if path.exists() else "missing"
        checks.append(Check(f"{path} is unchanged", got == pinned, got[:16], pinned[:16]))
    n = h.look_count()
    checks.append(Check(f"the look counter for {HOLDOUT_YEAR} reads {LOOKS_BEFORE}", n == LOOKS_BEFORE, str(n), str(LOOKS_BEFORE)))
    checks.append(Check("the output directory is new", not out.exists(), "exists" if out.exists() else "absent", f"{out} absent"))
    clean = h.tree_clean()
    checks.append(Check("the working tree is clean", clean, "clean" if clean else "dirty", "clean"))
    return checks


def refuse_unless_ready(checks: list[Check]) -> None:
    """Stop, naming every failed precondition, unless all passed."""
    failed = [c for c in checks if not c.ok]
    if failed:
        lines = "\n".join(f"  FAIL {c.name}: {c.observed} (required: {c.required})" for c in failed)
        raise SystemExit(f"The unseal is not taken; nothing from {HOLDOUT_YEAR} was read.\n{lines}")


def published_forecasts(manifest: Path = MANIFEST) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Every published forecast with its manifest entry, each file read only after its sha256 matches."""
    entries: list[dict[str, Any]] = json.loads(manifest.read_text())
    out = []
    for e in entries:
        blob = (manifest.parent / e["file"]).read_bytes()
        got = hashlib.sha256(blob).hexdigest()
        if got != e["sha256"]:
            raise SystemExit(f"{e['file']}: sha256 {got} does not match the manifest's {e['sha256']}; nothing is scored")
        out.append((e, json.loads(gzip.decompress(blob))))
    return out


def forecast_rows(published: list[tuple[dict[str, Any], dict[str, Any]]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long tables of the counted probability and dryness forecasts, as published."""
    probs: list[dict[str, Any]] = []
    dry: list[dict[str, Any]] = []
    for entry, payload in published:
        issue = pd.Timestamp(payload["issue"])
        for dom, b in payload["domains"].items():
            dec = b["decisions"]["targets"]
            for c in b["cells"]:
                for i, t in enumerate(b["targets"]):
                    state = dec.get(t, ["not_shown", ""])[0]
                    p = c["p"][i] if i < len(c["p"]) else None
                    h = int(t.rsplit("_h", 1)[1])
                    if state in SCORED_STATES and p is not None and issue + pd.Timedelta(weeks=h) <= LAST_TARGET_WEEK:
                        probs.append({"issue": issue, "domain": dom, "cell_id": c["id"], "target": t, "horizon": h,
                                      "state": state, "p": float(p), "backfilled": bool(entry.get("backfilled"))})
                for hs, vals in (c.get("h") or {}).items():
                    h = int(hs)
                    if vals and vals[0] is not None and issue + pd.Timedelta(weeks=h) <= LAST_TARGET_WEEK:
                        dry.append({"issue": issue, "domain": dom, "cell_id": c["id"], "horizon": h, "forecast": float(vals[0])})
    return pd.DataFrame(probs), pd.DataFrame(dry)


def outcomes(domain: str) -> pd.DataFrame:
    """The realized 2026 targets for a domain, through the training record's own builder and labels.

    This reads 2026 outcomes. It is called only after every precondition has passed.
    """
    from cofire.ship import build_v11, fit_v11

    f = build_v11.load(domain)
    g = fit_v11.with_targets(f, pd.to_numeric(f["erc_pct"], errors="coerce").to_numpy(float))
    g = g[pd.to_datetime(g["time"]).dt.year == HOLDOUT_YEAR].copy()
    g["issue"] = pd.to_datetime(g["time"])
    return g


def score_probability(p: np.ndarray, y: np.ndarray, weeks: np.ndarray, state: str) -> tuple[dict[str, Any], list[dict[str, float]]]:
    """Brier, its reliability and resolution terms, and the reliability diagram, with the pass judgement."""
    from cofire.model.prob_metrics import brier, brier_decomposition
    from cofire.model.stats_lib import reliability_sklearn

    m = np.isfinite(p) & np.isfinite(y)
    p, y, weeks = p[m], y[m], weeks[m]
    n = int(m.sum())
    if n == 0:
        return {"n": 0, "judged": False, "verdict": "no outcomes"}, []
    dec = brier_decomposition(p, y)
    rel = float(dec["reliability"])
    pos_weeks = int(pd.DataFrame({"w": weeks, "y": y}).groupby("w")["y"].max().gt(0).sum())
    judged = state == "probability" and n >= MIN_N
    verdict = ("pass" if rel <= RELIABILITY_MAX else "fail") if judged else ("reported only (regional rate)" if state == "base_rate" else "too few to judge")
    row = {"n": n, "positive_weeks": pos_weeks, "base_rate": round(float(y.mean()), 5), "brier": round(brier(p, y), 6),
           "reliability": round(rel, 6), "resolution": round(float(dec["resolution"]), 6), "judged": judged, "verdict": verdict}
    frac, mean_pred = reliability_sklearn(p, y, n_bins=10)
    return row, [{"forecast": round(float(e), 5), "observed": round(float(o), 5)} for o, e in zip(frac.tolist(), mean_pred.tolist(), strict=True)]


def score_dryness(forecast: np.ndarray, measured: np.ndarray) -> dict[str, Any]:
    """Mean absolute error, root mean square error and mean error of the dryness point forecasts."""
    m = np.isfinite(forecast) & np.isfinite(measured)
    e = forecast[m] - measured[m]
    if not len(e):
        return {"n": 0}
    return {"n": int(len(e)), "mae": round(float(np.abs(e).mean()), 3), "rmse": round(float(np.sqrt((e ** 2).mean())), 3), "bias": round(float(e.mean()), 3)}


def main(now: datetime | None = None, env: Mapping[str, str] | None = None, out: Path = OUT, hooks: Hooks | None = None) -> Path:
    """The unseal: check, read, score, write once, record the look."""
    now = now or datetime.now(UTC)
    checks = preconditions(now, os.environ if env is None else env, out, hooks)
    refuse_unless_ready(checks)

    published = published_forecasts()
    probs, dry = forecast_rows(published)
    prob_rows: list[dict[str, Any]] = []
    diagram: list[dict[str, Any]] = []
    dry_rows: list[dict[str, Any]] = []
    for dom in sorted(set(probs["domain"]) | set(dry["domain"])):
        realized = outcomes(dom)
        pd_ = probs[probs["domain"] == dom]
        for (target, state), grp in pd_.groupby(["target", "state"]):
            j = grp.merge(realized[["issue", "cell_id", target]], on=["issue", "cell_id"], how="left")
            weeks = (j["issue"] + pd.to_timedelta(j["horizon"], unit="W")).to_numpy()
            row, diag = score_probability(j["p"].to_numpy(float), pd.to_numeric(j[target], errors="coerce").to_numpy(float), weeks, str(state))
            prob_rows.append({"domain": dom, "target": target, "state": state, **row})
            diagram += [{"domain": dom, "target": target, **d} for d in diag]
        dd = dry[dry["domain"] == dom]
        for h, grp in dd.groupby("horizon"):
            col = f"erc_pct_h{int(h)}"
            j = grp.merge(realized[["issue", "cell_id", col]], on=["issue", "cell_id"], how="left")
            dry_rows.append({"domain": dom, "horizon": int(h), **score_dryness(j["forecast"].to_numpy(float), pd.to_numeric(j[col], errors="coerce").to_numpy(float))})

    from cofire.model.freeze import config_hash, record_look
    from cofire.ship import vintages

    # Everything is computed. Write once, into a directory that must be new.
    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(prob_rows).to_csv(out / "probability.csv", index=False)
    pd.DataFrame(diagram).to_csv(out / "reliability_diagram.csv", index=False)
    pd.DataFrame(dry_rows).to_csv(out / "dryness.csv", index=False)
    n = record_look(HOLDOUT_YEAR, config_hash(), "look 4, the unseal (docs/PREREGISTRATION_UNSEAL.md)")
    judged = [r for r in prob_rows if r.get("judged")]
    (out / "provenance.json").write_text(json.dumps({
        "holdout_year": HOLDOUT_YEAR, "look_index": n, "run_at": now.isoformat(),
        "preregistration_sha256": PREREG_SHA256, "look3_preregistration_sha256": LOOK3_PREREG_SHA256,
        "config_hash": CONFIG_HASH, "freeze_commit": FREEZE_COMMIT.read_text().strip(),
        "forecast_files_verified": len(published), "backfilled_issues": sum(1 for e, _ in published if e.get("backfilled")),
        "last_target_week": str(LAST_TARGET_WEEK.date()),
        "probability_pairs_judged": len(judged), "probability_pairs_passing": sum(1 for r in judged if r["verdict"] == "pass"),
        "gridmet_vintages": [r for r in vintages.manifest() if str(HOLDOUT_YEAR) in json.dumps(r)][-10:],
        "provisional_note": "gridMET values for late 2026 are still provisional on the unseal date; the vintages read are listed above.",
        "preconditions": [asdict(c) for c in checks],
    }, indent=1, default=str) + "\n")
    return out


if __name__ == "__main__":
    print(main())
    sys.exit(0)
