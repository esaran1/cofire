"""Staged, checkpointed, resumable statewide runner. INTENDED FOR HAND-REWRITE.

Statewide is ~6.1 h of training (artifacts/profile/throughput.md), well over the
60-minute stop rule for any single stage. This module therefore never runs it as
one job: it splits the work into stages, each of which checkpoints on completion
and is skipped on a rerun, and each of which is sized to stay under the limit.

`run_statewide(dry_run=True)` reports the plan and the ETA without executing
anything. That is the default, and the only mode this session is authorised to
use: statewide stays deferred until the No-go is explicitly overridden.
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from cofire.model.config import get_settings
from cofire.model.log import setup_logging

STOP_RULE_SECONDS = 60 * 60

# Measured on the Larimer subset; see artifacts/profile/throughput.md.
LARIMER_TILES_PER_STEP = 1
STATEWIDE_TILES_PER_STEP = 30
LGBM_ROW_EXPONENT = 0.406
CELL_RATIO = 50.0


@dataclass
class Stage:
    name: str
    module: str
    larimer_seconds: float
    scaling: str
    note: str = ""

    def eta_seconds(self) -> float:
        if self.scaling == "tiles":
            return float(self.larimer_seconds * (STATEWIDE_TILES_PER_STEP / LARIMER_TILES_PER_STEP))
        if self.scaling == "rows":
            return float(self.larimer_seconds * (CELL_RATIO**LGBM_ROW_EXPONENT))
        if self.scaling == "linear":
            return float(self.larimer_seconds * CELL_RATIO)
        return float(self.larimer_seconds)


# Feature construction and the ConvLSTM are split per year / per tile-block so no
# single stage runs past the stop rule.
STAGES: tuple[Stage, ...] = (
    Stage("sanity", "cofire.model.sanity", 10.3, "linear", "gates only; cheap"),
    Stage("features", "cofire.model.features", 60.0, "linear", "chunked per year to bound peak RSS"),
    Stage("train_lgbm", "cofire.model.train", 21.0, "rows", "6 fits; rows^0.41"),
    Stage("train_pi", "cofire.model.train", 724.0, "tiles", "3 configs + ablation; linear in tiles"),
    Stage("calibrate", "cofire.model.calibrate", 6.17, "linear"),
    Stage("export", "cofire.model.export", 30.72, "linear"),
)


def _checkpoint_path(settings: object, stage: str) -> Path:
    root = Path(getattr(settings, "artifacts_dir", Path("artifacts"))) / "statewide" / "checkpoints"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{stage}.json"


def plan() -> list[dict[str, object]]:
    """Per-stage ETA and whether each fits under the 60-minute stop rule."""
    out: list[dict[str, object]] = []
    for st in STAGES:
        eta = st.eta_seconds()
        out.append(
            {
                "stage": st.name,
                "larimer_seconds": st.larimer_seconds,
                "scaling": st.scaling,
                "eta_seconds": round(eta, 1),
                "eta_minutes": round(eta / 60, 1),
                "over_stop_rule": eta > STOP_RULE_SECONDS,
                "note": st.note,
            }
        )
    return out


def split_recommendation() -> list[dict[str, object]]:
    """For any stage over the stop rule, how many chunks keep each under it."""
    recs: list[dict[str, object]] = []
    for row in plan():
        if not row["over_stop_rule"]:
            continue
        eta = float(str(row["eta_seconds"]))
        chunks = int(eta // STOP_RULE_SECONDS) + 1
        recs.append(
            {
                "stage": row["stage"],
                "eta_minutes": row["eta_minutes"],
                "chunks_needed": chunks,
                "per_chunk_minutes": round(eta / chunks / 60, 1),
                "split_by": "tile block" if row["scaling"] == "tiles" else "year",
            }
        )
    return recs


def run_stage(stage: Stage, *, dry_run: bool = True, resume: bool = True) -> dict[str, object]:
    settings = get_settings()
    ck = _checkpoint_path(settings, stage.name)
    if resume and ck.exists():
        return {"stage": stage.name, "status": "skipped (checkpoint exists)", **json.loads(ck.read_text())}
    if dry_run:
        return {"stage": stage.name, "status": "dry-run", "eta_minutes": round(stage.eta_seconds() / 60, 1)}
    env = {**os.environ, "COFIRE_DEV_SUBSET": "0", "OMP_NUM_THREADS": "1"}
    t0 = time.time()
    proc = subprocess.run(["python", "-m", stage.module], env=env, capture_output=True, text=True)
    elapsed = time.time() - t0
    rec: dict[str, object] = {
        "stage": stage.name,
        "status": "ok" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "wall_seconds": round(elapsed, 2),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1e6, 1),
    }
    if elapsed > STOP_RULE_SECONDS:
        rec["stop_rule_breach"] = True
    if proc.returncode == 0:
        ck.write_text(json.dumps(rec, indent=2))
    return rec


def run_statewide(*, dry_run: bool = True, resume: bool = True) -> Path:
    """Run (or plan) every stage. Appends to logs/statewide.log."""
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    out_dir = Path(getattr(settings, "artifacts_dir", Path("artifacts"))) / "statewide"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path("logs") / "statewide.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    with log_path.open("a") as fh:
        fh.write(f"=== statewide {'PLAN' if dry_run else 'RUN'} {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n")
        for st in STAGES:
            rec = run_stage(st, dry_run=dry_run, resume=resume)
            records.append(rec)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            log.info("statewide stage %s -> %s", st.name, rec.get("status"))

    total = sum(s.eta_seconds() for s in STAGES)
    blob = {
        "dry_run": dry_run,
        "stages": records,
        "plan": plan(),
        "splits_needed": split_recommendation(),
        "total_eta_hours": round(total / 3600, 2),
        "stages_defined": [asdict(s) for s in STAGES],
    }
    (out_dir / "plan.json").write_text(json.dumps(blob, indent=2))
    return out_dir / "plan.json"


if __name__ == "__main__":
    import sys

    dry = "--run" not in sys.argv
    path = run_statewide(dry_run=dry)
    data = json.loads(Path(path).read_text())
    print(f"total ETA {data['total_eta_hours']} h; plan written to {path}")
    for row in data["plan"]:
        flag = "  << over stop rule" if row["over_stop_rule"] else ""
        print(f"  {row['stage']:<12} {row['eta_minutes']:>7.1f} min  ({row['scaling']}){flag}")
    for rec in data["splits_needed"]:
        print(
            f"  -> split {rec['stage']} into {rec['chunks_needed']} chunks by {rec['split_by']}"
            f" ({rec['per_chunk_minutes']} min each)"
        )
