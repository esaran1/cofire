"""Data vintages: every fetch kept, never overwritten, every issue pinned to one.

gridMET revises its provisional data, and the reach is not a fixed lag. On
2026-09-27 a re-read changed days back to 2026-02-28, 202 days before the older
copy's last day (`artifacts/audit/gridmet_revision_window.json`), so the window
was first set to 240 days. On 2026-10-09 the refresh's gate day failed: the
revisions then reached 2026-01-31 in every domain, about 250 days back, up to
21 ERC units (`artifacts/audit/gridmet_revision_reach.json`). The front moved
48 days in three weeks. The fourth quarter of 2025 still re-read exactly. So a
full year is provisional: WINDOW_DAYS = 365, and the gate day (window plus a
margin) falls in the previous year's file, which must re-read exactly.

The rules:

* Each fetch is stored as its own file, keyed by source, domain, year, the
  days it covers and the UTC time it was fetched, and is never overwritten.
* A daily series "as of" a time is every fetch up to that time, applied in
  order, a later fetch replacing the days it re-read.
* A new fetch may revise days inside the window; each revised cell-day is
  logged with its old and new value. A revision to a day older than the window
  fails the gate and the fetch is refused.
* Each forecast issue is pinned to the as-of time it was first produced from
  (`artifacts/ship/issue_vintages.json`). A rebuild reproduces an old issue from
  its own vintage; only new issues use the latest.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from cofire.ship.safe_fetch import FetchRefused

SOURCE = "gridmet_erc"
VAR = "energy_release_component-g"
WINDOW_DAYS = 365
ROOT = Path("data/vintages")
MANIFEST = Path("artifacts/vintages/manifest.json")
REVISIONS = Path("artifacts/vintages/revisions")
ISSUES = Path("artifacts/ship/issue_vintages.json")


def _stamp(t: pd.Timestamp) -> str:
    return str(pd.Timestamp(t).strftime("%Y%m%dT%H%M%SZ"))


def manifest() -> list[dict[str, Any]]:
    """Every vintage record in the manifest, or an empty list if there is none."""
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []


def _save(records: list[dict[str, Any]]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(records, indent=1) + "\n")


def records(domain: str, year: int, as_of: pd.Timestamp | None = None) -> list[dict[str, Any]]:
    """The ERC vintage records for one domain-year, only those fetched by `as_of` when it is given,
    oldest first.
    """
    out = [r for r in manifest() if r["source"] == SOURCE and r["domain"] == domain and r["year"] == year]
    if as_of is not None:
        out = [r for r in out if pd.Timestamp(r["fetched_at"]) <= pd.Timestamp(as_of)]
    return sorted(out, key=lambda r: r["fetched_at"])


def latest(domain: str, year: int) -> pd.Timestamp:
    """When the newest vintage of a domain-year was fetched; raises FetchRefused if there is none.
    """
    recs = records(domain, year)
    if not recs:
        raise FetchRefused(f"no vintage for {domain} {year}")
    return pd.Timestamp(recs[-1]["fetched_at"])


def _open(path: str) -> xr.DataArray:
    with xr.open_dataset(path) as ds:
        da = ds[VAR].load()
    return da.rename({"time": "day"}) if "time" in da.dims else da


def assemble(domain: str, year: int, as_of: pd.Timestamp | None = None) -> xr.DataArray:
    """The daily series as it stood at `as_of`: fetches applied in order."""
    recs = records(domain, year, as_of)
    if not recs:
        raise FetchRefused(f"no vintage for {domain} {year} as of {as_of}")
    out = _open(recs[0]["file"])
    for r in recs[1:]:
        new = _open(r["file"])
        keep = out.sel(day=~out["day"].isin(new["day"].values))
        out = xr.concat([keep, new], dim="day").sortby("day")
    return out


def gate_revisions(
    old: xr.DataArray, new: xr.DataArray, window_days: int = WINDOW_DAYS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Revised cell-days inside the window (accepted) and outside it (refused).

    The window is counted back from the newest day in `new`.
    """
    a, b = xr.align(old, new, join="inner")
    cols = ["date", "lat", "lon", "old", "new"]
    if a.size == 0:
        return pd.DataFrame(columns=cols), pd.DataFrame(columns=cols)
    av, bv = np.asarray(a.values, float), np.asarray(b.values, float)
    changed = ~((av == bv) | (np.isnan(av) & np.isnan(bv)))
    idx = np.argwhere(changed)
    days = pd.DatetimeIndex(a["day"].values)
    lat, lon = a["lat"].values, a["lon"].values
    frame = pd.DataFrame({
        "date": days[idx[:, 0]], "lat": lat[idx[:, 1]], "lon": lon[idx[:, 2]],
        "old": av[changed], "new": bv[changed],
    })
    cutoff = pd.Timestamp(new["day"].values[-1]) - pd.Timedelta(days=window_days)
    inside = frame["date"] >= cutoff
    return frame[inside].reset_index(drop=True), frame[~inside].reset_index(drop=True)


def record(
    domain: str, year: int, da: xr.DataArray, fetched_at: pd.Timestamp, kind: str = "fetch",
    window_days: int = WINDOW_DAYS, root: Path = ROOT,
) -> dict[str, Any]:
    """Store one fetch as a new vintage, after the revision gate."""
    da = da.rename({"time": "day"}) if "time" in da.dims else da
    prior = records(domain, year)
    accepted = pd.DataFrame()
    if prior:
        accepted, refused = gate_revisions(assemble(domain, year), da, window_days)
        if len(refused):
            r0 = refused.iloc[0]
            raise FetchRefused(
                f"{domain} {year}: {len(refused)} revised cell-day(s) older than the {window_days}-day "
                f"window, first {r0['date'].date()} ({r0['lat']:.4f}, {r0['lon']:.4f}): "
                f"old {r0['old']}, new {r0['new']}"
            )
    days = pd.DatetimeIndex(da["day"].values)
    stamp = _stamp(fetched_at)
    path = root / SOURCE / f"{domain}_{year}" / f"{stamp}_{days[0].date()}_{days[-1].date()}.nc"
    if path.exists():
        raise FetchRefused(f"vintage {path} exists; vintages are never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    da.to_dataset(name=VAR).to_netcdf(tmp)
    tmp.replace(path)
    rec: dict[str, Any] = {
        "id": f"{SOURCE}/{domain}/{year}/{stamp}", "source": SOURCE, "domain": domain, "year": year,
        "first_day": str(days[0].date()), "last_day": str(days[-1].date()),
        "fetched_at": pd.Timestamp(fetched_at).isoformat(), "kind": kind, "file": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "revisions": {"n_cell_days": int(len(accepted)), "window_days": window_days},
    }
    if len(accepted):
        REVISIONS.mkdir(parents=True, exist_ok=True)
        log = REVISIONS / f"{domain}_{year}_{stamp}.csv.gz"
        with gzip.open(log, "wt") as fh:
            accepted.assign(date=accepted["date"].dt.date).to_csv(fh, index=False)
        rec["revisions"] |= {
            "log": str(log), "first_date": str(accepted["date"].min().date()),
            "last_date": str(accepted["date"].max().date()),
            "max_abs": float(np.abs(accepted["new"] - accepted["old"]).max()),
        }
    _save([*manifest(), rec])
    return rec


def materialize(domain: str, year: int, dest: Path, as_of: pd.Timestamp | None = None) -> Path:
    """Write the series as of `as_of` (latest if None) where the frozen builder reads it."""
    da = assemble(domain, year, as_of)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    da.to_dataset(name=VAR).to_netcdf(tmp)
    tmp.replace(dest)
    return dest


def issue_vintages() -> dict[str, dict[str, str]]:
    """The saved issue pins, per domain from issue to as-of time; empty if there are none."""
    data: dict[str, dict[str, str]] = json.loads(ISSUES.read_text()) if ISSUES.exists() else {}
    return data


def pin_issues(pins: dict[str, dict[str, str]]) -> None:
    """Add new issue pins. An existing pin is never changed."""
    cur = issue_vintages()
    for dom, m in pins.items():
        have = cur.setdefault(dom, {})
        for issue, as_of in m.items():
            if issue in have and have[issue] != as_of:
                raise AssertionError(f"{dom} {issue} is pinned to {have[issue]}; refusing to repin to {as_of}")
            have.setdefault(issue, as_of)
    ISSUES.parent.mkdir(parents=True, exist_ok=True)
    ISSUES.write_text(json.dumps({d: dict(sorted(m.items())) for d, m in sorted(cur.items())}, indent=1) + "\n")


if __name__ == "__main__":
    for r in manifest():
        print(r["id"], r["first_day"], r["last_day"], r["kind"], r["revisions"])
    sys.exit(0)
