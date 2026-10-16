"""A compact data pack, so the weekly refresh can run on a fresh CI runner.

The frozen issue-frame builder re-rasterizes USDM from the yearly national
archives, 2007 to now, on every run: 1.2 GB that a scheduled job cannot fetch
each week under the download ledger. The pack carries what the refresh reads,
cut to what it needs:

* USDM archives clipped to Colorado (the frozen config's buffered state box).
  Same yearly and weekly zip layout, same DM column, so the frozen rasterizer
  reads them unchanged. `gate` proves the rasterized cubes are identical to the
  national archives' for every domain and week before a clipped archive is used.
* The daily ERC extension caches and every ERC vintage (cofire/ship/vintages.py).
* Larimer and Pueblo's processed weekly cubes, ERC only (the builder reads
  `erc` and the grid), and their raw 2026 daily ERC (the gate's reference).

    python -m cofire.ship.datapack clip <year>      # one year, resumable
    python -m cofire.ship.datapack gate
    python -m cofire.ship.datapack pack <out.tar.gz>
    python -m cofire.ship.datapack restore <in.tar.gz>
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402
from shapely.geometry import box  # noqa: E402

from cofire.ship import domains  # noqa: E402
from cofire.ship.safe_fetch import FetchRefused, safe_extract  # noqa: E402

LOGGER = logging.getLogger("cofire.ship.datapack")

DATA = Path("data")
CLIPPED = DATA / "raw" / "usdm_co"
GATE = Path("artifacts/domains/usdm_clip_gate.json")


def _bbox() -> tuple[float, float, float, float]:
    from cofire.model.config import COLORADO_BBOX_BUFFERED

    return COLORADO_BBOX_BUFFERED


def clip_weekly(member: bytes, name: str) -> bytes:
    """One weekly map zip, clipped to Colorado, in the same layout."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src"
        src.mkdir()
        (Path(d) / "in.zip").write_bytes(member)
        files = safe_extract(Path(d) / "in.zip", src)
        shp = next(f for f in files if f.suffix.lower() == ".shp")
        g = gpd.read_file(shp)
        g = g.to_crs(4326) if g.crs is not None else g.set_crs(4326)
        g = g.clip(box(*_bbox()))
        g = g[~g.geometry.is_empty]
        out = Path(d) / "out"
        out.mkdir()
        g.to_file(out / shp.name)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(out.iterdir()):
                zf.write(f, arcname=f.name)
        return buf.getvalue()


def clip_year(year: int, src: Path = DATA / "raw" / "usdm", dst: Path = CLIPPED) -> Path:
    """Clip one year's national USDM archive to Colorado, week by week, into the same layout under
    `dst`, and return the clipped archive's path; resumable, weeks already clipped are skipped.
    """
    out = dst / f"{year}_USDM_M.zip"
    have: set[str] = set()
    if out.exists():
        with zipfile.ZipFile(out) as zf:
            have = set(zf.namelist())
    dst.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src / f"{year}_USDM_M.zip") as zin:
        todo = [n for n in zin.namelist() if n.lower().endswith(".zip") and n not in have]
        part = out.with_name(out.name + ".part")
        if out.exists():
            part.write_bytes(out.read_bytes())
        with zipfile.ZipFile(part, "a") as zout:
            for n in todo:
                zout.writestr(n, clip_weekly(zin.read(n), n))
        part.replace(out)
    LOGGER.info("%d: %d weeks clipped, %d already done, %.1f MB", year, len(todo), len(have), out.stat().st_size / 1e6)
    return out


def append_clipped(weekly_zip: Path, year: int, dst: Path = CLIPPED) -> None:
    """Add one newly fetched weekly map to the clipped archive."""
    out = dst / f"{year}_USDM_M.zip"
    dst.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "a") as zf:
        if weekly_zip.name not in zf.namelist():
            zf.writestr(weekly_zip.name, clip_weekly(weekly_zip.read_bytes(), weekly_zip.name))


def _raster(domain: str, raw: Path, start: str, end: str) -> np.ndarray:
    """The frozen rasterizer's cube for one domain over one archive directory."""
    import pandas as pd

    from cofire.model.data import DateRange
    from cofire.model.data.usdm import UsdmSource
    from cofire.ship.build_v11 import settings

    st = settings(domain)
    src = UsdmSource(st)
    with xr.open_dataset(next((st.processed_dir / "gridmet").glob("weekly_*.nc"))) as ds:
        tmpl = xr.Dataset(coords={"lat": ds["lat"].values, "lon": ds["lon"].values})
    with tempfile.TemporaryDirectory() as d:
        src._raster_path = lambda: Path(d) / "weekly.nc"  # type: ignore[method-assign]
        src._rasterize_zips(raw, tmpl, DateRange(start=pd.Timestamp(start).date(), end=pd.Timestamp(end).date()))
        with xr.open_dataset(Path(d) / "weekly.nc") as ds:
            return np.asarray(ds["usdm"].values)


def gate(end: str = "2026-09-22") -> dict[str, Any]:
    """Clipped archives must rasterize to exactly the national cubes, every domain."""
    out: dict[str, Any] = {}
    for d in domains.ORDER:
        a = _raster(d, DATA / "raw" / "usdm", "2007-01-01", end)
        b = _raster(d, CLIPPED, "2007-01-01", end)
        diff = int((a != b).sum())
        out[d] = {"ok": diff == 0, "cells_weeks": int(a.size), "n_different": diff,
                  "weeks_with_drought": int((a.reshape(a.shape[0], -1) > 0).any(axis=1).sum())}
        LOGGER.info("%s: %s", d, out[d])
    GATE.write_text(json.dumps(out, indent=1) + "\n")
    return out


def _members() -> list[Path]:
    keep: list[Path] = sorted(CLIPPED.glob("*_USDM_M.zip"))
    keep += sorted((DATA / "cache" / "erc_ext").glob("*"))
    keep += sorted((DATA / "vintages").rglob("*.nc"))
    for proc in sorted(DATA.glob("processed*")):
        keep += sorted((proc / "gridmet").glob("weekly_*.nc"))
    keep += sorted((DATA / "raw").glob("gridmet*/erc_2026.nc"))
    return [p for p in keep if p.is_file()]


def pack(out: Path) -> dict[str, Any]:
    """Tar the pack. Store cubes go in ERC-only, the only variable the refresh reads."""
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with tarfile.open(out, "w:gz") as tar, tempfile.TemporaryDirectory() as d:
        # The story map's county outlines, Colorado only, instead of the
        # national 11.6 MB boundary file.
        national = DATA / "raw" / "boundaries" / "cb_2023_us_county_500k.zip"
        co = DATA / "raw" / "boundaries" / "co_counties.geojson"
        if national.exists():
            g = gpd.read_file(f"zip://{national}")
            g[g["STATEFP"] == "08"].to_file(Path(d) / co.name, driver="GeoJSON")
            tar.add(Path(d) / co.name, arcname=str(co))
            n += 1
        elif co.exists():
            tar.add(co, arcname=str(co))
            n += 1
        for p in _members():
            arc = str(p)
            if p.parent.name == "gridmet" and p.parent.parent.name.startswith("processed") and p.name != "weekly_template.nc":
                with xr.open_dataset(p) as ds:
                    slim = ds[["erc"]].load() if "erc" in ds.data_vars else ds.load()
                tmp = Path(d) / p.name
                slim.to_netcdf(tmp)
                tar.add(tmp, arcname=arc)
                tmp.unlink()
            else:
                tar.add(p, arcname=arc)
            n += 1
    return {"files": n, "bytes": out.stat().st_size}


def restore(src: Path) -> dict[str, Any]:
    """Unpack under data/, refusing absolute paths and any entry outside it."""
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(src, "r:gz") as tar:
            for m in tar.getmembers():
                if m.name.startswith(("/", "\\")) or ".." in Path(m.name).parts or not m.name.startswith("data/"):
                    raise FetchRefused(f"pack entry escapes data/: {m.name}")
                if not (m.isfile() or m.isdir()):
                    raise FetchRefused(f"pack entry is not a plain file: {m.name}")
            tar.extractall(d, filter="data")
        n = 0
        for f in Path(d).rglob("*"):
            if f.is_file():
                rel = f.relative_to(d)
                (Path(".") / rel).parent.mkdir(parents=True, exist_ok=True)
                f.replace(Path(".") / rel)
                n += 1
    # The frozen rasterizer reads data/raw/usdm; point it at the clipped copy.
    usdm = DATA / "raw" / "usdm"
    if not usdm.exists():
        usdm.symlink_to(CLIPPED.resolve())
    return {"files": n}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = sys.argv[1]
    if cmd == "clip":
        print(clip_year(int(sys.argv[2])))
    elif cmd == "gate":
        r = gate()
        print(json.dumps(r, indent=1))
        sys.exit(0 if all(v["ok"] for v in r.values()) else 1)
    elif cmd == "pack":
        print(pack(Path(sys.argv[2])))
    elif cmd == "restore":
        print(restore(Path(sys.argv[2])))
    else:
        raise SystemExit(__doc__)
