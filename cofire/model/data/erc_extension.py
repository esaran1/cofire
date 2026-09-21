"""gridMET ERC back-extension over OPeNDAP, with a reconciliation gate.

Replaces a hand-written DODS byte parser. That parser produced values whose
domain mean was 21.4 against the pipeline's 43.6 for the same year, domain and
variable, and the cause was never isolated: the bbox was hard-coded and wrong,
and the byte offset was assumed. Both faults share a root, which is reading a
binary wire format by hand when a library already does it.

Two rules this module enforces:

1. **The bbox comes from `Settings`, never from a literal.** The hard-coded
   40.25 to 41.00 range was 18 latitude rows against the real bbox's 16, so it
   silently covered different terrain.
2. **Nothing is ingested until it reconciles cell for cell** against an
   overlapping year already in the store. `reconcile` is the gate and
   `tests/test_erc_reconcile.py` proves it fails on an offset array.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402

from cofire.model.config import Settings, get_settings  # noqa: E402

LOGGER = logging.getLogger("cofire.data.erc_extension")

OPENDAP = "https://thredds.northwestknowledge.net/thredds/dodsC/MET/erc/erc_{year}.nc"
VAR = "energy_release_component-g"
CACHE = Path("data/cache/erc_ext")


@dataclass(frozen=True)
class ReconcileResult:
    ok: bool
    n_compared: int
    max_abs_diff: float
    first_mismatch: str = ""


def _open(year: int) -> xr.Dataset:
    """Open one year over OPeNDAP. netcdf4 first, pydap as fallback."""
    url = OPENDAP.format(year=year)
    try:
        return xr.open_dataset(url, engine="netcdf4", decode_times=True)
    except Exception as exc:  # noqa: BLE001
        LOGGER.info("netcdf4 engine failed for %s (%s); trying pydap", year, exc)
        return xr.open_dataset(url, engine="pydap", decode_times=True)


def fetch_year(year: int, settings: Settings | None = None) -> xr.DataArray:
    """One year of daily ERC over the domain's own bbox.

    The latitude axis descends, so the slice is ordered high to low. Getting
    that backwards returns an empty selection rather than an error, which is
    the kind of silent failure this module exists to prevent, so the result is
    checked for emptiness before it is returned.
    """
    settings = settings or get_settings()
    w, s, e, n = settings.bbox
    ds = _open(year)
    da = ds[VAR]
    lat_desc = bool(da.lat.values[0] > da.lat.values[-1])
    lat_slice = slice(n, s) if lat_desc else slice(s, n)
    out = da.sel(lat=lat_slice, lon=slice(w, e))
    if out.sizes.get("lat", 0) == 0 or out.sizes.get("lon", 0) == 0:
        raise ValueError(
            f"ERC {year}: empty selection for bbox {settings.bbox}; "
            f"lat descending={lat_desc}"
        )
    return out.load()


def cache_path(domain: str, year: int) -> Path:
    return CACHE / f"{domain}_{year}.nc"


def reconcile(
    fetched: xr.DataArray,
    reference: xr.DataArray,
    tol: float = 1e-6,
) -> ReconcileResult:
    """Cell-for-cell comparison against a year already in the store.

    The permanent gate. A newly fetched source-year is not ingested until it
    matches an overlapping year, because a wire-format or indexing error
    produces values that look physically plausible while being wrong.
    """
    a, b = xr.align(fetched, reference, join="inner")
    if a.size == 0:
        return ReconcileResult(False, 0, float("nan"), "no overlapping coordinates")
    av = np.asarray(a.values, dtype=float)
    bv = np.asarray(b.values, dtype=float)
    both = np.isfinite(av) & np.isfinite(bv)
    if not both.any():
        return ReconcileResult(False, 0, float("nan"), "no overlapping finite values")
    diff = np.abs(av - bv)
    diff[~both] = 0.0
    worst = float(diff.max())
    if worst <= tol:
        return ReconcileResult(True, int(both.sum()), worst)

    idx = np.unravel_index(int(np.argmax(diff)), diff.shape)
    coords = []
    for dim, i in zip(a.dims, idx, strict=True):
        try:
            coords.append(f"{dim}={a.coords[dim].values[i]}")
        except (KeyError, IndexError):
            coords.append(f"{dim}[{i}]")
    return ReconcileResult(
        False,
        int(both.sum()),
        worst,
        f"first mismatch at {', '.join(coords)}: fetched {av[idx]:.6g}, store {bv[idx]:.6g}",
    )


def reference_daily(year: int, settings: Settings | None = None) -> xr.DataArray | None:
    """The store's own daily ERC for a year, from THIS subset's raw cache.

    Subset-scoped deliberately. The raw caches live at `raw/gridmet` for the
    default subset and `raw/gridmet_<name>` for the others, and globbing across
    `raw/` returned Larimer's file when the active subset was Pueblo. The
    reconciliation gate then correctly refused to ingest, reporting no
    overlapping coordinates. This is the same unscoped-cache fault the project
    hit in v0.6 and again on the ESI start year, so the path is derived rather
    than searched.
    """
    settings = settings or get_settings()
    root = settings.raw_dir / "gridmet"
    scoped = settings.raw_dir / f"gridmet_{settings.subset_name}"
    if scoped.exists():
        root = scoped
    path = root / f"erc_{year}.nc"
    if not path.exists():
        return None
    ds = xr.open_dataset(path)
    for name in (VAR, "erc", "energy_release_component"):
        if name in ds.data_vars:
            return ds[name]
    return None
