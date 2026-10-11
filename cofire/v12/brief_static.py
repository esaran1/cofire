"""The latest weekly brief, precomputed, so the page paints without fetching.

Mirrors `app/lib/brief.ts` exactly (a Playwright test compares the two on the
newest issue), from the same bundles. Written by the weekly refresh to
`app/lib/brief_latest.json`; the brief page fetches bundles only for older
weeks. The top three free actions of the city Ember list ride along.

    python -m cofire.v12.brief_static
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

BUNDLES = Path("artifacts/ship/domains")
OUT = Path("app/lib/brief_latest.json")
H = "4"
WATER = ("upper_south_platte", "dillon")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _round(x: float) -> int:
    return math.floor(x + 0.5)  # JavaScript's Math.round


def _odds(summary: dict[str, Any], key: str) -> dict[str, Any] | None:
    o = (summary.get(H) or {}).get(f"{key}_h{H}")
    if not isinstance(o, dict):
        return None
    return {"mean": _num(o.get("mean")), "state": o.get("state") if isinstance(o.get("state"), str) else None}


def _counts(b: dict[str, Any]) -> dict[int, int]:
    out: dict[int, int] = {}
    for c in b["cells"]:
        if c.get("usdm") is None:
            continue
        k = _round(float(c["usdm"]))
        out[k] = out.get(k, 0) + 1
    return out


def _rows(b: dict[str, Any], prev: dict[str, Any] | None) -> list[dict[str, Any]]:
    now, before = _counts(b), (_counts(prev) if prev else None)
    idx = {t: i for i, t in enumerate(b["targets"])}
    rows = []
    for cat in sorted(now, reverse=True):
        cell = next(c for c in b["cells"] if c.get("usdm") is not None and _round(float(c["usdm"])) == cat)

        def p(t: str, cell: dict[str, Any] = cell) -> float | None:
            i = idx.get(f"{t}_h{H}")
            return _num(cell["p"][i]) if i is not None else None

        rows.append({"cat": cat, "cells": now[cat], "cellsPrev": (before.get(cat, 0) if before is not None else None),
                     "stay": p("d_nochange"), "ease": "impossible" if cat == 0 else p("d_improve1"),
                     "worsen": "impossible" if cat == 4 else p("d_intensify1")})
    return rows


def _area(id_: str, label: str, b: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
    s = b["summary"]
    return {"id": id_, "label": label, "cells": len(b["cells"]),
            "dryNow": _num(s.get("erc_pct_now_median")),
            "dryNowPrev": _num(prev["summary"].get("erc_pct_now_median")) if prev else None,
            "dryAhead": _num((s.get(H) or {}).get("erc_pct_median")),
            "f80": _odds(s, "f_gt80"), "f90": _odds(s, "f_gt90"),
            "f80Prev": ((_odds(prev["summary"], "f_gt80") or {}).get("mean") if prev else None),
            "rows": _rows(b, prev)}


def build() -> dict[str, Any]:
    from cofire.ship.ember_zones import score

    index = json.loads((BUNDLES / "index.json").read_text())
    issues = index["issues"]
    cur, prev = issues[-1], (issues[-2] if len(issues) > 1 else None)

    def load(d: str, i: str | None) -> dict[str, Any] | None:
        return json.loads((BUNDLES / d / f"{i}.json").read_text()) if i else None

    den, pden = load("denver", cur), load("denver", prev)
    assert den is not None
    water = []
    for w in WATER:
        b = load(w, cur)
        assert b is not None
        water.append(_area(w, index["domains"][w]["label"], b, load(w, prev)))
    items = [i for i in score({}, "city")["items"] if i["cost"] == "free"]
    items.sort(key=lambda i: -i["item_weight"])
    brief = {"issue": cur, "prevIssue": prev, "denver": _area("denver", "Denver", den, pden), "water": water}
    return {"brief": brief, "todo": [{"id": i["id"], "label": i["label"]} for i in items[:3]]}


def write() -> Path:
    OUT.write_text(json.dumps(build(), indent=1) + "\n")
    return OUT


if __name__ == "__main__":
    print(write())
