"""The v1.1 domain footprints are pinned and select exactly their rectangles."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from cofire.model import config
from cofire.model.data.gridmet import _clip_to_bbox
from cofire.ship import domains

EXPECTED = {  # name: (footprint cells, n_lat, n_lon, matched code)
    "denver": (52, 8, 13, "08031"),
    "upper_south_platte": (202, 18, 21, "10190002"),
    "dillon": (79, 9, 13, "14010002"),
}


def _grid() -> xr.DataArray:
    lat = domains.GRID_LAT0 - np.arange(600) / 24.0
    lon = domains.GRID_LON0 + np.arange(1386) / 24.0
    return xr.DataArray(np.zeros((len(lat), len(lon)), dtype="float32"),
                        coords={"lat": lat, "lon": lon}, dims=("lat", "lon"))


@pytest.mark.parametrize("name", list(EXPECTED))
def test_footprint_is_pinned(name: str) -> None:
    fp = domains.load()[name]
    n, n_lat, n_lon, code = EXPECTED[name]
    assert len(fp["cells"]) == n and (fp["n_lat"], fp["n_lon"]) == (n_lat, n_lon)
    assert code in fp["matched"].values()


@pytest.mark.parametrize("name", list(EXPECTED))
def test_bbox_selects_exactly_the_footprint_rectangle(name: str) -> None:
    fp = domains.load()[name]
    sub = _clip_to_bbox(_grid(), tuple(fp["bbox"]))
    assert (sub.sizes["lat"], sub.sizes["lon"]) == (fp["n_lat"], fp["n_lon"])
    mask = domains.footprint_mask(name, sub.lat.values, sub.lon.values)
    assert int(mask.sum()) == len(fp["cells"]), "every footprint cell lies in the rectangle"


def test_registration_reaches_the_frozen_config() -> None:
    domains.register()
    for name in domains.NEW:
        assert name in config.SUBSETS
    assert config.SUBSETS["larimer"][1] == config.LARIMER_FIPS, "frozen entries untouched"


def test_upstream_trace_stops_at_the_outlet() -> None:
    import geopandas as gpd

    h = gpd.GeoDataFrame({"huc12": ["a", "b", "c", "d"], "tohuc": ["b", "c", "x", "c"]},
                         geometry=gpd.points_from_xy([0] * 4, [0] * 4))
    assert set(domains.upstream(h, "b")["huc12"]) == {"a", "b"}
    assert set(domains.upstream(h, "c")["huc12"]) == {"a", "b", "c", "d"}


@pytest.mark.parametrize("name", domains.NEW)
def test_each_new_domain_reads_and_writes_only_its_own_paths(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cofire.model.config import get_settings
    from cofire.ship import build_v11

    # Recorded so teardown restores them after `settings` overwrites them.
    monkeypatch.setenv("COFIRE_SUBSET_NAME", "pueblo")
    monkeypatch.setenv("COFIRE_DEV_SUBSET", "1")
    try:
        st = build_v11.settings(name)
        assert st.processed_dir.name == f"processed_{name}"
        assert st.bbox == tuple(domains.load()[name]["bbox"])
    finally:
        get_settings.cache_clear()
