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


def load_index() -> dict[str, Any]:
    path = settings.artifacts_dir / "forecast_index.json"
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
    man = settings.data_dir / "MANIFEST.json"
    manifest = json.loads(man.read_text()) if man.exists() else {"sources": []}
    return {
        "shipping_arm": index.get("shipping_arm"),
        "resolution_m": index.get("resolution_m", 4000),
        "resolution_note": index.get("resolution_note"),
        "disclaimer": "COFIRE forecasts drought severity and conditions that allow fires to spread. It does not predict ignitions or where a fire will occur.",
        "manifest": manifest,
    }


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
    return cell


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
    cov = settings.artifacts_dir / "uncertainty" / "coverage_2026.png"
    cmp = settings.artifacts_dir / "uncertainty" / "comparison.md"
    return {
        "coverage_plot": "/hindcast/coverage.png" if cov.exists() else None,
        "comparison": cmp.read_text() if cmp.exists() else "",
        "may1_issue": "2026-05-05",
    }


@app.get("/hindcast/coverage.png")
def coverage_png() -> FileResponse:
    path = settings.artifacts_dir / "uncertainty" / "coverage_2026.png"
    if not path.exists():
        path = settings.artifacts_dir / "hindcast" / "coverage.png"
    if not path.exists():
        raise HTTPException(404, "coverage plot not generated")
    return FileResponse(path, media_type="image/png")


@app.get("/hindcast/fires")
def hindcast_fires() -> Any:
    path = settings.artifacts_dir / "hindcast" / "fires.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


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
    # Cached what-if: look up precomputed nudge on the nearest cell if present.
    index = load_index()
    cell = nearest_cell(body.lat, body.lon, index)
    nudge = {"delta_drought": 0.05 if body.type != "vegetation_green" else -0.04, "delta_fire": 1.2 if body.type != "vegetation_green" else -0.8, "source": "documented feature weight × cached model delta"}
    if cell and cell.get("nudge"):
        nudge = cell["nudge"].get(body.type, nudge)  # type: ignore[assignment]
    return {"id": oid, "nudge": nudge}


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
