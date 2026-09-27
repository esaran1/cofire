"""The v1.1 ERC wrapper: exact wire pricing, strict validation, ASCII gate parsing."""

from __future__ import annotations

import sys

import numpy as np
import pytest
import xarray as xr
from cofire.ship import erc_fetch, runner
from cofire.ship.safe_fetch import FetchRefused

DDS = """Dataset {
    Grid {
     ARRAY:
        UInt16 energy_release_component-g[day = 366][lat = 585][lon = 1386];
     MAPS:
        Float64 day[day = 366];
    } energy_release_component-g;
} MET/erc/erc_2020.nc;"""

ASCII = """Dataset {
} MET/erc/erc_2020.nc;
---------------------------------------------
energy_release_component-g.energy_release_component-g[3][1][1]
[0][0], 71
[1][0], 32767
[2][0], 72

energy_release_component-g.day[3]
44009.0, 44010.0, 44011.0

energy_release_component-g.lat[1]
39.73333333333334

energy_release_component-g.lon[1]
-104.97499996666667
"""


def _da(vals: np.ndarray) -> xr.DataArray:
    return xr.DataArray(vals, dims=("day", "lat", "lon"))


def test_pricing_counts_each_16_bit_value_as_a_4_byte_xdr_word() -> None:
    dims = erc_fetch._dims(DDS)
    assert dims == {"day": 366, "lat": 585, "lon": 1386}
    n = erc_fetch.projected_bytes(dims, 8, 13)
    assert n == 366 * 8 * 13 * 4 + (366 + 8 + 13) * 8 + (366 + 585 + 1386) * 8 + erc_fetch._OPEN_OVERHEAD


def test_a_dds_for_some_other_variable_is_refused() -> None:
    with pytest.raises(FetchRefused):
        erc_fetch._dims(DDS.replace("UInt16", "Float32"))


def test_validation_accepts_physical_erc() -> None:
    erc_fetch.validate(_da(np.random.default_rng(0).uniform(5, 90, (10, 2, 3))), 2, 3, 10)


@pytest.mark.parametrize(
    ("vals", "why"),
    [
        (np.full((10, 2, 3), 40.0), "constant"),
        (np.full((10, 2, 3), 400.0), "physical"),
        (np.full((10, 2, 3), np.nan), "finite"),
    ],
)
def test_validation_refuses_bad_arrays(vals: np.ndarray, why: str) -> None:
    with pytest.raises(FetchRefused, match=why):
        erc_fetch.validate(_da(vals), 2, 3, 10)


def test_validation_refuses_the_wrong_rectangle() -> None:
    with pytest.raises(FetchRefused, match="shape"):
        erc_fetch.validate(_da(np.random.default_rng(0).uniform(5, 90, (10, 2, 4))), 2, 3, 10)


def test_ascii_parser_reads_values_days_and_coordinates() -> None:
    vals, days, lat, lon = erc_fetch._parse_ascii(ASCII)
    assert vals == [71.0, 32767.0, 72.0] and days == [44009.0, 44010.0, 44011.0]
    assert lat == pytest.approx(39.7333333) and lon == pytest.approx(-104.975)


def test_watchdog_returns_the_stage_exit_code() -> None:
    assert runner.run("ok", [sys.executable, "-c", "raise SystemExit(3)"]) == 3
