"""Ember Score: weighted checklist. Score is completion, not a fire forecast."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CHECKLIST_PATH = Path(__file__).with_name("ember_checklist.yaml")


def load_checklist() -> dict[str, Any]:
    loaded = yaml.safe_load(CHECKLIST_PATH.read_text())
    if not isinstance(loaded, dict):
        raise ValueError("ember checklist must be a mapping")
    return loaded


def flatten_items(zone: str) -> list[dict[str, Any]]:
    data = load_checklist()
    items: list[dict[str, Any]] = []
    for group_id, group in data.items():
        weight = float(group["weight"])
        group_items = [i for i in group["items"] if zone in i.get("zone_applicability", [])]
        if not group_items:
            continue
        share = weight / len(group_items)
        for item in group_items:
            items.append({**item, "group": group_id, "group_label": group["label"], "item_weight": share})
    return items


def score(state: dict[str, bool], zone: str) -> dict[str, Any]:
    items = flatten_items(zone)
    done_w = sum(i["item_weight"] for i in items if state.get(i["id"]))
    total = sum(i["item_weight"] for i in items) or 1.0
    value = done_w / total
    free_todo = sorted(
        [i for i in items if i["cost"] == "free" and not state.get(i["id"])],
        key=lambda i: -i["item_weight"],
    )[:3]
    return {
        "score": value,
        "zone": zone,
        "items": items,
        "top_free": free_todo,
        "done": [i["id"] for i in items if state.get(i["id"])],
    }
