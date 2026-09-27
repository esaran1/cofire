"""Per-domain forecast bundles for the app, one small JSON per domain and issue.

The monolithic forecast index repeats every target's state and reason on every
cell of every issue and has grown past 240 MB. A bundle stores each decision
once per domain and each cell's probabilities as an array aligned to one target
list, so a whole domain-issue is tens of kilobytes. The API serves bundles, and
a static build can serve the same files unchanged.

Denver's bundle also carries its source watersheds: the fire-spread odds in the
Upper South Platte above Strontia Springs and the Blue River above Dillon, the
two collection areas Denver Water draws from.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cofire.ship import domains
from cofire.ship.index_build import HISTORY_YEARS

LOGGER = logging.getLogger("cofire.ship.bundles")

EXPORT = Path("artifacts/ship/forecast_issues.parquet")
OUT = Path("artifacts/ship/domains")
HORIZONS = (2, 4, 8)
SOURCES = {"denver": ("upper_south_platte", "dillon")}
KIND_NOTE = {
    "urban": "City and County of Denver, including the Glendale and Holly Hills enclaves.",
    "watershed": "A collection area Denver Water draws from.",
    "county": "County-wide forecast domain.",
}
# Which Ember checklist a domain opens with. Denver is a city; the rest are
# foothill and wildland-edge terrain.
EMBER_ZONE = {"denver": "city"}


def _num(v: Any, nd: int = 4) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if np.isfinite(f) else None


def _meta(dom: str, frame: pd.DataFrame) -> dict[str, Any]:
    fps = domains.load()
    if dom in fps:
        fp = fps[dom]
        kind, bbox, n = str(fp["kind"]), [float(v) for v in fp["bbox"]], len(fp["cells"])
        matched = fp["matched"]
    else:
        from cofire.model import config

        kind, n = "county", int(frame["cell_id"].nunique())
        bbox = [float(v) for v in config.SUBSETS[dom][0]]
        matched = {"FIPS": config.SUBSETS[dom][1]}
    return {
        "domain": dom, "label": domains.LABELS[dom], "kind": kind, "note": KIND_NOTE[kind],
        "bbox": bbox, "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
        "n_cells": n, "matched": matched, "sources": list(SOURCES.get(dom, ())),
        "ember_zone": EMBER_ZONE.get(dom, "wui"),
        "evaluation": "validation" if dom in domains.NEW else "look3",
    }


def _decisions(frame: pd.DataFrame, targets: list[str]) -> dict[str, Any]:
    row = frame.iloc[0]
    probs = {t: [row.get(f"{t}_state"), row.get(f"{t}_reason")] for t in targets}
    cont = {str(h): [row.get(f"erc_pct_h{h}_state"), row.get(f"erc_pct_h{h}_reason")] for h in HORIZONS}
    return {"targets": probs, "horizons": cont}


def _cell(row: pd.Series, targets: list[str]) -> dict[str, Any]:
    t0 = pd.Timestamp(row["time"])
    return {
        "id": str(row["cell_id"]), "lat": _num(row["lat"], 5), "lon": _num(row["lon"], 5),
        "erc": _num(row.get("erc"), 1), "erc_pct": _num(row.get("erc_pct"), 1),
        "usdm": _num(row.get("usdm"), 0),
        "p": [_num(row.get(f"{t}_p")) for t in targets],
        "h": {
            str(h): [
                _num(row.get(f"erc_pct_h{h}_point"), 1),
                _num(row.get(f"erc_h{h}_hist_lo"), 1),
                _num(row.get(f"erc_h{h}_hist_hi"), 1),
                (t0 + pd.Timedelta(weeks=h)).strftime("%Y-%m-%d"),
            ]
            for h in HORIZONS
        },
    }


def _summary(frame: pd.DataFrame, targets: list[str]) -> dict[str, Any]:
    """Domain-wide fire-spread odds and ERC outlook, for the watershed panel."""
    out: dict[str, Any] = {}
    for h in HORIZONS:
        blk: dict[str, Any] = {"erc_pct_median": _num(frame[f"erc_pct_h{h}_point"].median(), 1)}
        for t in targets:
            if not t.startswith("f_gt") or not t.endswith(f"_h{h}"):
                continue
            p = pd.to_numeric(frame[f"{t}_p"], errors="coerce")
            blk[t] = {"mean": _num(p.mean()), "min": _num(p.min()), "max": _num(p.max()),
                      "state": frame[f"{t}_state"].iloc[0]}
        out[str(h)] = blk
    out["erc_pct_now_median"] = _num(frame["erc_pct"].median(), 1)
    return out


def build(export: Path = EXPORT, out: Path = OUT) -> dict[str, Any]:
    frame = pd.read_parquet(export)
    frame["time"] = pd.to_datetime(frame["time"])
    targets = sorted(c[: -len("_p")] for c in frame.columns if c.endswith("_p"))
    issues = sorted(frame["time"].dt.strftime("%Y-%m-%d").unique().tolist())
    out.mkdir(parents=True, exist_ok=True)
    order = [d for d in domains.ORDER if d in set(frame["domain"])]
    index: dict[str, Any] = {
        "default": domains.DEFAULT, "order": order, "issues": issues, "targets": targets,
        "resolution_m": 4000, "history_years": HISTORY_YEARS,
        "domains": {d: _meta(d, frame[frame["domain"] == d]) for d in order},
    }
    sizes: dict[str, int] = {}
    for dom in order:
        fd = frame[frame["domain"] == dom]
        (out / dom).mkdir(exist_ok=True)
        dec = _decisions(fd, targets)
        for issue, fi in fd.groupby(fd["time"].dt.strftime("%Y-%m-%d")):
            bundle: dict[str, Any] = {
                "domain": dom, "issue": issue, "targets": targets, "decisions": dec,
                "cells": [_cell(r, targets) for _, r in fi.iterrows()],
                "summary": _summary(fi, targets),
                "sources": {
                    s: {"label": domains.LABELS[s],
                        "summary": _summary(frame[(frame["domain"] == s) & (frame["time"] == fi["time"].iloc[0])], targets),
                        "decisions": _decisions(frame[frame["domain"] == s], targets)["targets"]}
                    for s in SOURCES.get(dom, ())
                },
            }
            path = out / dom / f"{issue}.json"
            path.write_text(json.dumps(bundle, separators=(",", ":")))
            sizes[dom] = sizes.get(dom, 0) + path.stat().st_size
    (out / "index.json").write_text(json.dumps(index, indent=1))
    LOGGER.info("bundles: %s", {d: f"{b / 1e6:.2f} MB" for d, b in sizes.items()})
    return index


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    idx = build()
    print(len(idx["issues"]), "issues,", len(idx["order"]), "domains")


def legacy_cells(root: Path = OUT) -> dict[str, Any]:
    """The old forecast-index structure, rebuilt from the bundles under `root`.

    The API's cell endpoints (`/forecast`, `/predictions`, `/observations`)
    were written against one index of every cell and issue. Rebuilding that
    view from the bundles keeps them working for every domain without writing
    the 240 MB file.
    """
    idx = json.loads((root / "index.json").read_text())
    cells: list[dict[str, Any]] = []
    issues: set[str] = set()
    for dom in idx["order"]:
        for path in sorted((root / dom).glob("*.json")):
            b = json.loads(path.read_text())
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
                })
    return {
        "resolution_m": 4000,
        "resolution_note": "4 km gridMET cells. The displayed value is the cell's own, not an interpolation to a point.",
        "issues": sorted(issues), "cells": cells, "domains": idx["order"], "targets": idx["targets"],
        "configuration": "frozen at FREEZE_COMMIT; see docs/PREREGISTRATION_LOOK3.md",
    }
