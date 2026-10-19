"""Every forecast cell and issue, rebuilt from the per-domain bundles.

The API's cell endpoints (`/forecast`, `/predictions`, `/observations`) were
written against one index of every cell and issue. Rebuilding that view from
the bundles keeps them working for every domain without writing the 240 MB
file.

The bundles are read from a folder (`artifacts/ship/domains`, local runs) or
from a base URL. On Vercel the api service reads the copies the web service
publishes under `/data/domains/`, so its function carries no data and needs
nothing beyond the standard library here: no numpy, pandas or geopandas.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

FETCH_TIMEOUT_S = 30
FETCH_WORKERS = 16


def _url_reader(base: str) -> Callable[[str], Any]:
    root = base if base.endswith("/") else base + "/"

    def read(rel: str) -> Any:
        req = urllib.request.Request(root + rel, headers={"User-Agent": "cofire-api"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as r:
            return json.loads(r.read())

    return read


def legacy_cells(source: Path | str) -> dict[str, Any]:
    """The old forecast-index structure, rebuilt from the bundles under `source`.

    `source` is the bundle folder, or a base URL serving the same layout
    (`index.json`, then `<domain>/<issue>.json`). From a folder every bundle
    file present is read; from a URL, every issue the index lists.
    """
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        read = _url_reader(source)
        idx = read("index.json")
        rels = [f"{dom}/{issue}.json" for dom in idx["order"] for issue in idx["issues"]]
        with ThreadPoolExecutor(FETCH_WORKERS) as pool:
            bundles = list(zip(rels, pool.map(read, rels), strict=True))
    else:
        root = Path(source)
        idx = json.loads((root / "index.json").read_text())
        bundles = [
            (f"{dom}/{path.name}", json.loads(path.read_text()))
            for dom in idx["order"] for path in sorted((root / dom).glob("*.json"))
        ]
    cells: list[dict[str, Any]] = []
    issues: set[str] = set()
    for rel, b in bundles:
        dom = rel.split("/", 1)[0]
        issues.add(b["issue"])
        dec_t, dec_h = b["decisions"]["targets"], b["decisions"]["horizons"]
        for c in b["cells"]:
            horizons: dict[str, Any] = {}
            for h, (point, lo, hi, week) in c["h"].items():
                state, reason = dec_h.get(h, [None, None])
                blk: dict[str, Any] = {"point": point, "state": state, "reason": reason}
                if lo is not None and hi is not None:
                    blk |= {"hist_lo": lo, "hist_hi": hi, "hist_years": idx["history_years"], "target_week": week}
                horizons[h] = blk
            cells.append({
                "cell_id": c["id"], "lat": c["lat"], "lon": c["lon"], "issue": b["issue"],
                "domain": dom, "resolution_m": 4000, "erc": c["erc"], "erc_pct": c["erc_pct"],
                "usdm": c["usdm"], "horizons": horizons,
                "targets": {t: {"p": c["p"][i], "state": dec_t[t][0], "reason": dec_t[t][1]}
                            for i, t in enumerate(b["targets"])},
                "model": dict(zip(b.get("model_targets", []), c.get("m", []), strict=False)),
            })
    return {
        "resolution_m": 4000,
        "resolution_note": "4 km gridMET cells. The displayed value is the cell's own, not an interpolation to a point.",
        "issues": sorted(issues), "cells": cells, "domains": idx["order"], "targets": idx["targets"],
        "configuration": "frozen at FREEZE_COMMIT; see docs/PREREGISTRATION_LOOK3.md",
    }
