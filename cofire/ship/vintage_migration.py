"""One-time move from overwrite semantics to vintages (2026-09-27). Kept as the record.

1. Every ERC file already fetched becomes a seed vintage, dated by its file
   time in UTC.
2. Larimer and Pueblo's 2026 daily record as the stores were built from it
   (fetched 2026-09-20) is their first 2026 vintage.
3. The revised 2026 record fetched on 2026-09-27, which the old refresh gate
   refused, is adopted as their second vintage through the new gate: every
   revision inside the provisional window is logged with old and new value.
4. Every issue in the current export is pinned to the vintage it was built
   from, so adopting the revision leaves those issues unchanged.

    python -m cofire.ship.vintage_migration
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

from cofire.model.data import erc_extension as ext
from cofire.ship import domains, vintages

YEAR = 2026
STORE_RAW = {"larimer": Path("data/raw/gridmet/erc_2026.nc"), "pueblo": Path("data/raw/gridmet_pueblo/erc_2026.nc")}


def _mtime(p: Path) -> pd.Timestamp:
    return pd.Timestamp(os.path.getmtime(p), unit="s").floor("s")


def _daily(p: Path) -> xr.DataArray:
    with xr.open_dataset(p) as ds:
        name = next(v for v in ds.data_vars if "energy_release" in str(v) or str(v) == "erc")
        da = ds[name].load()
    t = next(d for d in da.dims if d in ("day", "time"))
    return da.rename({t: "day"}).rename(vintages.VAR)


def run() -> dict[str, Any]:
    if vintages.manifest():
        raise SystemExit("vintages already seeded; the migration runs once")
    out: dict[str, Any] = {"seeded": 0}
    cache = ext.cache_path("x", 0).parent
    for f in sorted(cache.glob("*_*.nc")):
        dom, year = f.stem.rsplit("_", 1)
        if dom not in domains.ORDER or int(year) == YEAR and dom in STORE_RAW:
            continue
        vintages.record(dom, int(year), _daily(f), _mtime(f), kind="seed")
        out["seeded"] += 1
    for dom, raw in STORE_RAW.items():
        v0 = vintages.record(dom, YEAR, _daily(raw), _mtime(raw), kind="seed: the copy the stores were built from")
        revised = cache / f"{dom}_{YEAR}.nc.ungated"
        v1 = vintages.record(dom, YEAR, _daily(revised), _mtime(revised), kind="fetch: adopted revision")
        vintages.materialize(dom, YEAR, ext.cache_path(dom, YEAR))
        revised.unlink()
        cache.joinpath(f"{dom}_{YEAR}.gated.json").unlink(missing_ok=True)
        out[dom] = {"v0": v0["id"], "v1": v1["id"], "revisions": v1["revisions"]}
    # Pin the issues already published to the vintage they were built from.
    export = pd.read_parquet("artifacts/ship/forecast_issues.parquet")
    pins: dict[str, dict[str, str]] = {}
    for dom in domains.ORDER:
        first = vintages.records(dom, YEAR)[0]["fetched_at"]
        issues = sorted(pd.to_datetime(export.loc[export["domain"] == dom, "time"]).unique())
        pins[dom] = {str(pd.Timestamp(t).date()): first for t in issues}
    vintages.pin_issues(pins)
    out["pinned"] = {d: len(m) for d, m in pins.items()}
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1, default=str))
