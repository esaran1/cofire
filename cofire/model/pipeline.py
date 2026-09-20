"""Run pipeline stages with wall-clock and peak RSS. Stop at 60 minutes."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import time
from pathlib import Path

from cofire.model.config import get_settings
from cofire.model.log import setup_logging
from cofire.model.train import git_sha

STAGE_TIMEOUT_S = 60 * 60
STAGES = ("sanity", "train", "calibrate", "hindcast", "export")


def _rss_kb(pid: int) -> int:
    """Sum RSS of pid and every descendant (uv wrapper is otherwise a few MB)."""
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,ppid=,rss="], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    rows: list[tuple[int, int, int]] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), int(parts[2])))
        except ValueError:
            continue
    keep = {pid}
    changed = True
    while changed:
        changed = False
        for child, parent, _rss in rows:
            if parent in keep and child not in keep:
                keep.add(child)
                changed = True
    return sum(rss for child, _parent, rss in rows if child in keep)


def run_stage(name: str, module: str, timeout_s: int = STAGE_TIMEOUT_S) -> dict[str, object]:
    log = setup_logging(get_settings().log_dir)
    env = os.environ.copy()
    env.setdefault("COFIRE_DEV_SUBSET", "1")
    # LightGBM then PyTorch in one process deadlocks OpenMP on macOS if both use many threads.
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    t0 = time.time()
    proc = subprocess.Popen(["uv", "run", "python", "-m", module], env=env)
    peak = _rss_kb(proc.pid)
    while proc.poll() is None:
        peak = max(peak, _rss_kb(proc.pid))
        if time.time() - t0 > timeout_s:
            proc.kill()
            elapsed = time.time() - t0
            raise SystemExit(
                f"{name} exceeded {timeout_s / 60:.0f} minutes (elapsed {elapsed / 60:.1f}). "
                "Stopped rather than continuing. Inspect logs/cofire.log for the bottleneck."
            )
        time.sleep(2)
        peak = max(peak, _rss_kb(proc.pid))
    elapsed = time.time() - t0
    rec = {
        "stage": name,
        "module": module,
        "exit_code": proc.returncode,
        "wall_seconds": round(elapsed, 2),
        "peak_rss_mb": round(peak / 1024.0, 1),
    }
    log.info("%s done exit=%s wall=%.1fs peak_rss=%.1f MB", name, proc.returncode, elapsed, peak / 1024.0)
    if proc.returncode != 0:
        rec["failed"] = True
        out = get_settings().artifacts_dir / "runtime.json"
        existing: dict[str, object] = json.loads(out.read_text()) if out.exists() else {"stages": []}
        raw_stages = existing.get("stages", [])
        stages: list[object] = list(raw_stages) if isinstance(raw_stages, list) else []
        stages.append(rec)
        out.write_text(json.dumps({"git_sha": git_sha(), "dev_subset": get_settings().dev_subset, "stages": stages}, indent=2))
        from cofire.model.status import write_status

        with contextlib.suppress(Exception):
            write_status()
        raise SystemExit(f"{name} failed with exit {proc.returncode}")
    return rec


def run_pipeline() -> Path:
    settings = get_settings()
    records: list[dict[str, object]] = []
    mapping = {
        "sanity": "cofire.model.sanity",
        "train": "cofire.model.train",
        "calibrate": "cofire.model.calibrate",
        "hindcast": "cofire.model.hindcast",
        "export": "cofire.model.export",
    }
    for name in STAGES:
        records.append(run_stage(name, mapping[name]))
    payload = {"git_sha": git_sha(), "dev_subset": settings.dev_subset, "stages": records}
    out = settings.artifacts_dir / "runtime.json"
    out.write_text(json.dumps(payload, indent=2))
    from cofire.model.status import write_status

    write_status()
    return out


if __name__ == "__main__":
    run_pipeline()
