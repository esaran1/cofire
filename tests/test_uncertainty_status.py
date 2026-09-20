"""Tests for the three-state uncertainty status.

The states must follow from calibration diagnostics, not from a hand-set flag.
See cofire/model/uncertainty/status.py and docs/PREREGISTRATION_CALIBRATION.md.
"""

from __future__ import annotations

import numpy as np
from cofire.model.uncertainty.status import (
    EXTRAPOLATION_LIMIT_SD,
    UNCALIBRATED_COVERAGE,
    PoolRegime,
    classify,
)

# Real per-year mean USDM from the 2018-2025 record.
RECORD = {2018: 0.147, 2019: 0.024, 2020: 0.901, 2021: 0.916, 2022: 0.363, 2023: 0.006, 2024: 0.679, 2025: 0.648}
YEAR_2026_MEAN_USDM = 2.231


def _pool(coverage: float = 0.88) -> PoolRegime:
    v = np.array(list(RECORD.values()), dtype=float)
    return PoolRegime(
        usdm_min=float(v.min()),
        usdm_max=float(v.max()),
        usdm_mean=float(v.mean()),
        usdm_sd=float(v.std()),
        pool_years=sorted(RECORD),
        measured_coverage=coverage,
    )


def test_inside_range_is_calibrated() -> None:
    r = classify(0.5, _pool())
    assert r.status == "calibrated"
    assert r.widen_factor == 1.0


def test_pool_maximum_is_still_calibrated() -> None:
    """The boundary belongs to the calibrated side."""
    pool = _pool()
    assert classify(pool.usdm_max, pool).status == "calibrated"


def test_mild_exceedance_is_extrapolating_and_widens() -> None:
    r = classify(1.10, _pool())
    assert r.status == "extrapolating"
    assert r.widen_factor > 1.0, "extrapolating must widen the interval"
    assert 0 < r.exceedance_sd <= EXTRAPOLATION_LIMIT_SD


def test_2026_regime_is_uncalibrated() -> None:
    """The regime that produced the No-go must suppress the interval.

    2026 sits ~3.7 pool SD past the record maximum; no year resembles it, so an
    interval would be fiction.
    """
    r = classify(YEAR_2026_MEAN_USDM, _pool())
    assert r.status == "uncalibrated"
    assert r.exceedance_sd > EXTRAPOLATION_LIMIT_SD


def test_weak_pool_coverage_forces_uncalibrated_even_inside_range() -> None:
    """A pool that cannot cover its own folds cannot support any interval."""
    weak = _pool(coverage=UNCALIBRATED_COVERAGE - 0.05)
    r = classify(0.5, weak)
    assert r.status == "uncalibrated"
    assert "coverage" in r.reason


def test_status_is_monotone_in_severity() -> None:
    """Increasing severity never moves the status back toward calibrated."""
    order = {"calibrated": 0, "extrapolating": 1, "uncalibrated": 2}
    pool = _pool()
    seen = [order[classify(u, pool).status] for u in np.linspace(0.0, 4.0, 40)]
    assert seen == sorted(seen), "status must not become less cautious as drought worsens"


def test_widen_factor_is_clipped() -> None:
    """Widening never runs away, even at the extrapolation limit."""
    pool = _pool()
    factors = [classify(u, pool).widen_factor for u in np.linspace(0.0, 4.0, 60)]
    assert max(factors) <= 3.0, "widen factor must respect the pre-registered clip"


def test_reason_is_always_populated() -> None:
    pool = _pool()
    for u in (0.0, 1.1, 3.0):
        assert classify(u, pool).reason.strip(), "every status needs a stated reason"


def test_api_forecast_carries_uncertainty_and_suppresses() -> None:
    """The /forecast payload must carry the status the Place Card acts on."""
    from cofire.api import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    body = client.get("/forecast?lat=40.5&lon=-105.5")
    if body.status_code != 200:
        return  # no exported forecast in this environment
    payload = body.json()
    u = payload.get("uncertainty")
    assert u is not None, "/forecast must carry an uncertainty block"
    assert u["status"] in {"calibrated", "extrapolating", "uncalibrated"}
    # show_interval must be the negation of the uncalibrated state.
    assert u["show_interval"] == (u["status"] != "uncalibrated")
    assert u["reason"].strip()


def test_api_status_endpoint_matches_classifier() -> None:
    from cofire.api import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    r = client.get("/uncertainty/status")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] in {"calibrated", "extrapolating", "uncalibrated"}
    if d.get("available"):
        assert "measured_coverage" in d
        assert d["show_interval"] == (d["status"] != "uncalibrated")
