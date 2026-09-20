from __future__ import annotations

from cofire.api import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_forecast_contract() -> None:
    r = client.get("/forecast", params={"lat": 40.54, "lon": -105.08, "issue": "2026-05-05"})
    assert r.status_code == 200
    body = r.json()
    assert "horizons" in body
    assert "4" in body["horizons"]
    assert "why" in body
    assert body["resolution_m"] == 4000
    assert len(body["why"]) == 5


def test_issues() -> None:
    r = client.get("/forecast/issues")
    assert "2026-05-05" in r.json()["issues"]


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
    assert "nudge" in obs.json()


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
