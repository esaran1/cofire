"""Forecast domains: the two frozen counties plus the v1.1 Denver domains.

Larimer and Pueblo are rectangles defined in the frozen config. The v1.1
domains are footprints: the gridMET cells a boundary polygon touches. Each is
fetched and processed as the rectangle enclosing its footprint (the frozen
pipeline selects by bbox), and the footprint mask says which of those cells
belong to the domain.

Boundaries are resolved from files already on disk, fetched once through
``safe_fetch``:

* Denver: Census cartographic county boundary, GEOID 08031.
* Upper South Platte: the WBD HUC8 whose name is exactly "Upper South Platte",
  cut to the HUC12s that drain to Strontia Springs Reservoir (located by its
  GNIS name in NHD).
* Dillon: the WBD HUC8 whose name is exactly "Blue", cut to the HUC12s that
  drain to the HUC12 named "Dillon Reservoir-Blue River".

Registration inserts the new domains into ``config.SUBSETS`` at runtime, so the
frozen code runs on them unchanged.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

from cofire.model import config

ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_DIR = ROOT / "data" / "raw" / "boundaries"
WBD_DIR = BOUNDARY_DIR / "wbd"
FOOTPRINTS = ROOT / "artifacts" / "domains" / "footprints.json"

# gridMET grid: cell centres at 49.4 - i/24 N and -124.7667 + j/24 E.
GRID_STEP = 1.0 / 24.0
GRID_LAT0 = 49.4
GRID_LON0 = -124.76666666666667

DENVER_GEOID = "08031"
ORDER = ("denver", "upper_south_platte", "dillon", "larimer", "pueblo")
LABELS = {
    "denver": "Denver",
    "upper_south_platte": "Upper South Platte",
    "dillon": "Dillon",
    "larimer": "Larimer",
    "pueblo": "Pueblo",
}
NEW = ("denver", "upper_south_platte", "dillon")
DEFAULT = "denver"


@dataclass(frozen=True)
class Footprint:
    name: str
    label: str
    kind: str  # "urban" | "watershed"
    source: str
    matched: dict[str, str]
    bbox: tuple[float, float, float, float]
    n_lat: int
    n_lon: int
    cells: list[tuple[float, float]]  # footprint cell centres (lat, lon)
    area_km2: float
    nominal_fips: str


def _snap(v: float, origin: float) -> float:
    return origin + round((v - origin) / GRID_STEP) * GRID_STEP


def footprint_cells(poly: Any) -> list[tuple[float, float]]:
    """Centres of every gridMET cell whose 1/24 degree square touches ``poly``."""
    west, south, east, north = poly.bounds
    half = GRID_STEP / 2
    lats = np.arange(_snap(south, GRID_LAT0) - GRID_STEP, _snap(north, GRID_LAT0) + 2 * GRID_STEP, GRID_STEP)
    lons = np.arange(_snap(west, GRID_LON0) - GRID_STEP, _snap(east, GRID_LON0) + 2 * GRID_STEP, GRID_STEP)
    out = []
    for la in lats:
        for lo in lons:
            if poly.intersects(box(lo - half, la - half, lo + half, la + half)):
                out.append((round(float(la), 6), round(float(lo), 6)))
    return sorted(out, key=lambda c: (-c[0], c[1]))


def _bbox(cells: list[tuple[float, float]]) -> tuple[tuple[float, float, float, float], int, int]:
    """A bbox whose centre selection is exactly the footprint's rectangle.

    The pad is a quarter cell, so float noise in either grid cannot add or drop
    a row.
    """
    lats = [c[0] for c in cells]
    lons = [c[1] for c in cells]
    pad = GRID_STEP / 4
    bbox = (min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad)
    n_lat = round((max(lats) - min(lats)) / GRID_STEP) + 1
    n_lon = round((max(lons) - min(lons)) / GRID_STEP) + 1
    return tuple(round(v, 6) for v in bbox), n_lat, n_lon  # type: ignore[return-value]


def _area_km2(poly: Any) -> float:
    return float(gpd.GeoSeries([poly], crs=4326).to_crs(5070).area.iloc[0] / 1e6)


def denver() -> Footprint:
    zp = BOUNDARY_DIR / "cb_2023_us_county_500k.zip"
    gdf = gpd.read_file(f"zip://{zp}")
    row = gdf[gdf["GEOID"] == DENVER_GEOID]
    if len(row) != 1:
        raise ValueError(f"expected one county with GEOID {DENVER_GEOID}, found {len(row)}")
    poly = row.to_crs(4326).geometry.iloc[0]
    cells = footprint_cells(poly)
    bbox, n_lat, n_lon = _bbox(cells)
    return Footprint(
        name="denver", label=LABELS["denver"], kind="urban",
        source=f"Census cartographic boundary {zp.name}",
        matched={"GEOID": DENVER_GEOID, "NAME": str(row["NAME"].iloc[0]), "NAMELSAD": str(row["NAMELSAD"].iloc[0])},
        bbox=bbox, n_lat=n_lat, n_lon=n_lon, cells=cells, area_km2=round(_area_km2(poly), 1),
        nominal_fips=DENVER_GEOID,
    )


def huc8_by_name(tag: str, name: str) -> dict[str, Any]:
    """The single WBD HUC8 in Colorado whose name is exactly ``name``."""
    feats = json.loads((WBD_DIR / f"huc8_{tag}_names.json").read_text())["features"]
    hits = [f["attributes"] for f in feats if f["attributes"]["name"] == name]
    if len(hits) != 1:
        cands = [(f["attributes"]["huc8"], f["attributes"]["name"]) for f in feats]
        raise LookupError(f"HUC8 name {name!r} matched {len(hits)}; candidates {cands}")
    return dict(hits[0])


def upstream(huc12s: gpd.GeoDataFrame, outlet: str) -> gpd.GeoDataFrame:
    """The outlet HUC12 and every HUC12 in the frame whose flow reaches it."""
    to = dict(zip(huc12s["huc12"], huc12s["tohuc"], strict=True))
    keep = set()
    for h in to:
        cur, seen = h, set()
        while cur in to and cur not in seen:
            if cur == outlet:
                keep.add(h)
                break
            seen.add(cur)
            cur = to[cur]
    return huc12s[huc12s["huc12"].isin(keep)]


def _outlet_containing(huc12s: gpd.GeoDataFrame, reservoir: Path) -> tuple[str, str, dict[str, str]]:
    res = gpd.read_file(reservoir)
    if len(res) != 1:
        raise LookupError(f"{reservoir.name}: expected one waterbody, found {len(res)}")
    hit = huc12s[huc12s.intersects(res.geometry.iloc[0])]
    if len(hit) != 1:
        # The dam is at the downstream end, so the outlet is the one the others drain into.
        inside = set(hit["huc12"])
        hit = hit[~hit["tohuc"].isin(inside) | ~hit["huc12"].isin(set(hit["tohuc"]))]
        hit = hit[hit["tohuc"].map(lambda t: t not in inside)]
    if len(hit) != 1:
        raise LookupError(f"{reservoir.name} spans HUC12s {list(hit['huc12'])} with no unique outlet")
    props = {str(k): str(v) for k, v in res.drop(columns="geometry").iloc[0].items()}
    return str(hit["huc12"].iloc[0]), str(hit["name"].iloc[0]), props


def _outlet_named(huc12s: gpd.GeoDataFrame, name: str) -> tuple[str, str]:
    hit = huc12s[huc12s["name"] == name]
    if len(hit) != 1:
        raise LookupError(f"HUC12 name {name!r} matched {len(hit)}; candidates {sorted(huc12s['name'])}")
    return str(hit["huc12"].iloc[0]), name


def watershed(name: str, tag: str, huc8_name: str, nominal_fips: str) -> Footprint:
    h8 = huc8_by_name(tag, huc8_name)
    huc12s = gpd.read_file(WBD_DIR / f"huc12_{h8['huc8']}.geojson")
    matched: dict[str, str] = {"huc8": str(h8["huc8"]), "huc8_name": str(h8["name"]),
                               "huc8_area_km2": str(h8["areasqkm"])}
    if name == "upper_south_platte":
        outlet, outlet_name, res = _outlet_containing(huc12s, WBD_DIR / "nhd_strontia.geojson")
        matched |= {"reservoir": res.get("GNIS_NAME", ""), "reservoir_gnis_id": res.get("GNIS_ID", ""),
                    "reservoir_source": "USGS NHD waterbody, matched by GNIS name"}
    else:
        outlet, outlet_name = _outlet_named(huc12s, "Dillon Reservoir-Blue River")
        matched |= {"reservoir": "Dillon Reservoir",
                    "reservoir_source": "WBD HUC12 named for the reservoir"}
    up = upstream(huc12s, outlet)
    matched |= {"outlet_huc12": outlet, "outlet_huc12_name": outlet_name,
                "n_huc12_upstream": str(len(up)), "n_huc12_in_huc8": str(len(huc12s))}
    poly = unary_union(list(up.to_crs(4326).geometry))
    cells = footprint_cells(poly)
    bbox, n_lat, n_lon = _bbox(cells)
    return Footprint(
        name=name, label=LABELS[name], kind="watershed",
        source="USGS WBD HUC8/HUC12 (hydro.nationalmap.gov wbd MapServer)",
        matched=matched, bbox=bbox, n_lat=n_lat, n_lon=n_lon, cells=cells,
        area_km2=round(_area_km2(poly), 1), nominal_fips=nominal_fips,
    )


def resolve() -> dict[str, Footprint]:
    return {
        "denver": denver(),
        # Nominal FIPS feeds only the frozen USDM county fallback, which the
        # v1.1 build refuses (USDM is rasterized from the yearly shapefiles).
        "upper_south_platte": watershed("upper_south_platte", "usp", "Upper South Platte", "08093"),
        "dillon": watershed("dillon", "blue", "Blue", "08117"),
    }


def write(path: Path = FOOTPRINTS) -> dict[str, Footprint]:
    fps = resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: asdict(v) for k, v in fps.items()}, indent=1) + "\n")
    return fps


def load(path: Path = FOOTPRINTS) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = json.loads(path.read_text())
    return data


def register(path: Path = FOOTPRINTS) -> None:
    """Make the v1.1 domains selectable as ``COFIRE_SUBSET_NAME`` by the frozen code."""
    for name, fp in load(path).items():
        bbox = tuple(float(v) for v in fp["bbox"])
        config.SUBSETS[name] = (bbox, str(fp["nominal_fips"]))  # type: ignore[assignment]


def footprint_mask(name: str, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Boolean (lat, lon) mask of footprint cells; all True for the frozen rectangles."""
    if name not in NEW:
        return np.ones((len(lat), len(lon)), dtype=bool)
    cells = {(round(a, 3), round(b, 3)) for a, b in load()[name]["cells"]}
    return np.array([[(round(float(a), 3), round(float(b), 3)) in cells for b in lon] for a in lat])


if __name__ == "__main__":
    for fp in write().values():
        print(fp.name, fp.kind, fp.matched)
        print(f"  area {fp.area_km2} km2, footprint {len(fp.cells)} cells, rectangle "
              f"{fp.n_lat}x{fp.n_lon}={fp.n_lat * fp.n_lon}, bbox {fp.bbox}")
