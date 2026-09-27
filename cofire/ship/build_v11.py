"""v1.1 Stage 3: configuration A stores for the Denver domains.

The frozen `features_a.build` runs unchanged on each registered domain. It
needs a processed cube for grid coordinates; the new domains have none, so a
coordinates-only template is written from the domain's own ERC cache, which is
on the same grid by construction. The template carries no `erc` variable, so
`weekly_erc` ignores it for data.

    python -m cofire.ship.build_v11 build <domain>
    python -m cofire.ship.build_v11 check
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

from cofire.model.data import erc_extension as ext  # noqa: E402
from cofire.ship import domains  # noqa: E402

REPORT = Path("artifacts/domains/stage3.json")
TRAIN_END = pd.Timestamp("2021-12-31")
VALID = (pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31"))


def settings(domain: str) -> Any:
    from cofire.model.config import get_settings

    domains.register()
    os.environ["COFIRE_SUBSET_NAME"] = domain
    os.environ["COFIRE_DEV_SUBSET"] = "1"
    get_settings.cache_clear()
    st = get_settings()
    # Larimer predates subset scoping and keeps the unscoped path (see config).
    scoped = domain in str(st.processed_dir) or (domain == "larimer" and st.processed_dir.name == "processed")
    assert st.subset_name == domain and scoped, st.processed_dir
    return st


def write_template(domain: str) -> Path:
    st = settings(domain)
    out: Path = st.processed_dir / "gridmet" / "weekly_template.nc"
    with xr.open_dataset(ext.cache_path(domain, 2020)) as ds:
        lat, lon = ds["lat"].values, ds["lon"].values
    fp = domains.load()[domain]
    assert (lat.size, lon.size) == (fp["n_lat"], fp["n_lon"]), "cache grid is not the footprint rectangle"
    out.parent.mkdir(parents=True, exist_ok=True)
    mask = domains.footprint_mask(domain, lat, lon).astype("int8")
    xr.Dataset({"footprint": (("lat", "lon"), mask)}, coords={"lat": lat, "lon": lon}).to_netcdf(out)
    return out


def build(domain: str) -> Path:
    from cofire.model.features_a import build as build_a

    st = settings(domain)
    write_template(domain)
    erc_files = sorted(ext.cache_path(domain, 0).parent.glob(f"{domain}_*.nc"))
    assert len(erc_files) == 22 and all(domain in p.name for p in erc_files), erc_files
    out = build_a(st)
    assert domain in str(out), out
    return out


def load(domain: str) -> pd.DataFrame:
    """The domain's config-A frame, footprint cells only, with a path check."""
    from cofire.model.features_a import load as load_a

    st = settings(domain)
    root = st.processed_dir / "features_a"
    assert domain in str(root) or domain == "larimer", f"{root} is not scoped to {domain}"
    f = load_a(st)
    f["time"] = pd.to_datetime(f["time"])
    if domain in domains.NEW:
        cells = {f"{la:.4f}_{lo:.4f}" for la, lo in domains.load()[domain]["cells"]}
        f = f[f["cell_id"].isin(cells)].reset_index(drop=True)
        assert f["cell_id"].nunique() == len(cells), "a footprint cell is missing from the store"
    return f


def check(domain: str) -> dict[str, Any]:
    from cofire.model.features_a import add_horizons
    from cofire.model.prob_metrics import MIN_POSITIVE_WEEKS, positive_weeks
    from cofire.model.targets import HORIZONS, all_event_targets, target_names

    f = load(domain)
    t = f["time"]
    out: dict[str, Any] = {"n_cells": int(f["cell_id"].nunique()), "n_weeks": int(t.nunique()),
                           "first_week": str(t.min().date()), "last_week": str(t.max().date())}

    # USDM category distribution by year, share of footprint cell-weeks.
    dist = (f.assign(year=t.dt.year).groupby("year")["usdm"]
            .value_counts(normalize=True).unstack(fill_value=0.0).reindex(columns=range(5), fill_value=0.0))
    out["usdm_by_year"] = {int(y): [round(float(v), 3) for v in row] for y, row in dist.iterrows()}

    # erc_pct uniformity over the training years: a percentile against its own
    # training pool should spread across 0 to 100, so the per-cell 5-95 width
    # sits near 90. Integer ERC ties pull it below 90.
    train = f[t <= TRAIN_END]
    q = train.groupby("cell_id")["erc_pct"].quantile([0.05, 0.95]).unstack()
    width = (q[0.95] - q[0.05]).to_numpy(float)
    out["erc_pct_width_5_95"] = {"median": round(float(np.median(width)), 2),
                                 "min": round(float(width.min()), 2), "max": round(float(width.max()), 2)}
    out["erc_pct_train_mean"] = round(float(train["erc_pct"].mean()), 2)

    g = all_event_targets(add_horizons(f, HORIZONS), HORIZONS)
    gt = g["time"]
    val = g[(gt >= VALID[0]) & (gt <= VALID[1])]
    tr = g[gt <= TRAIN_END]
    pos: dict[str, dict[str, int]] = {}
    for tg in target_names(HORIZONS):
        pos[tg] = {
            "train": int(positive_weeks(tr[tg].to_numpy(float), tr["time"].to_numpy()).size),
            "valid": int(positive_weeks(val[tg].to_numpy(float), val["time"].to_numpy()).size),
        }
    out["positive_weeks"] = pos
    out["not_estimable_in_validation"] = sorted(k for k, v in pos.items() if v["valid"] < MIN_POSITIVE_WEEKS)
    return out


def check_all() -> dict[str, Any]:
    from cofire.model.freeze import look_count

    assert look_count() == 3
    rep = {d: check(d) for d in domains.ORDER}
    for d, v in rep.items():
        w = v["erc_pct_width_5_95"]
        # Integer ERC ties keep the width a little under 90; Larimer and Pueblo sit at 88.6.
        assert 85.0 <= w["median"] <= 95.0 and w["min"] >= 80.0, f"{d}: erc_pct is not uniform in training, {w}"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1) + "\n")
    assert look_count() == 3
    return rep


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        print(build(sys.argv[2]))
    elif cmd == "check":
        r = check_all()
        for d, v in r.items():
            print(d, v["n_cells"], "cells", v["n_weeks"], "weeks", v["first_week"], v["last_week"],
                  "pct width", v["erc_pct_width_5_95"], "not estimable:", len(v["not_estimable_in_validation"]))
    else:
        raise SystemExit(__doc__)
