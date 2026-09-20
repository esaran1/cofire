"""Freeze a committable demo fixture set. INTENDED FOR HAND-REWRITE.

A judge clones the repo on a laptop with no credentials and runs `make demo`.
That must work offline, with real numbers, without running the pipeline. This
module assembles the smallest fixture set that serves every route, under 200 MB.

Contents:
  - the latest issue's forecast cells (Place Cards, map grid)
  - the May 1 hindcast issue (the replay link on the Hindcast screen)
  - the 2026 coverage series and the conformal/bootstrap comparison
  - the fires table plus its matched non-fire control
  - the multiregime results and the LODO summary
  - metrics, sanity, the regime pool and the run log

Nothing here evaluates anything. It copies and subsets existing artifacts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from cofire.model.config import get_settings

DEMO_DIR = Path("demo")
MAY1_ISSUE = "2026-05-05"
SIZE_CAP_MB = 200


def _copy(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return sum(f.stat().st_size for f in dst.rglob("*") if f.is_file())
    shutil.copy2(src, dst)
    return dst.stat().st_size


def _subset_index(index: dict[str, Any], issues: list[str]) -> dict[str, Any]:
    """Keep only the named issues' cells, so the fixture stays small."""
    keep = set(issues)
    cells = [c for c in index.get("cells", []) if c.get("issue") in keep]
    out = dict(index)
    out["cells"] = cells
    out["issues"] = [i for i in index.get("issues", []) if i in keep]
    out["demo_fixture"] = True
    out["demo_note"] = (
        "Subset of the full export: only the issues the demo needs. "
        "Regenerate the full index with `make export`."
    )
    return out


def build(out_dir: Path = DEMO_DIR) -> dict[str, Any]:
    settings = get_settings()
    art = settings.artifacts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"files": {}, "bytes": 0}

    index_path = art / "forecast_index.json"
    if not index_path.exists():
        raise SystemExit("no forecast_index.json - run `make export` first")
    index = json.loads(index_path.read_text())
    issues = index.get("issues", [])
    latest = issues[-1] if issues else None
    wanted = [i for i in (latest, MAY1_ISSUE) if i and i in issues]
    if not wanted:
        wanted = issues[-1:]
    slim = _subset_index(index, wanted)
    target = out_dir / "artifacts" / "forecast_index.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(slim))
    report["files"]["forecast_index.json"] = target.stat().st_size
    report["issues_kept"] = wanted
    report["cells_kept"] = len(slim["cells"])

    # Everything else is small enough to copy verbatim.
    for rel in (
        "metrics.json",
        "metrics.md",
        "sanity.json",
        "sanity.md",
        "shipping_arm.txt",
        "runtime.json",
        "why.json",
        "hindcast/fires.json",
        "hindcast/fires.md",
        "hindcast/control.json",
        "hindcast/run_log.json",
        "hindcast/coverage.png",
        "uncertainty/comparison.json",
        "uncertainty/comparison.md",
        "uncertainty/coverage_2026.png",
        "uncertainty/multiregime.json",
        "uncertainty/multiregime.md",
        "uncertainty/regime_pool.json",
        "uncertainty/diagnosis.md",
        "uncertainty/leak_check.md",
        "lodo/folds.json",
        "lodo/lodo.md",
        "lodo/coverage.json",
        "profile/throughput.md",
    ):
        n = _copy(art / rel, out_dir / "artifacts" / rel)
        if n:
            report["files"][rel] = n

    # A feature slice so Place Cards can render drivers offline.
    feat = settings.processed_dir / "features"
    latest_year = "2026"
    src = feat / f"year={latest_year}.parquet"
    if src.exists():
        n = _copy(src, out_dir / "features" / f"year={latest_year}.parquet")
        report["files"][f"features/year={latest_year}.parquet"] = n

    # MANIFEST so the About screen shows real provenance.
    man = settings.data_dir / "MANIFEST.json"
    if man.exists():
        report["files"]["MANIFEST.json"] = _copy(man, out_dir / "MANIFEST.json")

    total = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
    report["bytes"] = total
    report["megabytes"] = round(total / 1e6, 1)
    report["under_cap"] = total < SIZE_CAP_MB * 1e6
    report["cap_mb"] = SIZE_CAP_MB
    (out_dir / "MANIFEST_DEMO.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    r = build()
    print(f"demo fixture: {r['megabytes']} MB ({'OK' if r['under_cap'] else 'OVER CAP'}), "
          f"{r.get('cells_kept', 0)} cells across {r.get('issues_kept')}")
