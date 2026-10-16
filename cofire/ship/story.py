"""Build `app/lib/story.json`: the real data behind the landing page's pictures.

The landing page tells its story through pictures of the actual forecast rather
than decoration: a map of Colorado with every forecast cell coloured, and two
real Place Cards. This module extracts exactly what those need from artifacts
already on disk. It reads the frozen export and the census county boundaries,
and it fits, scores, and chooses nothing.

Everything the map caption says is computed here, so the sentence under the
picture cannot drift from the picture.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd

LOGGER = logging.getLogger("cofire.ship.story")

EXPORT = Path("artifacts/ship/forecast_issues.parquet")
BUNDLES = Path("demo/artifacts/ship/domains")
COUNTIES = Path("data/raw/boundaries/cb_2023_us_county_500k.zip")
# The data pack carries only Colorado's counties (cofire/ship/datapack.py).
CO_COUNTIES = Path("data/raw/boundaries/co_counties.geojson")
OUT = Path("app/lib/story.json")

COLORADO_FIPS = "08"
HORIZONS = (2, 4, 8)
# gridMET cells are 1/24 of a degree on a side.
CELL_DEG = 1.0 / 24.0
# Map projection: equirectangular, corrected for Colorado's mid latitude so a
# degree of longitude is not drawn as wide as a degree of latitude.
LAT0 = 39.0
KX = math.cos(math.radians(LAT0))
SCALE = 100.0

# One cell shown as a real Place Card. Larimer at 4 weeks carries both kinds of
# probability row, per-cell and county-wide, so the card shows the app deciding
# what it will and will not stand behind.
CARD_CELL = ("larimer", 40.733, -105.433, "4")


def _xy(lon: float, lat: float, lon0: float, lat1: float) -> tuple[float, float]:
    return ((lon - lon0) * KX * SCALE, (lat1 - lat) * SCALE)


def _path(geom: Any, lon0: float, lat1: float) -> str:
    """SVG path data for a (multi)polygon, rounded to keep the file small."""
    polys = getattr(geom, "geoms", [geom])
    parts: list[str] = []
    for poly in polys:
        ring = list(poly.exterior.coords)
        pts = [_xy(x, y, lon0, lat1) for x, y in ring]
        parts.append(
            "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"
        )
    return "".join(parts)


def _plain(text: str) -> str:
    """Replace en and em dashes, which app copy does not use, with words.

    The checklist source says "5\u201330 feet". It lives in the frozen model
    tree and cannot be edited, so the dash is normalised on the way out.
    """
    return text.replace("\u2013", " to ").replace("\u2014", ", ")


def quick_wins(n: int = 3) -> list[dict[str, Any]]:
    """The Harden page's own rule: the highest-weight free actions.

    Scored through `cofire.model.ember.score`, the same call the API makes, so
    the preview offers exactly what the real screen offers first.
    """
    from cofire.model.ember import score

    items = score({}, "wui")["items"]
    free = sorted(
        (i for i in items if i["cost"] == "free"), key=lambda i: -float(i["item_weight"])
    )
    return [{"id": str(i["id"]), "label": _plain(str(i["label"]))} for i in free[:n]]


def build() -> dict[str, Any]:
    """The landing page's data from the export and county boundaries: the latest issue's cells on a
    projected Colorado map with its outlines, crop and area labels, the caption figures per horizon,
    one real Place Card, and the quick wins.
    """
    import geopandas as gpd

    frame = pd.read_parquet(EXPORT)
    frame["time"] = pd.to_datetime(frame["time"])
    issue = frame["time"].max()
    latest = frame[frame["time"] == issue]

    counties = gpd.read_file(f"zip://{COUNTIES}") if COUNTIES.exists() else gpd.read_file(CO_COUNTIES)
    co = counties[counties["STATEFP"] == COLORADO_FIPS].copy()
    co["geometry"] = co.geometry.simplify(0.012, preserve_topology=True)
    minx, miny, maxx, maxy = co.total_bounds
    lon0, lat1 = float(minx), float(maxy)
    width = (float(maxx) - lon0) * KX * SCALE
    height = (lat1 - float(miny)) * SCALE

    outlines = [
        {"name": str(r["NAME"]), "d": _path(r.geometry, lon0, lat1)}
        for _, r in co.iterrows()
    ]

    cw = CELL_DEG * KX * SCALE
    ch = CELL_DEG * SCALE
    cells: list[dict[str, Any]] = []
    for _, r in latest.iterrows():
        x, y = _xy(float(r["lon"]) - CELL_DEG / 2, float(r["lat"]) + CELL_DEG / 2, lon0, lat1)
        cells.append(
            {
                "x": round(x, 2),
                "y": round(y, 2),
                "d": str(r["domain"]),
                "v": [round(float(r[f"erc_pct_h{h}_point"]), 1) for h in HORIZONS],
            }
        )

    # The caption, computed from the same values the map draws.
    by_h: dict[str, dict[str, float]] = {}
    for i, h in enumerate(HORIZONS):
        vals = pd.Series([c["v"][i] for c in cells])
        by_h[str(h)] = {
            "median": round(float(vals.median()), 1),
            "share_below_typical": round(float((vals < 50).mean()), 3),
            "spread": round(float(vals.quantile(0.9) - vals.quantile(0.1)), 1),
        }

    # Crop to where the forecasts are. The full state left the two forecast
    # areas as small patches in a mostly empty frame, with Pueblo off screen.
    xs = [c["x"] for c in cells]
    ys = [c["y"] for c in cells]
    margin = 0.3 * SCALE
    view = [
        round(min(xs) - margin, 1),
        round(min(ys) - margin, 1),
        round(max(xs) + cw - min(xs) + 2 * margin, 1),
        round(max(ys) + ch - min(ys) + 2 * margin, 1),
    ]

    # Each forecast area is outlined as what it is. Larimer and Pueblo are
    # rectangles of cells, so the rectangle is drawn; outlining the county
    # instead would claim coverage the grid does not have. The v1.1 domains are
    # footprints (Denver, and two watersheds cut at their reservoirs), where a
    # rectangle would claim cells outside the area, so only their label is
    # drawn and the coloured cells show the shape.
    from cofire.ship import domains

    areas = []
    for dom in [d for d in domains.ORDER if d in {c["d"] for c in cells}]:
        dx = [c["x"] for c in cells if c["d"] == dom]
        dy = [c["y"] for c in cells if c["d"] == dom]
        areas.append(
            {
                "name": domains.LABELS[dom],
                "x": round(min(dx), 1),
                "y": round(min(dy), 1),
                "w": round(max(dx) + cw - min(dx), 1),
                "h": round(max(dy) + ch - min(dy), 1),
                "outline": dom not in domains.NEW,
            }
        )

    # A small locator: the state outline and where the crop sits in it.
    state_geom = co.union_all().simplify(0.03, preserve_topology=True)

    from cofire.ship.bundles import legacy_cells

    index = legacy_cells(BUNDLES)
    dom, lat, lon, horizon = CARD_CELL
    pool = [
        c for c in index["cells"]
        if c.get("domain") == dom and c.get("issue") == issue.strftime("%Y-%m-%d")
    ]
    if not pool:
        raise SystemExit(f"no {dom} cells for {issue.date()} in {BUNDLES}")
    cell = min(pool, key=lambda c: (c["lat"] - lat) ** 2 + (c["lon"] - lon) ** 2)
    states = [
        t["state"] for name, t in cell["targets"].items() if name.endswith(f"_h{horizon}")
    ]
    if "base_rate" not in states or "probability" not in states:
        raise SystemExit(
            f"{dom} h{horizon} no longer carries both per-cell and county-wide rows; "
            "the story card would not show what the chapter says it shows"
        )
    card = {
        "place": cell,
        "horizon": horizon,
        "band_state": cell["horizons"][horizon]["state"],
        "n_probability": states.count("probability"),
        "n_base_rate": states.count("base_rate"),
    }

    return {
        "note": "Generated by cofire.ship.story from artifacts. Do not hand-edit.",
        "issue": issue.strftime("%Y-%m-%d"),
        "horizons": list(HORIZONS),
        "map": {
            "width": round(width, 1),
            "height": round(height, 1),
            "cell": [round(cw, 2), round(ch, 2)],
            "outlines": outlines,
            "view": view,
            "areas": areas,
            "state": _path(state_geom, lon0, lat1),
            "cells": cells,
            "by_horizon": by_h,
        },
        "card": card,
        "quick_wins": quick_wins(),
    }


def write(out: Path = OUT) -> Path:
    """Build the story data, write it as compact JSON to `out`, and return the path."""
    story = build()
    out.write_text(json.dumps(story, separators=(",", ":")))
    LOGGER.info(
        "story.json: %d cells, %d outlines, card %s, %.0f KB",
        len(story["map"]["cells"]), len(story["map"]["outlines"]),
        story["card"]["band_state"], out.stat().st_size / 1e3,
    )
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write())
