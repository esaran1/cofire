"""Build `forecast_index.json` from the frozen export, carrying rendering state.

The app reads this file and nothing else for Place Cards and the map. Every
number in it comes from `artifacts/ship/forecast_issues.parquet`, and every
number carries the rendering state and reason that the preregistration fixed,
so the app never decides what to show: it reads the decision.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger("cofire.ship.index_build")

EXPORT = Path("artifacts/ship/forecast_issues.parquet")
OUT = Path("artifacts/forecast_index.json")
HORIZONS = (2, 4, 8)


def _clean(v: Any) -> Any:
    """JSON cannot hold NaN. A missing number must read as missing, not as 0."""
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if not np.isfinite(f) else round(f, 6)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return v


def continuous_block(row: pd.Series, h: int) -> dict[str, Any]:
    """The ERC percentile forecast for one horizon, in its rendering state.

    `interval` carries lo and hi; `historical_range` carries the labelled
    climatological range instead and no interval; `uncalibrated` carries
    neither. The point forecast is present in every state, as preregistered.
    """
    state = row.get(f"erc_pct_h{h}_state")
    point = _clean(row.get(f"erc_pct_h{h}_point"))
    out: dict[str, Any] = {
        "point": point,
        "state": state,
        "reason": row.get(f"erc_pct_h{h}_reason"),
    }
    if state == "interval":
        radius = _clean(row.get(f"erc_pct_h{h}_radius"))
        if point is not None and radius is not None:
            out["lo"] = round(max(0.0, point - radius), 6)
            out["hi"] = round(min(100.0, point + radius), 6)
    elif state == "historical_range":
        med = _clean(row.get(f"erc_pct_h{h}_clim_median"))
        width = _clean(row.get(f"erc_pct_h{h}_clim_width"))
        if med is not None and width is not None:
            out["range_lo"] = round(max(0.0, med - width / 2), 6)
            out["range_hi"] = round(min(100.0, med + width / 2), 6)
            out["range_label"] = "historical range for this week of year"
    return out


def target_block(row: pd.Series, target: str) -> dict[str, Any]:
    return {
        "p": _clean(row.get(f"{target}_p")),
        "state": row.get(f"{target}_state"),
        "reason": row.get(f"{target}_reason"),
    }


def build(export: Path = EXPORT) -> dict[str, Any]:
    frame = pd.read_parquet(export)
    frame["time"] = pd.to_datetime(frame["time"])
    frame["issue"] = frame["time"].dt.strftime("%Y-%m-%d")
    targets = sorted(
        c[: -len("_p")] for c in frame.columns if c.endswith("_p")
    )

    cells: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        cells.append(
            {
                "cell_id": str(row["cell_id"]),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "issue": str(row["issue"]),
                "domain": str(row["domain"]),
                "resolution_m": 4000,
                "erc": _clean(row.get("erc")),
                "erc_pct": _clean(row.get("erc_pct")),
                "usdm": _clean(row.get("usdm")),
                "horizons": {str(h): continuous_block(row, h) for h in HORIZONS},
                "targets": {t: target_block(row, t) for t in targets},
            }
        )

    issues = sorted(frame["issue"].unique().tolist())
    return {
        "resolution_m": 4000,
        "resolution_note": (
            "4 km gridMET cells. The displayed value is the cell's own, not an "
            "interpolation to a point."
        ),
        "issues": issues,
        "cells": cells,
        "domains": sorted(frame["domain"].unique().tolist()),
        "targets": targets,
        "configuration": "frozen at FREEZE_COMMIT; see docs/PREREGISTRATION_LOOK3.md",
    }


def write(out: Path = OUT, export: Path = EXPORT) -> Path:
    index = build(export)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index))
    LOGGER.info(
        "%s: %d cells, %d issues, %d targets, %.1f MB",
        out, len(index["cells"]), len(index["issues"]), len(index["targets"]),
        out.stat().st_size / 1e6,
    )
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write())
