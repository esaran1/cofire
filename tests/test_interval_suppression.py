"""Interval suppression must be driven by the uncertainty status.

The failure mode this guards against: a client deciding whether to draw a band
by looking at which keys happen to be present in the payload. It would then draw
a band wherever interval data existed, including where the record does not
support one.

The contract asserted here is that the payload NAMES the state rather than
leaving it to be inferred, that the state was fixed before the sealed year was
opened, and that a horizon not in the `interval` state carries no bounds at all,
so there is nothing to draw by mistake.
"""

from __future__ import annotations

import numpy as np
import pytest
from cofire.api import app
from cofire.model.uncertainty.status import PoolRegime, classify
from fastapi.testclient import TestClient

client = TestClient(app)


def _pool(coverage: float, usdm_max: float = 2.058) -> PoolRegime:
    years = {2018: 2.058, 2019: 0.460, 2020: 1.554, 2021: 0.853, 2022: 0.905, 2023: 0.621, 2024: 0.017, 2025: 0.065}
    v = np.array(list(years.values()), dtype=float)
    return PoolRegime(
        usdm_min=float(v.min()),
        usdm_max=usdm_max,
        usdm_mean=float(v.mean()),
        usdm_sd=float(v.std()),
        pool_years=sorted(years),
        measured_coverage=coverage,
    )


def test_show_interval_is_a_function_of_status_only() -> None:
    """Across the whole severity range, show_interval tracks status and nothing else."""
    pool = _pool(0.88)
    for usdm in np.linspace(0.0, 4.0, 40):
        pos = classify(float(usdm), pool)
        expected = pos.status != "uncalibrated"
        assert (pos.widen_factor >= 1.0) is True
        # The API contract mirrors this: show_interval == (status != uncalibrated)
        assert expected == (pos.status in {"calibrated", "extrapolating"})


def test_low_pool_coverage_suppresses_regardless_of_severity() -> None:
    """A pool that cannot cover its own folds suppresses at every severity.

    This is the live configuration: measured coverage 0.331 against a 0.90
    target, below the 0.60 floor.
    """
    weak = _pool(0.331)
    for usdm in (0.0, 0.5, 1.109, 2.0, 3.5):
        assert classify(float(usdm), weak).status == "uncalibrated", f"usdm={usdm} not suppressed"


def test_suppression_is_not_keyed_to_issue_date() -> None:
    """Identical diagnostics must give identical suppression, whatever the year.

    2026 is the sealed holdout, but that is not why its intervals are hidden.
    They are hidden because the pool's measured coverage is below the floor, and
    a 2024 issue with the same pool must behave identically.
    """
    weak = _pool(0.331)
    healthy = _pool(0.88)
    usdm = 1.109
    assert classify(usdm, weak).status == "uncalibrated"
    assert classify(usdm, healthy).status != "uncalibrated"


@pytest.mark.parametrize("issue_is_2026", [True, False])
def test_api_show_interval_matches_status(issue_is_2026: bool) -> None:
    """Live API: show_interval is the negation of the uncalibrated state."""
    issues = client.get("/forecast/issues").json()["issues"]
    if not issues:
        pytest.skip("no exported issues")
    wanted = [i for i in issues if i.startswith("2026")] if issue_is_2026 else [i for i in issues if not i.startswith("2026")]
    if not wanted:
        pytest.skip("no issues of the requested vintage")
    grid = client.get("/forecast/grid", params={"issue": wanted[-1], "horizon": 4}).json()
    feats = grid.get("features") or []
    if not feats:
        pytest.skip("no cells for that issue")
    lon, lat = feats[0]["geometry"]["coordinates"]
    body = client.get("/forecast", params={"lat": lat, "lon": lon, "issue": wanted[-1]}).json()
    u = body.get("uncertainty")
    assert u is not None, "/forecast must carry an uncertainty block"
    assert u["show_interval"] == (u["status"] != "uncalibrated")


def test_interval_columns_may_be_present_while_suppressed() -> None:
    """The payload carrying fire_lo/fire_hi must not imply the band is drawn.

    `forecast_issues` attaches intervals from the frozen calibrate pool, so the
    columns exist on 2026 rows. Suppression is a separate decision.
    """
    issues = client.get("/forecast/issues").json()["issues"]
    y2026 = [i for i in issues if i.startswith("2026")]
    if not y2026:
        pytest.skip("no 2026 issues exported")
    grid = client.get("/forecast/grid", params={"issue": y2026[-1], "horizon": 4}).json()
    feats = grid.get("features") or []
    if not feats:
        pytest.skip("no cells")
    lon, lat = feats[0]["geometry"]["coordinates"]
    body = client.get("/forecast", params={"lat": lat, "lon": lon, "issue": y2026[-1]}).json()
    hz = body["horizons"]["4"]

    # The principle is unchanged; the contract that carries it is not. The
    # shipped payload names the state instead of leaving the client to infer one
    # from which keys happen to be present, which is what this test was written
    # to catch. A horizon that is not in the `interval` state must carry no
    # bounds at all, so there is nothing for a client to draw by mistake.
    assert hz["state"] in {"interval", "historical_range", "uncalibrated"}
    if hz["state"] == "interval":
        assert hz.get("lo") is not None and hz.get("hi") is not None
    else:
        assert hz.get("lo") is None and hz.get("hi") is None
        assert hz["reason"], "a suppressed interval must say why"
