"""The Urban Ember Score for Denver, beside the frozen wildland-edge list."""

from __future__ import annotations

import yaml
from cofire.model import ember as frozen
from cofire.ship import ember_zones


def test_city_weights_sum_to_one_and_every_item_has_a_source() -> None:
    data = yaml.safe_load(ember_zones.CITY_PATH.read_text())
    assert abs(sum(g["weight"] for g in data.values()) - 1.0) < 1e-9
    assert set(data) == {"water", "smoke", "ignition"}
    for g in data.values():
        for i in g["items"]:
            assert i["source"] and i["rationale"] and i["cost"] in {"free", "under_100", "contractor"}


def test_city_score_is_completion() -> None:
    items = ember_zones.score({}, "city")["items"]
    assert ember_zones.score({}, "city")["score"] == 0
    assert ember_zones.score({i["id"]: True for i in items}, "city")["score"] == 1
    water = [i["id"] for i in items if i["group"] == "water"]
    assert abs(ember_zones.score(dict.fromkeys(water, True), "city")["score"] - 0.40) < 1e-9


def test_the_wildland_edge_list_is_the_frozen_one() -> None:
    assert ember_zones.score({}, "wui") == frozen.score({}, "wui")


def test_city_copy_has_no_dashes() -> None:
    text = ember_zones.CITY_PATH.read_text()
    assert "—" not in text and "–" not in text
