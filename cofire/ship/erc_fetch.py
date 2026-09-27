"""gridMET ERC for the v1.1 domains, over the reconciled OPeNDAP path.

The frozen `erc_extension.fetch_year` opens the THREDDS OPeNDAP URL with
`xarray.open_dataset` and selects the domain bbox with `.sel`; that path
reconciled cell for cell against both existing stores. It is used here
unchanged. The server's NCSS subset service would have produced a file that
`safe_fetch` could handle, but it returns "-101: NetCDF: HDF error" for every
request, and the whole-file fileServer route costs tens of MB per year.

An OPeNDAP read is a stream the NetCDF library makes, not a file download, so
`safe_fetch` cannot wrap it directly. This module applies each rule that has a
meaning for a stream:

1. HTTPS and the host allowlist, checked on the URL; a HEAD on the `.dds`
   endpoint that answers with a redirect off the allowlist aborts before the
   library connects.
2. HEAD first, then the `.dds` itself through `safe_fetch`; the exact wire size
   is computed from its shape (DAP2 sends each 16-bit value as a 4-byte XDR
   word) and checked against the session cap and the ledger before any data
   moves.
3. The library refuses an HTML error page, and the returned array must have the
   domain's exact shape and physical ERC values, or nothing is cached.
4. Each cached year is checked against its peers' sizes.
5. No archive is involved.
6. No new packages.
7. Every read is logged with URL, computed bytes, the sha256 of the cached
   file, and a timestamp.
"""

from __future__ import annotations

import hashlib
import logging
import re
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

from cofire.model.config import Settings
from cofire.model.data import erc_extension as ext
from cofire.model.data.ledger import DownloadLedger
from cofire.ship import domains
from cofire.ship.safe_fetch import (
    SESSION,
    SESSION_CAP_BYTES,
    FetchRefused,
    check_magic,
    check_peer_size,
    check_url,
    safe_fetch,
    session_bytes,
)

LOGGER = logging.getLogger("cofire.ship.erc_fetch")

DDS_DIR = Path("data/raw/erc_v11/dds")
YEARS = range(2004, 2026)
# Metadata and coordinate variables the library reads on open: the DAS and DDS
# (about 4.2 kB) and the three Float64 coordinate arrays.
_OPEN_OVERHEAD = 4_300


def settings_for(domain: str) -> Settings:
    domains.register()
    return Settings(subset_name=domain, dev_subset=True)


def _dds(year: int, ledger: DownloadLedger) -> str:
    """The year's DDS, fetched once through `safe_fetch`."""
    path = DDS_DIR / f"erc_{year}.dds"
    if not path.exists():
        safe_fetch(ext.OPENDAP.format(year=year) + ".dds", path, "dap", "gridMET-DAP-meta",
                   max_bytes=100_000, ledger=ledger)
    return path.read_text()


def _dims(dds: str) -> dict[str, int]:
    m = re.search(r"UInt16 energy_release_component-g\[day = (\d+)\]\[lat = (\d+)\]\[lon = (\d+)\]", dds)
    if m is None:
        raise FetchRefused("DDS does not describe a UInt16 day x lat x lon ERC grid")
    return {"day": int(m.group(1)), "lat": int(m.group(2)), "lon": int(m.group(3))}


def projected_bytes(dims: dict[str, int], n_lat: int, n_lon: int) -> int:
    """Exact DAP2 wire size of one domain-year read."""
    data = dims["day"] * n_lat * n_lon * 4
    maps = (dims["day"] + n_lat + n_lon) * 8
    coords = (dims["day"] + dims["lat"] + dims["lon"]) * 8
    return data + maps + coords + _OPEN_OVERHEAD


def _check_redirect(url: str) -> None:
    check_url(url)
    head = requests.head(url + ".dds", allow_redirects=False, timeout=60)
    if head.status_code in (301, 302, 303, 307, 308):
        check_url(urllib.parse.urljoin(url, head.headers.get("Location", "")))
        raise FetchRefused(f"{url} redirects; the NetCDF library would follow it unchecked")
    if head.status_code >= 400:
        raise FetchRefused(f"HEAD {url}.dds returned {head.status_code}")
    ctype = (head.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if not ctype.startswith("text/plain"):
        raise FetchRefused(f"DDS Content-Type {ctype!r} is not text/plain")


def validate(da: xr.DataArray, n_lat: int, n_lon: int, n_day: int) -> None:
    """The array must be this domain's rectangle and physical ERC values."""
    shape = (da.sizes.get("day", da.sizes.get("time", 0)), da.sizes.get("lat", 0), da.sizes.get("lon", 0))
    if shape != (n_day, n_lat, n_lon):
        raise FetchRefused(f"shape {shape} is not the expected {(n_day, n_lat, n_lon)}")
    v = np.asarray(da.values, dtype=float)
    finite = np.isfinite(v)
    if finite.mean() < 0.95:
        raise FetchRefused(f"only {finite.mean():.1%} of cell-days are finite")
    lo, hi = float(np.nanmin(v)), float(np.nanmax(v))
    if lo < 0 or hi > 200:
        raise FetchRefused(f"ERC range {lo}..{hi} is not physical")
    if float(np.nanstd(v)) == 0.0:
        raise FetchRefused("ERC is constant across every cell-day")


def fetch(domain: str, year: int, ledger: DownloadLedger, peers: list[int] | None = None) -> Path:
    """One domain-year of daily ERC into the frozen extension cache."""
    dest = ext.cache_path(domain, year)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    fp = domains.load()[domain]
    url = ext.OPENDAP.format(year=year)
    _check_redirect(url)
    dims = _dims(_dds(year, ledger))
    n = projected_bytes(dims, fp["n_lat"], fp["n_lon"])
    if session_bytes(ledger) + n > SESSION_CAP_BYTES:
        raise FetchRefused(f"would exceed the {SESSION} session cap")
    if not ledger.can_afford(n):
        raise FetchRefused(f"would exceed the ledger ceiling: {n} B, {ledger.remaining_bytes} B left")

    constraint = f"{url}?energy_release_component-g bbox={fp['bbox']}"
    try:
        da = ext.fetch_year(year, settings_for(domain))
        validate(da, fp["n_lat"], fp["n_lon"], dims["day"])
    except FetchRefused:
        ledger.record("gridMET-OPeNDAP", constraint, n, note=f"session={SESSION}; REJECTED")
        raise
    except Exception as exc:  # noqa: BLE001  (an error page surfaces as a library error)
        ledger.record("gridMET-OPeNDAP", constraint, n, note=f"session={SESSION}; REJECTED")
        raise FetchRefused(f"OPeNDAP read failed for {domain} {year}: {exc}") from exc

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    da.to_dataset(name=ext.VAR).to_netcdf(tmp)
    with open(tmp, "rb") as fh:
        check_magic(fh.read(64), "netcdf")
    size = tmp.stat().st_size
    try:
        check_peer_size(size, peers or [])
    except FetchRefused:
        tmp.unlink()
        ledger.record("gridMET-OPeNDAP", constraint, n, note=f"session={SESSION}; REJECTED")
        raise
    tmp.replace(dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    ledger.record("gridMET-OPeNDAP", constraint, n,
                  note=f"session={SESSION}; sha256={sha}; bytes computed from the DAP2 wire format")
    return dest


def price(ledger: DownloadLedger, years: range = YEARS, extra_years: tuple[int, ...] = ()) -> dict[str, int]:
    """Projected bytes per domain across the years, from one DDS per year."""
    out: dict[str, int] = {}
    fps = domains.load()
    for d in domains.NEW:
        out[d] = 0
        for y in (*years, *extra_years):
            out[d] += projected_bytes(_dims(_dds(y, ledger)), fps[d]["n_lat"], fps[d]["n_lon"])
    return out


def run(years: range = YEARS) -> dict[str, list[int]]:
    ledger = DownloadLedger(Path("data/ledger.json"))
    sizes: dict[str, list[int]] = {}
    for d in domains.NEW:
        sizes[d] = []
        for y in years:
            p = fetch(d, y, ledger, peers=sizes[d][-5:])
            sizes[d].append(p.stat().st_size)
            LOGGER.info("%s %d: %d B cached", d, y, sizes[d][-1])
    return sizes


ASCII_URL = "https://thredds.northwestknowledge.net/thredds/dodsC/MET/erc/erc_{year}.nc.ascii"
GATE_PATH = Path("artifacts/domains/erc_gate.json")
_FILL = 32767


def _parse_ascii(text: str) -> tuple[list[float], list[float], float, float]:
    """Values, days, lat and lon from a one-cell DAP ASCII response."""
    body = text.split("-" * 45, 1)[1]
    blocks = [b.strip().splitlines() for b in body.strip().split("\n\n")]
    vals = [float(line.split(",")[1]) for line in blocks[0][1:]]
    days = [float(x) for x in blocks[1][1].split(",")]
    return vals, days, float(blocks[2][1]), float(blocks[3][1])


def verify_against_source(
    domain: str, ledger: DownloadLedger, n_years: int = 3, n_cells: int = 4, n_days: int = 7, seed: int = 2026
) -> dict[str, object]:
    """Compare cached cell-days with the server's raw ASCII for a random sample.

    A different wire format read by different code: DAP ASCII parsed as text,
    against DAP2 binary decoded by the NetCDF library. The coordinate maps come
    back with the values, so the check also proves each index is the cell the
    cache says it is.
    """
    rng = np.random.default_rng(seed)
    fp = domains.load()[domain]
    years = sorted(int(y) for y in rng.choice(list(YEARS), n_years, replace=False))
    cells = [fp["cells"][int(k)] for k in rng.choice(len(fp["cells"]), n_cells, replace=False)]
    n_cmp, worst, first = 0, 0.0, ""
    for y in years:
        cached = xr.open_dataset(ext.cache_path(domain, y))[ext.VAR].load()
        t = cached.dims[0]
        for la, lo in cells:
            d0 = int(rng.integers(0, cached.sizes[t] - n_days))
            i = round((domains.GRID_LAT0 - la) * 24)
            j = round((lo - domains.GRID_LON0) * 24)
            url = f"{ASCII_URL.format(year=y)}?energy_release_component-g[{d0}:1:{d0 + n_days - 1}][{i}:1:{i}][{j}:1:{j}]"
            out = Path("data/raw/erc_v11/gate") / f"{domain}_{y}_{i}_{j}_{d0}.txt"
            if not out.exists():
                safe_fetch(url, out, "dap", "gridMET-DAP-ascii", max_bytes=100_000, ledger=ledger)
            vals, days, alat, alon = _parse_ascii(out.read_text())
            if abs(alat - la) > 1e-4 or abs(alon - lo) > 1e-4:
                return {"ok": False, "first_mismatch": f"{y} index ({i},{j}) is ({alat},{alon}), cache cell ({la},{lo})"}
            sel = cached.sel(lat=la, lon=lo, method="nearest").isel({t: slice(d0, d0 + n_days)})
            want_days = (np.asarray(sel[t].values, dtype="datetime64[D]") - np.datetime64("1900-01-01", "D")).astype(int)
            if list(want_days) != [int(d) for d in days]:
                return {"ok": False, "first_mismatch": f"{y} days {days} against cache {list(want_days)}"}
            src = np.array([np.nan if v == _FILL else v for v in vals])
            got = np.asarray(sel.values, dtype=float)
            both = np.isfinite(src) & np.isfinite(got)
            if (np.isfinite(src) != np.isfinite(got)).any():
                return {"ok": False, "first_mismatch": f"{y} ({la},{lo}) missing-value pattern differs"}
            diff = np.abs(src[both] - got[both])
            n_cmp += int(both.sum())
            if diff.size and float(diff.max()) > worst:
                worst = float(diff.max())
                k = int(np.argmax(np.abs(np.where(both, src - got, 0))))
                first = f"{y} ({la},{lo}) day {d0 + k}: source {src[k]}, cache {got[k]}"
    return {"ok": worst == 0.0, "n_compared": n_cmp, "max_abs_diff": worst, "years": years,
            "cells": cells, "first_mismatch": first}


# ------------------------------------------------------------ weekly refresh

OVERLAP_DAYS = 14  # re-read the last two cached weeks; revisions there become a new vintage
GATE_MARGIN_DAYS = 7  # one day this far beyond the provisional window must re-read exactly


def rect(domain: str) -> tuple[int, int]:
    """Rows and columns the frozen bbox selection gives for a domain."""
    from cofire.model import config

    domains.register()
    w, s, e, n = config.SUBSETS[domain][0]
    lats = domains.GRID_LAT0 - np.arange(585) / 24.0
    lons = domains.GRID_LON0 + np.arange(1386) / 24.0
    return int(((lats >= s) & (lats <= n)).sum()), int(((lons >= w) & (lons <= e)).sum())


def _read_days(domain: str, year: int, start: int, stop: int) -> xr.DataArray:
    """Days [start, stop) of one year over the domain's bbox, the reconciled way.

    The same `open_dataset` and `.sel` as the frozen `fetch_year`, with the
    day axis sliced first so only the new days cross the wire.
    """
    w, s, e, n = settings_for(domain).bbox
    da = ext._open(year)[ext.VAR].isel(day=slice(start, stop))
    lat_desc = bool(da.lat.values[0] > da.lat.values[-1])
    out = da.sel(lat=slice(n, s) if lat_desc else slice(s, n), lon=slice(w, e)).load()
    if out.sizes.get("lat", 0) == 0 or out.sizes.get("lon", 0) == 0:
        raise FetchRefused(f"ERC {year}: empty selection for {domain}")
    return out


def extend(domain: str, year: int, ledger: DownloadLedger, now: pd.Timestamp | None = None) -> dict[str, object]:
    """Fetch the new days of one domain-year as a new vintage.

    Re-reads the last OVERLAP_DAYS already held, plus one day just beyond the
    provisional window. The vintage gate (`cofire.ship.vintages`) accepts and
    logs revisions inside the window and refuses the fetch if the older day, or
    anything else outside the window, changed.
    """
    from cofire.ship import vintages
    from cofire.ship.export import utc_now

    now = utc_now() if now is None else now
    n_lat, n_lon = rect(domain)
    url = ext.OPENDAP.format(year=year)
    _check_redirect(url)
    (DDS_DIR / f"erc_{year}.dds").unlink(missing_ok=True)
    n_server = _dims(_dds(year, ledger))["day"]
    have = vintages.assemble(domain, year) if vintages.records(domain, year) else None
    n_have = 0 if have is None else int(have.sizes["day"])
    if have is not None and n_have >= n_server:
        return {"domain": domain, "year": year, "new_days": 0, "last_day": str(have.day.values[-1])[:10]}
    start = max(0, n_have - OVERLAP_DAYS)
    n_days = n_server - start
    gate_day = n_server - 1 - vintages.WINDOW_DAYS - GATE_MARGIN_DAYS
    cost = n_days * n_lat * n_lon * 4 + (n_days + n_lat + n_lon) * 8 + _OPEN_OVERHEAD
    if have is not None and 0 <= gate_day < n_have:
        cost += n_lat * n_lon * 4 + _OPEN_OVERHEAD
    if session_bytes(ledger) + cost > SESSION_CAP_BYTES or not ledger.can_afford(cost):
        raise FetchRefused(f"{domain} {year}: {cost} B would exceed the session cap or the ledger")
    constraint = f"{url}?energy_release_component-g day[{start}:{n_server}] bbox={settings_for(domain).bbox}"
    try:
        new = _read_days(domain, year, start, n_server)
        validate(new, n_lat, n_lon, n_days)
        if have is not None and 0 <= gate_day < n_have:
            g = _read_days(domain, year, gate_day, gate_day + 1)
            r = ext.reconcile(g, have.isel(day=slice(gate_day, gate_day + 1)))
            if not r.ok:
                raise FetchRefused(f"{domain} {year} day {gate_day}, beyond the provisional window: {r.first_mismatch}")
        rec = vintages.record(domain, year, new, fetched_at=now)
    except FetchRefused:
        ledger.record("gridMET-OPeNDAP", constraint, cost, note=f"session={SESSION}; REJECTED")
        raise
    except Exception as exc:  # noqa: BLE001
        ledger.record("gridMET-OPeNDAP", constraint, cost, note=f"session={SESSION}; REJECTED")
        raise FetchRefused(f"OPeNDAP read failed for {domain} {year}: {exc}") from exc
    ledger.record("gridMET-OPeNDAP", constraint, cost,
                  note=f"session={SESSION}; sha256={rec['sha256']}; vintage={rec['id']}; bytes computed from the DAP2 wire format")
    dest = vintages.materialize(domain, year, ext.cache_path(domain, year))
    return {"domain": domain, "year": year, "new_days": int(n_server - n_have), "last_day": rec["last_day"],
            "vintage": rec["id"], "revised_cell_days": rec["revisions"]["n_cell_days"], "bytes": cost,
            "materialized": str(dest)}
