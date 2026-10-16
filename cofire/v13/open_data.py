"""Open data: every published forecast as CSV, GeoJSON and JSON, under CC BY 4.0.

    python -m cofire.v13.open_data [out_dir]

Reads the per-domain bundles the app serves (`cofire.ship.bundles`) and the
vintage each issue is pinned to (`artifacts/ship/issue_vintages.json`), and
writes, by default to `artifacts/ship/open/`:

* `cofire_latest.csv`, `cofire_latest.geojson`, `cofire_latest.json`: the
  latest issue, uncompressed;
* `issues/cofire_<issue>.csv.gz` and `issues/cofire_<issue>.geojson.gz`:
  every published issue, gzipped (each uncompressed CSV is several MB; they
  compress about twenty-fold);
* `index.json`: the endpoint a program starts from, with the license,
  attribution, field definitions, and every file with its size and sha256;
* `LICENSE.md`: the CC BY 4.0 notice and upstream attribution.

Fields, one row per cell, target and issue: issue date, vintage (when the
dryness data behind the issue was fetched), area, cell (and its centre),
target, horizon in weeks, the live probability as published, its rendering
state, and the reason for that state. The probability is exactly the
bundle's: base rates are base rates, and a target the app does not show has
no number. Nothing here computes anything new, and nothing reads 2026
outcomes.

The static site build copies the output to `app/public/data/open/`; the API
serves the same files at `/open/{name}`.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from cofire.ship import bundles

OUT = Path("artifacts/ship/open")
VINTAGES = Path("artifacts/ship/issue_vintages.json")
HALF = 1 / 48  # half a gridMET cell in degrees, as the app draws cells
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
FIELDS: list[tuple[str, str, str]] = [
    ("issue", "date", "The forecast's issue date (a Tuesday, the drought map's date), YYYY-MM-DD."),
    ("vintage", "datetime", "When the gridMET dryness data behind this issue was fetched (UTC). Each issue is pinned to the data as it stood then; later revisions do not change it."),
    ("area", "string", "Forecast area: denver, upper_south_platte, dillon, larimer or pueblo."),
    ("cell", "string", "Cell id, the cell centre as latitude_longitude. Cells are gridMET's 1/24-degree grid, about 4 km."),
    ("lat", "number", "Latitude of the cell centre, degrees north."),
    ("lon", "number", "Longitude of the cell centre, degrees east (negative is west)."),
    ("target", "string", "What the probability is of, with its horizon: d_ge2 drought D2 or worse, d_ge3 D3 or worse, d_improve1 easing by at least one category, d_intensify1 / d_intensify2 worsening by at least one / two categories, d_nochange staying in the same category, f_gt80 / f_gt90 / f_gt97 fuel dryness (ERC) above the 80th / 90th / 97th percentile for the week; _hN is N weeks ahead."),
    ("horizon_weeks", "integer", "How many weeks after the issue date the target is about: 2, 4 or 8."),
    ("probability", "number", "The live probability as the app publishes it, 0 to 1, four decimals. Empty when the app shows no number for this target."),
    ("state", "string", "How the app shows this target: probability (this cell's forecast), base_rate (the area's usual rate for the time of year, the same in every cell), or a state in which no number is shown; the reason says why."),
    ("reason", "string", "Why the target is shown as it is, from the app's own rendering decision (for example the validation reliability, or too few events to check)."),
]


def _rows(bundle: dict[str, Any], vintage: str) -> list[list[Any]]:
    """The long-format rows of one domain's bundle."""
    out: list[list[Any]] = []
    targets: list[str] = bundle["targets"]
    dec: dict[str, list[str]] = bundle["decisions"]["targets"]
    for c in bundle["cells"]:
        p = c["p"]
        for i, t in enumerate(targets):
            state, reason = dec.get(t, ["not_shown", "no rendering decision"])
            prob = p[i] if i < len(p) else None
            out.append([bundle["issue"], vintage, bundle["domain"], c["id"], c["lat"], c["lon"], t,
                        int(t.rsplit("_h", 1)[1]), "" if prob is None else f"{prob:.4f}", state, reason])
    return out


def _csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([f[0] for f in FIELDS])
    w.writerows(rows)
    return buf.getvalue().encode()


def _geojson(issue: str, per_domain: list[tuple[dict[str, Any], str]]) -> bytes:
    """One feature per cell (its square); each target's probability and state flattened into properties."""
    features: list[dict[str, Any]] = []
    reasons: dict[str, dict[str, str]] = {}
    for b, vintage in per_domain:
        dec: dict[str, list[str]] = b["decisions"]["targets"]
        reasons[b["domain"]] = {t: v[1] for t, v in dec.items()}
        for c in b["cells"]:
            props: dict[str, Any] = {"issue": issue, "vintage": vintage, "area": b["domain"], "cell": c["id"]}
            for i, t in enumerate(b["targets"]):
                prob = c["p"][i] if i < len(c["p"]) else None
                props[f"p_{t}"] = None if prob is None else round(float(prob), 4)
                props[f"state_{t}"] = dec.get(t, ["not_shown", ""])[0]
            lat, lon = float(c["lat"]), float(c["lon"])
            ring = [[lon - HALF, lat - HALF], [lon + HALF, lat - HALF], [lon + HALF, lat + HALF], [lon - HALF, lat + HALF], [lon - HALF, lat - HALF]]
            features.append({"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [[[round(x, 6), round(y, 6)] for x, y in ring]]}})
    fc = {"type": "FeatureCollection", "license": LICENSE_URL, "issue": issue,
          "note": "p_<target> is the live probability as published (null when not shown), state_<target> its rendering state; reasons[area][target] says why.",
          "reasons": reasons, "features": features}
    return json.dumps(fc, separators=(",", ":")).encode()


def _json(issue: str, per_domain: list[tuple[dict[str, Any], str]]) -> bytes:
    """The latest issue as compact JSON: per area, its vintage, reasons, and each cell's probabilities in target order."""
    areas: dict[str, Any] = {}
    for b, vintage in per_domain:
        dec: dict[str, list[str]] = b["decisions"]["targets"]
        areas[b["domain"]] = {
            "vintage": vintage,
            "targets": b["targets"],
            "state": [dec.get(t, ["not_shown", ""])[0] for t in b["targets"]],
            "reason": [dec.get(t, ["", "no rendering decision"])[1] for t in b["targets"]],
            "cells": [{"cell": c["id"], "lat": c["lat"], "lon": c["lon"], "probability": [None if (c["p"][i] if i < len(c["p"]) else None) is None else round(float(c["p"][i]), 4) for i in range(len(b["targets"]))]} for c in b["cells"]],
        }
    return json.dumps({"issue": issue, "license": LICENSE_URL, "areas": areas}, separators=(",", ":")).encode()


def _attribution() -> list[dict[str, str]]:
    facts = json.loads(Path("app/lib/facts.json").read_text())
    keep = ("gridMET", "U.S. Drought Monitor", "USGS Watershed Boundary Dataset and NHD", "U.S. Census Bureau cartographic boundaries")
    return [{"name": c["name"], "use": c["use"], "credit": c["credit"], "license": c["license"], "url": c["url"]} for c in facts["credits"] if c["name"] in keep]


def _write(path: Path, data: bytes, gz: bool = False) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = gzip.compress(data, compresslevel=9, mtime=0) if gz else data
    path.write_bytes(blob)
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), **({"uncompressed_bytes": len(data)} if gz else {})}


def build(out: Path = OUT, src: Path = bundles.OUT, strict: bool = True, vintages_path: Path = VINTAGES) -> dict[str, Any]:
    """Write the open data from the bundles; return the index.

    `strict` (the published site) requires every issue to be pinned to a vintage;
    the API's demo fixture may carry issues that are not, which are marked unpinned.
    """
    idx = json.loads((src / "index.json").read_text())
    vintages: dict[str, dict[str, str]] = json.loads(vintages_path.read_text())
    if out.exists():
        shutil.rmtree(out)
    files: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    for issue in idx["issues"]:
        per: list[tuple[dict[str, Any], str]] = []
        for dom in idx["order"]:
            b = json.loads((src / dom / f"{issue}.json").read_text())
            vintage = vintages.get(dom, {}).get(issue)
            if vintage is None:
                if strict:
                    raise SystemExit(f"{dom} {issue} has no pinned vintage in {vintages_path}")
                vintage = "unpinned"
            per.append((b, vintage))
        rows = [r for b, v in per for r in _rows(b, v)]
        files[f"issues/cofire_{issue}.csv.gz"] = _write(out / "issues" / f"cofire_{issue}.csv.gz", _csv(rows), gz=True)
        files[f"issues/cofire_{issue}.geojson.gz"] = _write(out / "issues" / f"cofire_{issue}.geojson.gz", _geojson(issue, per), gz=True)
        issues.append({"issue": issue, "rows": len(rows), "csv": f"issues/cofire_{issue}.csv.gz", "geojson": f"issues/cofire_{issue}.geojson.gz",
                       "vintages": {b["domain"]: v for b, v in per}, "bundles": {b["domain"]: f"../domains/{b['domain']}/{issue}.json" for b, _ in per}})
        if issue == idx["issues"][-1]:
            files["cofire_latest.csv"] = _write(out / "cofire_latest.csv", _csv(rows))
            files["cofire_latest.geojson"] = _write(out / "cofire_latest.geojson", _geojson(issue, per))
            files["cofire_latest.json"] = _write(out / "cofire_latest.json", _json(issue, per))
    attribution = _attribution()
    license_md = "\n".join([
        "# COFIRE open data: license",
        "",
        f"The forecasts in this directory are licensed under the Creative Commons Attribution 4.0 International license (CC BY 4.0): {LICENSE_URL}",
        "",
        "Credit: COFIRE, Colorado drought and fire-spread condition forecasts.",
        "",
        "They are built from these upstream data sources, which keep their own terms:",
        "",
        *[f"- {a['name']} ({a['use']}): {a['credit']} License: {a['license']}. {a['url']}" for a in attribution],
        "",
        "These are forecasts of conditions that let fire spread and of drought categories, not of ignitions.",
        "Forecasts can be wrong; the app's Method page says how each number was checked.",
        "",
    ])
    files["LICENSE.md"] = _write(out / "LICENSE.md", license_md.encode())
    index = {
        "name": "COFIRE open data",
        "description": "Every published COFIRE forecast: drought and fire-spread condition probabilities for each 4 km cell of Denver, its two source watersheds, Larimer County and Pueblo County, 2 to 8 weeks ahead.",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL, "credit": "COFIRE, Colorado drought and fire-spread condition forecasts", "upstream": attribution},
        "latest": {"issue": idx["issues"][-1], "csv": "cofire_latest.csv", "geojson": "cofire_latest.geojson", "json": "cofire_latest.json"},
        "fields": [{"name": n, "type": t, "description": d} for n, t, d in FIELDS],
        "areas": {d: idx["domains"][d]["label"] for d in idx["order"]},
        "targets": idx["targets"],
        "issues": issues,
        "files": files,
        "generated_from": "artifacts/ship/domains (the bundles the app serves) and artifacts/ship/issue_vintages.json; cofire/v13/open_data.py",
    }
    (out / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    return index


if __name__ == "__main__":
    i = build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
    print(json.dumps({"issues": len(i["issues"]), "latest": i["latest"]["issue"],
                      "bytes": sum(f["bytes"] for f in i["files"].values())}))
