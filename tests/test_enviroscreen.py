"""The EnviroScreen context layer: Denver's tracts only, percentiles only, with provenance."""

from __future__ import annotations

import json

import pytest
from cofire.ship.enviroscreen import FIELDS, N_TRACTS, OUT, tidy
from cofire.ship.safe_fetch import FetchRefused


def _raw(geoid: str = "08031000102", v: float = 50.0) -> dict:
    props = {"GEOID": geoid, "Ttl_P": 100, **{k: v for k in FIELDS}}
    return {"type": "FeatureCollection", "features": [{"properties": props, "geometry": None}] * N_TRACTS}


def test_an_arcgis_error_served_as_json_is_refused() -> None:
    with pytest.raises(FetchRefused, match="not a feature collection"):
        tidy({"error": {"code": 400, "message": "Invalid query"}}, "t", "s")


def test_a_tract_outside_denver_or_a_value_off_the_percentile_scale_is_refused() -> None:
    with pytest.raises(FetchRefused, match="outside Denver"):
        tidy(_raw(geoid="08001000100"), "t", "s")
    with pytest.raises(FetchRefused, match="not a percentile"):
        tidy(_raw(v=140.0), "t", "s")
    with pytest.raises(FetchRefused, match="expected"):
        tidy({"type": "FeatureCollection", "features": _raw()["features"][:5]}, "t", "s")


def test_the_committed_layer_is_denver_with_its_source() -> None:
    d = json.loads(OUT.read_text())
    assert len(d["features"]) == N_TRACTS
    assert all(f["properties"]["geoid"].startswith("08031") for f in d["features"])
    assert d["meta"]["page"].startswith("https://") and d["meta"]["sha256"]
    assert set(d["features"][0]["properties"]) == {"geoid", "pop", *FIELDS.values()}
