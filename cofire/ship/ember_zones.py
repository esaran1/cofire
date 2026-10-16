"""Ember checklists by zone: the Denver city list plus the frozen ones.

`city` is the Urban Ember Score for Denver, read from `ember_city.yaml` beside
this file. `wui` and `urban` are the frozen wildland-edge checklist in
`cofire/model/ember_checklist.yaml`, scored by the frozen code unchanged.

The city list is scored with the same rule as the frozen one: group weight
split evenly across the group's items, score = completed weight over total.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from cofire.model import ember as frozen

CITY_PATH = Path(__file__).with_name("ember_city.yaml")
ZONES = ("city", "wui", "urban")


def _city_items() -> list[dict[str, Any]]:
    data = yaml.safe_load(CITY_PATH.read_text())
    if not isinstance(data, dict):
        raise ValueError("city ember checklist must be a mapping")
    total = sum(float(g["weight"]) for g in data.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"city ember group weights sum to {total}, not 1")
    items: list[dict[str, Any]] = []
    for gid, group in data.items():
        share = float(group["weight"]) / len(group["items"])
        for item in group["items"]:
            items.append({**item, "group": gid, "group_label": group["label"], "item_weight": share})
    return items


def score(state: dict[str, bool], zone: str) -> dict[str, Any]:
    """Score ticked items for a zone: wui and urban go to the frozen scorer; city returns its score,
    items, the three heaviest free items not yet done, and the done ids. Raises ValueError for an
    unknown zone.
    """
    if zone not in ZONES:
        raise ValueError(f"zone must be one of {ZONES}")
    if zone != "city":
        return frozen.score(state, zone)
    items = _city_items()
    done_w = sum(i["item_weight"] for i in items if state.get(i["id"]))
    total = sum(i["item_weight"] for i in items) or 1.0
    free_todo = sorted(
        [i for i in items if i["cost"] == "free" and not state.get(i["id"])],
        key=lambda i: -i["item_weight"],
    )[:3]
    return {
        "score": done_w / total,
        "zone": zone,
        "items": items,
        "top_free": free_todo,
        "done": [i["id"] for i in items if state.get(i["id"])],
    }
