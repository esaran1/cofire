"""Colorado EnviroScreen 2.0 for Denver's census tracts: context, not a forecast.

CDPHE publishes EnviroScreen by tract (published 2024-11-14). The map shows it
as a context layer under Denver's forecast, so a reader can see which
neighborhoods carry the most environmental and health burden where drought,
heat and smoke land. Nothing here enters a model or a forecast number.

One fetch through `safe_fetch` (logged in the ledger): Denver's 178 tracts,
the overall score and five indicators, outlines simplified to about 30 m.

    python -m cofire.ship.enviroscreen
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from cofire.ship.safe_fetch import FetchRefused, safe_fetch

LAYER = "https://services3.arcgis.com/66aUo8zsujfVXRIT/arcgis/rest/services/ColoradoEnviroScreen_v2_Tract_24118_Final/FeatureServer/0"
PAGE = "https://cdphe.colorado.gov/enviroscreen"
OUT = Path("app/lib/enviroscreen_denver.json")
DENVER_FIPS = "08031"
N_TRACTS = 178  # Denver County tracts in the layer, counted 2026-10-04

# Source field -> short name. All are statewide percentiles, 0 to 100.
# Not taken: Drought (Drg_P) is county-level, the same 35.4 in every Denver
# tract, so it says nothing about neighborhoods; Wildfire Risk (Wl__P) reads
# high across urban Denver and would suggest a wildland fire danger the app
# does not claim for the city.
FIELDS = {
    "ES_S_": "score",  # EnviroScreen Percentile Score
    "E___P": "heat",  # Extreme Heat Days (percentile)
    "F___P": "pm25",  # Fine Particle Pollution (percentile)
    "As___P": "asthma",  # Asthma Hospitalization Rate (percentile)
}


def query_url() -> str:
    params = {
        "where": f"GEOID LIKE '{DENVER_FIPS}%'",
        "outFields": ",".join(["GEOID", "Ttl_P", *FIELDS]),
        "outSR": "4326",
        "geometryPrecision": "4",
        "maxAllowableOffset": "0.0003",
        "returnGeometry": "true",
        "f": "geojson",
    }
    return f"{LAYER}/query?{urlencode(params)}"


def tidy(raw: dict[str, Any], fetched: str, sha256: str) -> dict[str, Any]:
    """The app's file: short names, checked values, and where they came from."""
    if "error" in raw or raw.get("type") != "FeatureCollection":
        raise FetchRefused(f"not a feature collection: {str(raw)[:200]}")
    feats = []
    for f in raw["features"]:
        p = f["properties"]
        geoid = str(p["GEOID"])
        if not geoid.startswith(DENVER_FIPS):
            raise FetchRefused(f"tract {geoid} is outside Denver")
        props: dict[str, Any] = {"geoid": geoid, "pop": p.get("Ttl_P")}
        for src, name in FIELDS.items():
            v = p.get(src)
            if v is not None and not 0 <= float(v) <= 100:
                raise FetchRefused(f"{geoid} {src}={v} is not a percentile")
            props[name] = None if v is None else round(float(v), 1)
        feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
    if len(feats) != N_TRACTS:
        raise FetchRefused(f"{len(feats)} tracts, expected {N_TRACTS}")
    feats.sort(key=lambda f: f["properties"]["geoid"])
    return {
        "type": "FeatureCollection",
        "meta": {
            "source": "Colorado EnviroScreen 2.0, Colorado Department of Public Health and Environment",
            "published": "2024-11-14",
            "page": PAGE,
            "layer": LAYER,
            "fetched": fetched,
            "sha256": sha256,
            "fields": FIELDS,
        },
        "features": feats,
    }


def run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "enviroscreen.geojson"
        res = safe_fetch(query_url(), dest, "json", "EnviroScreen-v2-Denver", max_bytes=3_000_000)
        raw = json.loads(dest.read_text())
    out = tidy(raw, datetime.now(UTC).isoformat(timespec="seconds"), res.sha256)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    return {"tracts": len(out["features"]), "bytes": res.n_bytes, "file_bytes": OUT.stat().st_size}


if __name__ == "__main__":
    print(run())
