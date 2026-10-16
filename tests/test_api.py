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
            "cell_id": "40.5250_-105.0583",
            "horizon": 4,
            "drought_category": 2,
            "fire_band": "high",
            "issue": "2026-05-05",
        },
    )
    assert r.status_code == 200
    m = r.json()["locked_model"]
    # The model always makes a call; its chance appears only when checked.
    assert m["drought_likely"] is not None
    assert m["drought_likely_p"] is not None or m.get("drought_note")
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


def test_every_credit_is_complete() -> None:
    import json
    from pathlib import Path

    credits = json.loads(Path("app/lib/facts.json").read_text())["credits"]
    names = {c["name"] for c in credits}
    assert {"OpenStreetMap", "U.S. Drought Monitor", "gridMET", "High Park fire photo"} <= names
    for c in credits:
        assert c["license"] and c["credit"] and c["url"].startswith("https://")


def test_the_model_pick_is_the_most_likely_drought_category() -> None:
    from cofire.api import _likely_category

    cell = {"usdm": 2.0, "targets": {
        "d_improve1_h4": {"p": 0.10}, "d_nochange_h4": {"p": 0.48},
        "d_intensify1_h4": {"p": 0.42}, "d_intensify2_h4": {"p": 0.05}}}
    assert _likely_category(cell, 4) == {"drought_now": 2, "drought_likely": 2, "drought_likely_p": 0.48}
    cell["targets"]["d_nochange_h4"]["p"] = 0.20
    assert _likely_category(cell, 4)["drought_likely"] == 3  # 0.42 - 0.05 = 0.37 to D3
    assert _likely_category(None, 4)["drought_likely"] is None
    # Unchecked on the card: the call is still made from the model's own
    # numbers, but no chance is reported.
    cell["model"] = {k: v["p"] for k, v in cell["targets"].items()}
    cell["targets"]["d_intensify2_h4"]["p"] = None
    out = _likely_category(cell, 4)
    assert out["drought_likely"] is not None and out["drought_likely_p"] is None
    assert "could not be checked" in out["drought_note"]
    # From D3 worsening by two is impossible, so an unchecked number there is no gap.
    cell["usdm"] = 3.0
    assert _likely_category(cell, 4)["drought_likely_p"] is not None


def test_a_locked_pick_returns_the_model_numbers_the_page_shows() -> None:
    r = client.post("/predictions", json={"device_id": "t-lock", "cell_id": "39.7750_-104.8500",
                                          "horizon": 4, "drought_category": 2, "fire_band": "high"})
    m = r.json()["locked_model"]
    assert {"point", "drought_likely", "drought_likely_p"} <= set(m)


def test_a_pick_for_a_cell_that_does_not_exist_is_refused() -> None:
    r = client.post("/predictions", json={"device_id": "t-ghost", "cell_id": "40.5417_-105.0833",
                                          "horizon": 4, "drought_category": 2, "fire_band": "high"})
    assert r.status_code == 404
    assert client.get("/predictions/me", params={"device_id": "t-ghost"}).json() == []


def test_saved_ember_ticks_come_back_for_the_zone_asked_for() -> None:
    dev = "t-ember-zones"
    client.post("/ember/state", json={"device_id": dev, "zone": "wui", "state": {"water_leaks": True}})
    city = client.get("/ember/score", params={"device_id": dev, "zone": "city"}).json()
    assert city["zone"] == "city" and "water_leaks" in city["done"]
    assert client.get("/ember/score", params={"device_id": dev, "zone": "wui"}).json()["zone"] == "wui"
    assert client.get("/ember/score", params={"device_id": dev, "zone": "nowhere"}).status_code == 400


def test_a_pick_is_scored_once_its_week_is_in() -> None:
    from cofire.api import score_pick

    cells = {("c1", "2026-06-02"): {"usdm": 2.0, "erc_pct": 83.0}}
    base = {"cell_id": "c1", "issue": "2026-05-05", "horizon": 4}
    right = score_pick(base | {"drought_category": 2, "fire_band": "high"}, cells)
    assert right["status"] == "scored" and right["points"] == 2 and right["actual_band"] == "high"
    wrong = score_pick(base | {"drought_category": 0, "fire_band": "low"}, cells)
    assert wrong["points"] == 0 and wrong["drought_correct"] is False
    later = score_pick(base | {"issue": "2026-09-22", "drought_category": 2, "fire_band": "high"}, cells)
    assert later["status"] == "pending" and later["target_week"] == "2026-10-20"
    assert "model" not in " ".join(k for k in right), "the model is never scored"


def test_fire_band_edges_match_the_page() -> None:
    import re
    from pathlib import Path

    from cofire.api import FIRE_BAND_EDGES

    text = Path("app/lib/options.ts").read_text()
    page = {m[0]: (float(m[1]), float(m[2])) for m in re.findall(r'value: "(\w+)",[^}]*min: (\d+), max: (\d+)', text)}
    assert page == {name: (lo, hi) for name, lo, hi in FIRE_BAND_EDGES}


def test_the_leaderboard_ranks_by_points() -> None:
    r = client.post("/predictions", json={"device_id": "t-rank-a", "cell_id": "40.5250_-105.0583", "horizon": 4,
                                          "drought_category": 2, "fire_band": "high", "issue": "2026-05-05"})
    assert r.status_code == 200
    board = client.get("/leaderboard").json()
    assert all({"points", "scored", "picks"} <= set(row) for row in board)
    pts = [row["points"] for row in board]
    assert pts == sorted(pts, reverse=True)


def test_a_horizon_that_is_not_forecast_is_refused() -> None:
    r = client.post("/predictions", json={"device_id": "t-h", "cell_id": "40.5250_-105.0583", "horizon": 5,
                                          "drought_category": 2, "fire_band": "high"})
    assert r.status_code == 422


def test_every_ember_item_has_spanish() -> None:
    import json
    from pathlib import Path

    import yaml

    es = json.loads(Path("app/lib/i18n/ember_es.json").read_text())
    for f in ("cofire/ship/ember_city.yaml", "cofire/model/ember_checklist.yaml"):
        for gid, group in yaml.safe_load(Path(f).read_text()).items():
            if not isinstance(group, dict):
                continue
            assert es["groups"].get(gid), gid
            for item in group.get("items", []):
                t = es["items"].get(item["id"])
                assert t and t["label"] and t["rationale"], item["id"]


def test_open_data_is_served_and_names_are_checked() -> None:
    r = client.get("/open/index.json")
    assert r.status_code == 200
    idx = r.json()
    assert idx["license"]["name"] == "CC BY 4.0"
    assert [f["name"] for f in idx["fields"]][:3] == ["issue", "vintage", "area"]
    latest = client.get(f"/open/{idx['latest']['csv']}")
    assert latest.status_code == 200 and latest.text.startswith("issue,vintage,area,cell")
    assert client.get("/open/..%2Findex.json").status_code in (400, 404)
    assert client.get("/open/issues/../../secrets").status_code in (400, 404)
