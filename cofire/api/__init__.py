"""FastAPI app. Serves precomputed forecasts; never runs models at request time."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

from cofire.model.config import get_settings
from cofire.model.ember import score as ember_score
from cofire.model.uncertainty.status import classify, pool_from_artifacts

settings = get_settings()
DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("COFIRE_DATABASE_URL") or str(settings.database_url)
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})

app = FastAPI(title="COFIRE", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_WRITE_HITS: dict[str, list[float]] = defaultdict(list)


class PredictionRow(SQLModel, table=True):
    id: str = SQLField(default_factory=lambda: uuid4().hex, primary_key=True)
    device_id: str
    cell_id: str
    horizon: int
    drought_category: int
    fire_band: str
    issue: str
    created_at: str = SQLField(default_factory=lambda: datetime.now(UTC).isoformat())


class ObservationRow(SQLModel, table=True):
    id: str = SQLField(default_factory=lambda: uuid4().hex, primary_key=True)
    device_id: str
    lat: float
    lon: float
    obs_type: str
    note: str = ""
    photo_path: str = ""
    created_at: str = SQLField(default_factory=lambda: datetime.now(UTC).isoformat())


class EmberRow(SQLModel, table=True):
    device_id: str = SQLField(primary_key=True)
    zone: str = "wui"
    state_json: str = "{}"


class PredictionIn(BaseModel):
    device_id: str
    cell_id: str
    horizon: int
    drought_category: int = Field(ge=0, le=4)
    fire_band: str
    issue: str | None = None


class ObservationIn(BaseModel):
    device_id: str
    lat: float
    lon: float
    type: str
    note: str = ""
    photo_path: str = ""


class EmberIn(BaseModel):
    device_id: str
    zone: str
    state: dict[str, bool]


OBS_TYPES = {"stock_tank_dry", "lawn_crispy", "creek_low", "soil_cracked", "vegetation_green"}
FIRE_BANDS = {"low", "moderate", "high", "very_high"}

SQLModel.metadata.create_all(engine)


def _rate_limit(device_id: str, limit: int = 30) -> None:
    now = datetime.now(UTC).timestamp()
    hits = [t for t in _WRITE_HITS[device_id] if now - t < 60]
    if len(hits) >= limit:
        raise HTTPException(429, "rate limit")
    hits.append(now)
    _WRITE_HITS[device_id] = hits


# `make demo` runs from a committed fixture set with no pipeline run and no
# network. When demo/ exists it wins, so a fresh clone serves real numbers.
# Anchored to the repo root (three levels up from this file), not the process
# cwd: `make demo` and `uvicorn` are started from different directories, and a
# relative path silently fell through to the test fixture instead.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = Path(os.environ.get("COFIRE_DEMO_DIR") or (_REPO_ROOT / "demo"))


# A report within this distance of a forecast cell centre is attached to that
# cell. gridMET cells are 1/24 degree, so this is about one and a half cells.
OBS_ATTACH_DEG = 0.06


def art_path(rel: str) -> Path:
    """Artifact path, preferring the committed demo fixture when present."""
    demo = DEMO_ROOT / "artifacts" / rel
    if demo.exists():
        return demo
    return settings.artifacts_dir / rel


def load_index() -> dict[str, Any]:
    path = art_path("forecast_index.json")
    fixture = Path("tests/fixtures/forecast_index.json")
    if path.exists():
        return json.loads(path.read_text())
    if fixture.exists():
        return json.loads(fixture.read_text())
    return {"issues": [], "cells": [], "resolution_m": 4000, "shipping_arm": "unknown", "resolution_note": "no forecast exported"}


def nearest_cell(lat: float, lon: float, index: dict[str, Any], issue: str | None = None) -> dict[str, Any] | None:
    cells = index.get("cells") or []
    if issue:
        cells = [c for c in cells if c.get("issue") == issue]
    if not cells:
        return None
    return min(cells, key=lambda c: (float(c["lat"]) - lat) ** 2 + (float(c["lon"]) - lon) ** 2)


@app.on_event("startup")
def startup() -> None:
    SQLModel.metadata.create_all(engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict[str, Any]:
    index = load_index()
    man = DEMO_ROOT / "MANIFEST.json"
    if not man.exists():
        man = settings.data_dir / "MANIFEST.json"
    manifest = json.loads(man.read_text()) if man.exists() else {"sources": []}
    metrics_path = art_path("metrics.json")
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    shipping = metrics.get("shipping_arm") or index.get("shipping_arm")
    resolution = metrics.get("resolution_m") or index.get("resolution_m", 4000)
    status_path = Path("STATUS.md")
    verdict = "unknown"
    if status_path.exists():
        head = status_path.read_text().splitlines()[0] if status_path.read_text() else ""
        if ":" in head:
            verdict = head.split(":", 1)[1].strip()
    return {
        "shipping_arm": shipping,
        "shipping_arm_basis": "lowest validation ERC-percentile MAE on the 2023 split; tie-break drought MAE",
        "resolution_m": resolution,
        "resolution_note": index.get("resolution_note")
        or "gridMET native ~4 km cells. Downscaling to 10–30 m is off.",
        "disclaimer": "COFIRE forecasts drought severity and conditions that allow fires to spread. It does not predict ignitions or where a fire will occur.",
        "manifest": manifest,
        "manifest_hash": metrics.get("manifest_hash"),
        "git_sha": metrics.get("git_sha"),
        "status": verdict,
        "hindcast_looks": metrics.get("hindcast_looks", []),
        "issue_dates": index.get("issues", []),
        # Camera for the map, derived from the exported grid so the view follows
        # the active dev subset instead of a hardcoded location.
        **_grid_camera(index),
    }


def _grid_camera(index: dict[str, Any]) -> dict[str, Any]:
    cells = index.get("cells") or []
    if not cells:
        return {}
    lats = [float(c["lat"]) for c in cells[:20000]]
    lons = [float(c["lon"]) for c in cells[:20000]]
    span = max(max(lats) - min(lats), max(lons) - min(lons))
    zoom = 9.0 if span < 0.8 else 8.3 if span < 1.6 else 7.0
    return {
        "center": [(min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2],
        "zoom": zoom,
    }


def _regime_status(issue: str | None = None) -> dict[str, Any]:
    """Three-state uncertainty status for an issue, from calibration diagnostics."""
    pool_root = DEMO_ROOT / "artifacts" if (DEMO_ROOT / "artifacts" / "uncertainty" / "regime_pool.json").exists() else settings.artifacts_dir
    pool = pool_from_artifacts(pool_root)
    if pool is None:
        return {
            "status": "uncalibrated",
            "reason": "no calibration pool on disk; run the multi-regime calibration",
            "available": False,
        }
    index = load_index()
    iss = issue or (index.get("issues") or [None])[-1]
    current = None
    if iss:
        vals = [
            (c.get("horizons") or {}).get("4", {}).get("drought_point")
            for c in index.get("cells", [])
            if c.get("issue") == iss
        ]
        vals = [v for v in vals if isinstance(v, int | float)]
        if vals:
            current = sum(vals) / len(vals)
    if current is None:
        current = pool.usdm_mean
    pos = classify(float(current), pool)
    return {
        **pos.to_dict(),
        "issue": iss,
        "pool_years": pool.pool_years,
        "pool_usdm_min": pool.usdm_min,
        "available": True,
        "show_interval": pos.status != "uncalibrated",
    }


@app.get("/uncertainty/status")
def uncertainty_status(issue: str | None = None) -> dict[str, Any]:
    return _regime_status(issue)


@app.get("/forecast/issues")
def issues() -> dict[str, Any]:
    index = load_index()
    return {"issues": index.get("issues", [])}


@app.get("/forecast")
def forecast(lat: float = Query(...), lon: float = Query(...), issue: str | None = None) -> dict[str, Any]:
    index = load_index()
    cell = nearest_cell(lat, lon, index, issue)
    if cell is None:
        raise HTTPException(404, "no forecast for this location")
    # Attach the uncertainty status so the Place Card can suppress or caveat the
    # interval without a second round trip.
    out = dict(cell)
    out["uncertainty"] = _regime_status(cell.get("issue") or issue)
    return out


@app.get("/forecast/grid")
def forecast_grid(issue: str, horizon: int = 4, variable: str = "fire") -> dict[str, Any]:
    index = load_index()
    cells = [c for c in index.get("cells", []) if c.get("issue") == issue]
    feats = []
    for c in cells:
        hz = (c.get("horizons") or {}).get(str(horizon), {})
        value = hz.get("fire_index") if variable == "fire" else hz.get("drought_point")
        conf = hz.get("confidence", 0.5)
        feats.append(
            {
                "type": "Feature",
                "properties": {"cell_id": c["cell_id"], "value": value, "confidence": conf},
                "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            }
        )
    return {"type": "FeatureCollection", "features": feats, "resolution_m": index.get("resolution_m", 4000)}


@app.get("/overlay/{issue}/{horizon}/{variable}.png")
def overlay(issue: str, horizon: int, variable: str) -> FileResponse:
    path = settings.artifacts_dir / "overlays" / f"{issue}_{horizon}_{variable}.png"
    if not path.exists():
        raise HTTPException(404, "overlay not found")
    return FileResponse(path, media_type="image/png")


@app.get("/overlay/{issue}/{horizon}/{variable}.json")
def overlay_bounds(issue: str, horizon: int, variable: str) -> Any:
    path = settings.artifacts_dir / "overlays" / f"{issue}_{horizon}_{variable}.json"
    if not path.exists():
        raise HTTPException(404, "overlay bounds not found")
    return json.loads(path.read_text())


@app.get("/tiles/{issue}/{horizon}/{variable}/{z}/{x}/{y}.png")
def tiles(issue: str, horizon: int, variable: str, z: int, x: int, y: int) -> FileResponse:
    # Demo: fall back to the pre-rendered overlay (4 km cells; no sub-field implication).
    del z, x, y
    return overlay(issue, horizon, variable)


@app.get("/hindcast/summary")
def hindcast_summary() -> dict[str, Any]:
    cov = art_path("uncertainty/coverage_2026.png")
    cmp = art_path("uncertainty/comparison.md")
    cmp_json = art_path("uncertainty/comparison.json")
    metrics_path = art_path("metrics.json")
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    looks = metrics.get("hindcast_looks", [])
    coverage: list[dict[str, Any]] = []
    nominal = 0.90
    if cmp_json.exists():
        raw = json.loads(cmp_json.read_text())
        nominal = raw.get("nominal", 0.90)
        for split in ("calibrate", "hindcast"):
            for method, block in (raw.get(split) or {}).items():
                for row in block.get("rows", []):
                    if row.get("stratum") != "overall":
                        continue
                    coverage.append(
                        {
                            "split": split,
                            "method": method,
                            "horizon": row.get("horizon"),
                            "coverage": row.get("coverage"),
                            "width": row.get("width"),
                            "n": row.get("n"),
                        }
                    )
    return {
        "coverage_plot": "/hindcast/coverage.png" if cov.exists() else None,
        "comparison": cmp.read_text() if cmp.exists() else "",
        "coverage_rows": coverage,
        "nominal": nominal,
        "may1_issue": "2026-05-05",
        "look_index": looks[-1]["look_index"] if looks else 0,
        "contaminated": bool(looks) and looks[-1]["look_index"] > 1,
        "contamination_note": (
            "Skill vs persistence was re-scored after a merge_pred bug that scored stored baseline "
            "hats as the model. Hyperparameters were not changed, but this is a repeat look at the "
            "locked 2026 holdout and is reported as contaminated."
        ),
    }


@app.get("/hindcast/coverage.png")
def coverage_png() -> FileResponse:
    path = art_path("uncertainty/coverage_2026.png")
    if not path.exists():
        path = art_path("hindcast/coverage.png")
    if not path.exists():
        raise HTTPException(404, "coverage plot not generated")
    return FileResponse(path, media_type="image/png")


@app.get("/hindcast/fires")
def hindcast_fires() -> Any:
    path = art_path("hindcast/fires.json")
    ctrl = art_path("hindcast/control.json")
    fires = json.loads(path.read_text()) if path.exists() else []
    control = json.loads(ctrl.read_text()) if ctrl.exists() else {}
    in_domain = [f for f in fires if f.get("in_domain")]
    return {
        "fires": fires,
        "control": control,
        "n_in_domain": len(in_domain),
        "threshold_acres": 1000,
        "note": (
            "Ranks for fires outside the current domain are nearest-cell only. With no in-domain "
            "fires this table is not evidence of skill; compare against the control mean rank."
        ),
    }


@app.post("/predictions")
def post_prediction(body: PredictionIn) -> dict[str, Any]:
    _rate_limit(body.device_id)
    if body.fire_band not in FIRE_BANDS:
        raise HTTPException(400, "fire_band must be low|moderate|high|very_high")
    index = load_index()
    issue = body.issue or (index.get("issues") or [""])[-1]
    row = PredictionRow(
        device_id=body.device_id,
        cell_id=body.cell_id,
        horizon=body.horizon,
        drought_category=body.drought_category,
        fire_band=body.fire_band,
        issue=issue,
    )
    pid = row.id
    with Session(engine) as session:
        session.add(row)
        session.commit()
    locked = nearest_cell(0, 0, index, issue)
    for c in index.get("cells", []):
        if c["cell_id"] == body.cell_id and c["issue"] == issue:
            locked = c
            break
    hz = (locked or {}).get("horizons", {}).get(str(body.horizon), {})
    return {"id": pid, "locked_model": hz, "issue": issue}


@app.get("/predictions/me")
def predictions_me(device_id: str) -> list[dict[str, Any]]:
    with Session(engine) as session:
        rows = session.exec(select(PredictionRow).where(PredictionRow.device_id == device_id)).all()
        return [r.model_dump() for r in rows]


@app.get("/leaderboard")
def leaderboard(county: str | None = None) -> list[dict[str, Any]]:
    del county
    with Session(engine) as session:
        rows = session.exec(select(PredictionRow)).all()
    scores: dict[str, int] = defaultdict(int)
    for r in rows:
        scores[r.device_id] += 1
    return [{"device_id": k[:8], "picks": v} for k, v in sorted(scores.items(), key=lambda kv: -kv[1])]


@app.post("/observations")
def post_observation(body: ObservationIn) -> dict[str, Any]:
    _rate_limit(body.device_id)
    if body.type not in OBS_TYPES:
        raise HTTPException(400, f"type must be one of {sorted(OBS_TYPES)}")
    row = ObservationRow(
        device_id=body.device_id,
        lat=body.lat,
        lon=body.lon,
        obs_type=body.type,
        note=body.note,
        photo_path=body.photo_path,
    )
    oid = row.id
    with Session(engine) as session:
        session.add(row)
        session.commit()
    # Say what actually happened to the report, and nothing more.
    #
    # This used to return a "nudge" of +0.05 drought and +1.2 fire, hardcoded,
    # labelled "documented feature weight x cached model delta", and the Observe
    # page displayed it as the report's effect on the forecast. Nothing computed
    # it. The shipped configuration never reads ground reports, so there is no
    # effect to report, and inventing one was a false claim to every user who
    # filed. The report is logged against its nearest forecast cell, and the
    # response says which one, or that it fell outside both forecast areas.
    index = load_index()
    cell = nearest_cell(body.lat, body.lon, index)
    attached = None
    if cell is not None:
        dist = ((float(cell["lat"]) - body.lat) ** 2 + (float(cell["lon"]) - body.lon) ** 2) ** 0.5
        # Within one cell's width of a forecast cell centre counts as inside.
        if dist <= OBS_ATTACH_DEG:
            attached = {
                "cell_id": cell["cell_id"],
                "lat": cell["lat"],
                "lon": cell["lon"],
                "domain": cell.get("domain"),
            }
    return {"id": oid, "nudge": None, "cell": attached, "changes_forecast": False}


@app.get("/observations")
def get_observations(bbox: str | None = None) -> list[dict[str, Any]]:
    with Session(engine) as session:
        rows = session.exec(select(ObservationRow)).all()
        out = [r.model_dump() for r in rows]
    out = [{**r, "type": r.get("obs_type", "")} for r in out]
    if bbox:
        west, south, east, north = [float(x) for x in bbox.split(",")]
        out = [r for r in out if west <= r["lon"] <= east and south <= r["lat"] <= north]
    return out


@app.get("/ember/checklist")
def ember_checklist(zone: str = "wui") -> dict[str, Any]:
    if zone not in {"urban", "wui"}:
        raise HTTPException(400, "zone must be urban|wui")
    return ember_score({}, zone)


@app.post("/ember/state")
def ember_state(body: EmberIn) -> dict[str, Any]:
    _rate_limit(body.device_id)
    with Session(engine) as session:
        row = session.get(EmberRow, body.device_id) or EmberRow(device_id=body.device_id)
        row.zone = body.zone
        row.state_json = json.dumps(body.state)
        session.add(row)
        session.commit()
    return ember_score(body.state, body.zone)


@app.get("/ember/score")
def get_ember_score(device_id: str, zone: str = "wui") -> dict[str, Any]:
    with Session(engine) as session:
        row = session.get(EmberRow, device_id)
    state = json.loads(row.state_json) if row else {}
    z = row.zone if row else zone
    return ember_score(state, z)


@app.get("/manifest")
def manifest() -> Any:
    path = settings.data_dir / "MANIFEST.json"
    if not path.exists():
        return {"sources": []}
    return json.loads(path.read_text())
