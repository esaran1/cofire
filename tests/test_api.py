from __future__ import annotations

from cofire.api import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_forecast_contract() -> None:
    """Contract test, domain-agnostic.

    Coordinates and issue dates follow the active dev subset, so the test asks
    the API what it has rather than hardcoding a location that breaks whenever
    the subset moves.
    """
    issues = client.get("/forecast/issues").json()["issues"]
    assert issues, "no exported issues; run `make export`"
    cell = client.get("/forecast/grid", params={"issue": issues[-1], "horizon": 4}).json()
    feats = cell.get("features") or []
    assert feats, "no cells for the latest issue"
    lon, lat = feats[0]["geometry"]["coordinates"]
    r = client.get("/forecast", params={"lat": lat, "lon": lon, "issue": issues[-1]})
    assert r.status_code == 200
    body = r.json()
    assert "horizons" in body
    assert "4" in body["horizons"]
    assert body["resolution_m"] == 4000

    # The shipped contract: every horizon declares the state it renders in and
    # why. The state was fixed in the preregistration before the sealed year was
    # opened, so a payload without it would let the client decide, which is the
    # thing the preregistration exists to prevent.
    hz = body["horizons"]["4"]
    assert hz["state"] in {"interval", "historical_range", "uncalibrated"}
    assert hz["reason"], "a rendering state without a reason is a number with no account of itself"
    assert "point" in hz

    # `why` is absent by design. The shipped configuration is a transition table
    # and a damped persistence rule, neither of which has a per-feature
    # attribution; an empty or invented driver list would be worse than none.
    assert not body.get("why")


def test_issues() -> None:
    """Issues are present and ISO-formatted. The specific dates track the
    active subset and the stages that have been run, so they are not asserted."""
    issues = client.get("/forecast/issues").json()["issues"]
    assert issues, "no exported issues"
    assert all(len(i) == 10 and i[4] == "-" for i in issues)
    assert issues == sorted(issues)


def test_ember_and_observation() -> None:
    z = client.get("/ember/checklist", params={"zone": "wui"})
    assert z.status_code == 200
    assert "top_free" in z.json()
    obs = client.post(
        "/observations",
        json={
            "device_id": "dev1",
            "lat": 40.54,
            "lon": -105.08,
            "type": "lawn_crispy",
            "note": "front yard",
        },
    )
    assert obs.status_code == 200
    body = obs.json()
    # A report does not change the forecast, and the response must not claim it
    # does. This used to check only that a "nudge" key existed, which let a
    # hardcoded +0.05 / +1.2 "effect" through to every user who filed one.
    assert body["changes_forecast"] is False
    assert body["nudge"] is None
    # Fort Collins sits inside the Larimer forecast area, so the report is
    # attached to a real cell and says which.
    assert body["cell"] is not None
    assert body["cell"]["domain"] == "larimer"


def test_a_report_outside_every_area_is_not_attached() -> None:
    """The eastern plains lie outside all five domains, where there is no forecast.

    This used to use the point between Larimer and Pueblo, which the Upper
    South Platte domain now covers.
    """
    r = client.post(
        "/observations",
        json={"device_id": "t-outside", "lat": 39.0, "lon": -103.5, "type": "creek_low", "note": ""},
    )
    assert r.status_code == 200
    assert r.json()["cell"] is None


def test_beat_the_model() -> None:
    r = client.post(
        "/predictions",
        json={
            "device_id": "dev1",
            "cell_id": "40.5417_-105.0833",
            "horizon": 4,
            "drought_category": 2,
            "fire_band": "high",
            "issue": "2026-05-05",
        },
    )
    assert r.status_code == 200
    me = client.get("/predictions/me", params={"device_id": "dev1"})
    assert len(me.json()) >= 1


def test_forecast_defaults_to_the_latest_issue() -> None:
    """With no issue named, the answer is the newest forecast, not the oldest."""
    issues = client.get("/forecast/issues").json()["issues"]
    body = client.get("/forecast", params={"lat": 40.55, "lon": -105.08}).json()
    assert body["issue"] == max(issues)


def test_domain_index_and_bundles() -> None:
    r = client.get("/domains")
    if r.status_code == 404:
        return
    idx = r.json()
    assert idx["default"] == "denver"
    b = client.get(f"/domains/denver/{idx['issues'][-1]}").json()
    assert b["domain"] == "denver" and b["cells"]
    assert client.get("/domains/..%2Fetc/2026-09-22").status_code in (400, 404)
    assert client.get("/domains/denver/not-a-date").status_code == 400


def test_city_ember_zone_is_served() -> None:
    assert client.get("/ember/checklist?zone=city").json()["zone"] == "city"
    assert client.get("/ember/checklist?zone=nowhere").status_code == 400
