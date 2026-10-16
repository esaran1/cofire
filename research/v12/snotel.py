"""Stage 2: April 1 SNOTEL SWE for each domain's stations, 2007 to 2025.

Station rule (docs/PREREGISTRATION_V12.md): SNOTEL stations inside the
domain's footprint bounding box expanded by 0.25 degrees, with April 1 SWE
reported in at least 15 of the 19 years. Denver uses the union of the Upper
South Platte and Dillon stations. A domain whose box holds no qualifying
station uses the three nearest qualifying stations to its centre.

One AWDB request per year for every candidate station, through `safe_fetch`
(the host is already allowlisted for NRCS), priced first. The station lists
are written before any stage-2 model is fitted.

    python -m research.v12.snotel price
    python -m research.v12.snotel fetch
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from cofire.v12 import common

AWDB = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"
YEARS = tuple(range(2007, 2026))
MIN_YEARS = 15
BUFFER = 0.25
NEAREST = 3
NEAR_CANDIDATES = 10  # nearest candidates fetched for a domain with none in its box
BYTES_PER_STATION_YEAR = 330  # measured on a two-station probe: 619 B
OUT = common.OUT / "stage2"
APR1 = OUT / "snotel_apr1.csv"
STATIONS = common.OUT / "stage2_stations.json"


def _stations() -> pd.DataFrame:
    st = pd.read_parquet("data/cache/snotel_stations.parquet")
    return st[st["networkCode"] == "SNTL"].reset_index(drop=True)


def _box(domain: str) -> tuple[float, float, float, float]:
    from cofire.model import config
    from cofire.ship import domains

    domains.register()
    w, s, e, n = config.SUBSETS[domain][0]
    return float(w), float(s), float(e), float(n)


def candidates() -> dict[str, list[str]]:
    """Stations each domain may draw on, before the completeness rule."""
    from cofire.ship import domains

    st = _stations()
    out: dict[str, list[str]] = {}
    for d in domains.ORDER:
        if d == "denver":
            continue
        w, s, e, n = _box(d)
        m = ((st.longitude >= w - BUFFER) & (st.longitude <= e + BUFFER)
             & (st.latitude >= s - BUFFER) & (st.latitude <= n + BUFFER))
        if m.any():
            out[d] = sorted(st.loc[m, "stationTriplet"])
        else:
            cx, cy = (w + e) / 2, (s + n) / 2
            dist = np.hypot((st.longitude - cx) * np.cos(np.radians(cy)), st.latitude - cy)
            out[d] = list(st.loc[dist.sort_values().index[:NEAR_CANDIDATES], "stationTriplet"])
    return out


def price() -> dict[str, int]:
    uniq = sorted({s for v in candidates().values() for s in v})
    return {"stations": len(uniq), "requests": len(YEARS),
            "bytes": len(uniq) * len(YEARS) * BYTES_PER_STATION_YEAR}


def fetch() -> Path:
    from cofire.ship.safe_fetch import safe_fetch

    common.assert_looks()
    uniq = sorted({s for v in candidates().values() for s in v})
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for y in YEARS:
            url = (f"{AWDB}?stationTriplets={','.join(uniq)}&elements=WTEQ&duration=DAILY"
                   f"&beginDate={y}-04-01&endDate={y}-04-01")
            dest = Path(tmp) / f"apr1_{y}.json"
            safe_fetch(url, dest, "json", "SNOTEL-AWDB-April1", max_bytes=len(uniq) * 2000)
            for st in json.loads(dest.read_text()):
                vals = [v for d in st.get("data", []) for v in d.get("values", [])]
                v = next((x.get("value") for x in vals if str(x.get("date", ""))[:10] == f"{y}-04-01"), None)
                rows.append({"station": st["stationTriplet"], "year": y,
                             "swe_in": float(v) if v is not None else np.nan})
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).sort_values(["station", "year"])
    df.to_csv(APR1, index=False)
    select(df)
    return APR1


def select(apr1: pd.DataFrame) -> dict[str, Any]:
    """Apply the completeness rule and write the station lists."""
    from cofire.ship import domains

    ok_years = apr1.dropna(subset=["swe_in"]).groupby("station")["year"].nunique()
    qualifies = set(ok_years[ok_years >= MIN_YEARS].index)
    st = _stations().set_index("stationTriplet")
    out: dict[str, Any] = {"rule": f"in the footprint box + {BUFFER} deg, April 1 SWE in >= {MIN_YEARS} of {len(YEARS)} years; "
                                   f"else the {NEAREST} nearest qualifying; Denver = Upper South Platte + Dillon",
                           "domains": {}}
    cand = candidates()
    for d in domains.ORDER:
        if d == "denver":
            continue
        w, s, e, n = _box(d)
        inside = [x for x in cand[d] if x in qualifies
                  and w - BUFFER <= st.loc[x, "longitude"] <= e + BUFFER
                  and s - BUFFER <= st.loc[x, "latitude"] <= n + BUFFER]
        if inside:
            chosen, how = inside, "box"
        else:
            cx, cy = (w + e) / 2, (s + n) / 2
            q = st.loc[[x for x in cand[d] if x in qualifies]]
            dist = np.hypot((q.longitude - cx) * np.cos(np.radians(cy)), q.latitude - cy)
            chosen, how = list(dist.sort_values().index[:NEAREST]), "nearest"
        out["domains"][d] = {"how": how, "stations": sorted(chosen),
                             "names": [str(st.loc[x, "name"]) for x in sorted(chosen)]}
    den = sorted(set(out["domains"]["upper_south_platte"]["stations"]) | set(out["domains"]["dillon"]["stations"]))
    out["domains"]["denver"] = {"how": "union of upper_south_platte and dillon", "stations": den,
                                "names": [str(st.loc[x, "name"]) for x in den]}
    STATIONS.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    if sys.argv[1] == "price":
        print(price())
    elif sys.argv[1] == "fetch":
        print(fetch())
        print(STATIONS.read_text())
    else:
        raise SystemExit(__doc__)
