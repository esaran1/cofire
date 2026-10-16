"""FastAPI app. Serves precomputed forecasts; never runs models at request time."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

from cofire.model.config import get_settings
from cofire.model.uncertainty.status import classify, pool_from_artifacts
from cofire.ship.ember_zones import ZONES as EMBER_ZONES
from cofire.ship.ember_zones import score as ember_score

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
    """A stored player pick: the device, cell, issue and horizon, and the drought category and
    fire-spread band chosen, with when it was made.
    """
    id: str = SQLField(default_factory=lambda: uuid4().hex, primary_key=True)
    device_id: str
    cell_id: str
    horizon: int
    drought_category: int
    fire_band: str
    issue: str
    created_at: str = SQLField(default_factory=lambda: datetime.now(UTC).isoformat())


class ObservationRow(SQLModel, table=True):
    """A stored ground report: the device, its location and report type, an optional note and photo
    path, and when it was filed.
    """
    id: str = SQLField(default_factory=lambda: uuid4().hex, primary_key=True)
    device_id: str
    lat: float
    lon: float
    obs_type: str
    note: str = ""
    photo_path: str = ""
    created_at: str = SQLField(default_factory=lambda: datetime.now(UTC).isoformat())


class EmberRow(SQLModel, table=True):
    """A device's saved Ember checklist: the zone it last saved and its ticked items as JSON."""
    device_id: str = SQLField(primary_key=True)
    zone: str = "wui"
    state_json: str = "{}"


class PredictionIn(BaseModel):
    """The body of a pick: device, cell, horizon (2, 4 or 8 weeks), drought category 0 to 4,
    fire-spread band, and the issue, which defaults to the latest.
    """
    device_id: str
    cell_id: str
    horizon: int
    drought_category: int = Field(ge=0, le=4)
    fire_band: str
    issue: str | None = None

    @field_validator("horizon")
    @classmethod
    def _horizon(cls, v: int) -> int:
        if v not in (2, 4, 8):
            raise ValueError("horizon must be 2, 4 or 8")
        return v


class ObservationIn(BaseModel):
    """The body of a ground report: device, latitude and longitude, report type, and an optional
    note and photo path.
    """
    device_id: str
    lat: float
    lon: float
    type: str
    note: str = ""
    photo_path: str = ""


class EmberIn(BaseModel):
    """The body of an Ember save: device, zone, and the ticked state of each item by id."""
    device_id: str
    zone: str
    state: dict[str, bool]


OBS_TYPES = {"stock_tank_dry", "lawn_crispy", "creek_low", "soil_cracked", "vegetation_green"}
FIRE_BANDS = {"low", "moderate", "high", "very_high"}
# Band edges on the dryness scale (the ERC percentile for the week, 50 typical).
# The same edges as app/lib/options.ts; tests/test_api.py pins the two together.
FIRE_BAND_EDGES = (("low", 0.0, 50.0), ("moderate", 50.0, 80.0), ("high", 80.0, 90.0), ("very_high", 90.0, 101.0))


def fire_band_for(value: float) -> str:
    """The fire-spread band (low, moderate, high or very_high) for a value on the dryness scale, by
    FIRE_BAND_EDGES; a value outside every band reads as very_high.
    """
    for name, lo, hi in FIRE_BAND_EDGES:
        if lo <= value < hi:
            return name
    return "very_high"


def score_pick(pick: dict[str, Any], cells: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """A player's pick against what happened, once the target week is in.

    The target week is the pick's issue plus its horizon. What happened is the
    cell's own record for that week: its USDM category and its dryness
    percentile, the two quantities the forecasts are about. Only the player is
    scored. The model's call is never compared with 2026 outcomes: 2026 is the
    sealed test year, and scoring the model against it would be another look.
    """
    target = (date.fromisoformat(str(pick["issue"])) + timedelta(weeks=int(pick["horizon"]))).isoformat()
    out = {**pick, "target_week": target, "status": "pending"}
    cell = cells.get((str(pick["cell_id"]), target))
    if cell is None or cell.get("usdm") is None or cell.get("erc_pct") is None:
        return out
    actual_cat = int(round(float(cell["usdm"])))
    actual_band = fire_band_for(float(cell["erc_pct"]))
    drought_ok = actual_cat == int(pick["drought_category"])
    fire_ok = actual_band == str(pick["fire_band"])
    return out | {
        "status": "scored", "actual_category": actual_cat, "actual_band": actual_band,
        "actual_dryness": round(float(cell["erc_pct"]), 1),
        "drought_correct": drought_ok, "fire_correct": fire_ok, "points": int(drought_ok) + int(fire_ok),
    }


def _cells_by_key() -> dict[tuple[str, str], dict[str, Any]]:
    """Every cell record by (cell, issue week), for scoring."""
    index = load_index()
    key = f"{len(index.get('cells', []))}:{index.get('issues', [''])[-1] if index.get('issues') else ''}"
    if _SCORE_CACHE.get("key") != key:
        _SCORE_CACHE.clear()
        _SCORE_CACHE["key"] = key
        _SCORE_CACHE["cells"] = {(c["cell_id"], c["issue"]): c for c in index.get("cells", [])}
    cells: dict[tuple[str, str], dict[str, Any]] = _SCORE_CACHE["cells"]
    return cells


_SCORE_CACHE: dict[str, Any] = {}

SQLModel.metadata.create_all(engine)


def _rate_limit(device_id: str, limit: int = 30) -> None:
    now = datetime.now(UTC).timestamp()
    hits = [t for t in _WRITE_HITS[device_id] if now - t < 60]
    if len(hits) >= limit:
        raise HTTPException(429, "rate limit")
    hits.append(now)
    _WRITE_HITS[device_id] = hits


# `make demo` runs from a committed fixture set with no pipeline run and no
# network (COFIRE_DEMO=1). Otherwise the real artifacts are served when built,
# and the fixture is the fallback, so a fresh clone still serves real numbers.
# Anchored to the repo root (three levels up from this file), not the process
# cwd: `make demo` and `uvicorn` are started from different directories, and a
# relative path silently fell through to the test fixture instead.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = Path(os.environ.get("COFIRE_DEMO_DIR") or (_REPO_ROOT / "demo"))


# A report within this distance of a forecast cell centre is attached to that
# cell. gridMET cells are 1/24 degree, so this is about one and a half cells.
OBS_ATTACH_DEG = 0.06


def art_path(rel: str) -> Path:
    """Artifact path: the real artifacts when built, else the committed demo fixture.

    `make demo` sets COFIRE_DEMO=1 to serve the fixture even where artifacts
    exist. This used to prefer the fixture always, so a local run showed the
    fixture's two issues instead of every issue the export holds.
    """
    demo = DEMO_ROOT / "artifacts" / rel
    real = settings.artifacts_dir / rel
    if os.environ.get("COFIRE_DEMO") == "1" and demo.exists():
        return demo
    return real if real.exists() else demo


_INDEX_CACHE: dict[str, Any] = {}


def load_index() -> dict[str, Any]:
    """Every cell and issue, rebuilt from the per-domain bundles when present.

    Cached on the bundle index's modification time, so a refresh is picked up
    without a restart and a request never re-reads every bundle.
    """
    bundles = art_path("ship/domains/index.json")
    if bundles.exists():
        key = f"{bundles}:{bundles.stat().st_mtime_ns}"
        if key not in _INDEX_CACHE:
            from cofire.ship.bundles import legacy_cells

            _INDEX_CACHE.clear()
            _INDEX_CACHE[key] = legacy_cells(bundles.parent)
        cached: dict[str, Any] = _INDEX_CACHE[key]
        return cached
    path = art_path("forecast_index.json")
    fixture = Path("tests/fixtures/forecast_index.json")
    if path.exists():
        idx: dict[str, Any] = json.loads(path.read_text())
        return idx
    if fixture.exists():
        fx: dict[str, Any] = json.loads(fixture.read_text())
        return fx
    return {"issues": [], "cells": [], "resolution_m": 4000, "shipping_arm": "unknown", "resolution_note": "no forecast exported"}


def nearest_cell(lat: float, lon: float, index: dict[str, Any], issue: str | None = None) -> dict[str, Any] | None:
    """The index cell nearest a point, in the given issue or the latest one."""
    cells: list[dict[str, Any]] = index.get("cells") or []
    # With no issue named, answer with the latest one. Every issue has a cell at
    # every location, so the unfiltered minimum used to return whichever issue
    # came first in the index, which was the oldest.
    if not issue and index.get("issues"):
        issue = max(index["issues"])
    if issue:
        cells = [c for c in cells if c.get("issue") == issue]
    if not cells:
        return None
    return min(cells, key=lambda c: (float(c["lat"]) - lat) ** 2 + (float(c["lon"]) - lon) ** 2)


@app.on_event("startup")
def startup() -> None:
    """Create the database tables at startup if they do not exist yet."""
    SQLModel.metadata.create_all(engine)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check; always answers with status ok."""
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict[str, Any]:
    """App metadata: the shipping configuration, resolution, disclaimer, data manifest, hashes, the
    verdict from STATUS.md, hindcast looks, issue dates, and a map camera fitted to the exported
    grid.
    """
    index = load_index()
    man = DEMO_ROOT / "MANIFEST.json"
    if not man.exists():
        man = settings.data_dir / "MANIFEST.json"
    manifest = json.loads(man.read_text()) if man.exists() else {"sources": []}
    metrics_path = art_path("metrics.json")
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    resolution = metrics.get("resolution_m") or index.get("resolution_m", 4000)
    status_path = Path("STATUS.md")
    verdict = "unknown"
    if status_path.exists():
        head = status_path.read_text().splitlines()[0] if status_path.read_text() else ""
        if ":" in head:
            verdict = head.split(":", 1)[1].strip()
    return {
        "shipping_arm": "configuration A: Markov transitions for drought, damped logistic for fire-spread, damped regression for the ERC percentile",
        "shipping_arm_basis": "chosen on leave-one-drought-year-out folds; frozen at FREEZE_COMMIT (docs/DECISIONS.md)",
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
    """The three-state uncertainty status for an issue (the latest when none is given), from the
    calibration pool on disk; uncalibrated when there is no pool.
    """
    return _regime_status(issue)


_DOMAIN_RE = re.compile(r"^[a-z_]{1,40}$")
_ISSUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@app.get("/domains")
def domains_index() -> Any:
    """The forecast domains, Denver first, with the issues each bundle covers."""
    path = art_path("ship/domains/index.json")
    if not path.exists():
        raise HTTPException(404, "no domain bundles exported")
    return json.loads(path.read_text())


@app.get("/domains/{domain}/{issue}")
def domain_bundle(domain: str, issue: str) -> Any:
    """One domain's forecast for one issue: cells, decisions, and source watersheds."""
    if not _DOMAIN_RE.match(domain) or not _ISSUE_RE.match(issue):
        raise HTTPException(400, "bad domain or issue")
    path = art_path(f"ship/domains/{domain}/{issue}.json")
    if not path.exists():
        raise HTTPException(404, f"no forecast for {domain} on {issue}")
    return json.loads(path.read_text())


@app.get("/explain/{domain}")
def domain_explain(domain: str) -> Any:
    """The tables behind a domain's live probabilities (cofire/v13/explain.py)."""
    if not _DOMAIN_RE.match(domain):
        raise HTTPException(400, "bad domain")
    path = Path("artifacts/v13/explain") / f"{domain}.json"
    if not path.exists():
        raise HTTPException(404, f"no explanation tables for {domain}")
    return json.loads(path.read_text())


_OPEN_RE = re.compile(r"^(?:issues/)?[a-zA-Z0-9_.-]{1,80}$")


@app.get("/open/{name:path}")
def open_data_file(name: str) -> Any:
    """The open data files (cofire/v13/open_data.py), built from the bundles on first request."""
    from fastapi.responses import FileResponse

    from cofire.v13 import open_data

    if not _OPEN_RE.match(name) or ".." in name:
        raise HTTPException(400, "bad file name")
    src = art_path("ship/domains")
    # Built once into a cache that is never committed, even when serving the demo fixture.
    root = settings.artifacts_dir / "ship" / ("open_demo" if DEMO_ROOT in src.parents else "open")
    if not (root / "index.json").exists():
        open_data.build(root, src, strict=False)
    path = root / name
    if not path.is_file():
        raise HTTPException(404, f"no open data file {name}")
    return FileResponse(path)


@app.get("/forecast/issues")
def issues() -> dict[str, Any]:
    """Every forecast issue date the index holds."""
    index = load_index()
    return {"issues": index.get("issues", [])}


@app.get("/forecast")
def forecast(
    lat: float = Query(...), lon: float = Query(...), issue: str | None = None, domain: str | None = None
) -> dict[str, Any]:
    """The forecast for the cell nearest a point, in the given issue (the latest by default) and
    optionally one domain, with its uncertainty status attached; 404 when no cell matches.
    """
    index = load_index()
    if domain:
        index = {**index, "cells": [c for c in index.get("cells", []) if c.get("domain") == domain]}
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
    """One issue's cells as a GeoJSON FeatureCollection of points, each valued by the forecast ERC
    percentile at the horizon for fire, otherwise by the percent chance of D2 or worse.
    """
    index = load_index()
    cells = [c for c in index.get("cells", []) if c.get("issue") == issue]
    feats = []
    for c in cells:
        hz = (c.get("horizons") or {}).get(str(horizon), {})
        # Fire: the forecast ERC percentile. Drought: the chance, in percent, of
        # D2 or worse at the horizon. The same values the map colours.
        if variable == "fire":
            value = hz.get("point")
        else:
            p = ((c.get("targets") or {}).get(f"d_ge2_h{horizon}") or {}).get("p")
            value = None if p is None else round(float(p) * 100, 2)
        feats.append(
            {
                "type": "Feature",
                "properties": {"cell_id": c["cell_id"], "domain": c.get("domain"), "value": value},
                "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            }
        )
    return {"type": "FeatureCollection", "features": feats, "resolution_m": index.get("resolution_m", 4000)}


@app.get("/overlay/{issue}/{horizon}/{variable}.png")
def overlay(issue: str, horizon: int, variable: str) -> FileResponse:
    """The pre-rendered PNG overlay for an issue, horizon and variable; 404 when it was not
    rendered.
    """
    path = settings.artifacts_dir / "overlays" / f"{issue}_{horizon}_{variable}.png"
    if not path.exists():
        raise HTTPException(404, "overlay not found")
    return FileResponse(path, media_type="image/png")


@app.get("/overlay/{issue}/{horizon}/{variable}.json")
def overlay_bounds(issue: str, horizon: int, variable: str) -> Any:
    """The JSON bounds that go with a pre-rendered overlay; 404 when missing."""
    path = settings.artifacts_dir / "overlays" / f"{issue}_{horizon}_{variable}.json"
    if not path.exists():
        raise HTTPException(404, "overlay bounds not found")
    return json.loads(path.read_text())


@app.get("/tiles/{issue}/{horizon}/{variable}/{z}/{x}/{y}.png")
def tiles(issue: str, horizon: int, variable: str, z: int, x: int, y: int) -> FileResponse:
    """A map tile request, answered with the whole pre-rendered overlay PNG; the tile coordinates
    are ignored.
    """
    # Demo: fall back to the pre-rendered overlay (4 km cells; no sub-field implication).
    del z, x, y
    return overlay(issue, horizon, variable)


@app.get("/hindcast/summary")
def hindcast_summary() -> dict[str, Any]:
    """The hindcast summary: the coverage plot link, the comparison text, the overall coverage rows
    per split, method and horizon, the nominal level, and the latest look index with its
    contamination flag and note.
    """
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
    """The coverage plot PNG, the 2026 uncertainty plot if present, else the hindcast one; 404 when
    neither exists.
    """
    path = art_path("uncertainty/coverage_2026.png")
    if not path.exists():
        path = art_path("hindcast/coverage.png")
    if not path.exists():
        raise HTTPException(404, "coverage plot not generated")
    return FileResponse(path, media_type="image/png")


@app.get("/hindcast/fires")
def hindcast_fires() -> Any:
    """The hindcast fire table with its control ranks, the number of fires inside the domain, the
    1000 acre threshold, and a note on how to read it.
    """
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
    """Store a player's pick for a cell and issue (the latest by default) and return its id with the
    model's call for that cell locked beside it. Rate limited; 400 for an unknown band, 404 for a
    cell with no forecast in that issue.
    """
    _rate_limit(body.device_id)
    if body.fire_band not in FIRE_BANDS:
        raise HTTPException(400, "fire_band must be low|moderate|high|very_high")
    index = load_index()
    issue = body.issue or (index.get("issues") or [""])[-1]
    if not any(c["cell_id"] == body.cell_id and c["issue"] == issue for c in index.get("cells", [])):
        raise HTTPException(404, f"no forecast cell {body.cell_id} for {issue}")
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
    # No match locks nothing. This used to fall back to the cell nearest (0, 0),
    # which locked an arbitrary forecast against the pick.
    locked = None
    for c in index.get("cells", []):
        if c["cell_id"] == body.cell_id and c["issue"] == issue:
            locked = c
            break
    hz = dict((locked or {}).get("horizons", {}).get(str(body.horizon), {}))
    hz.update(_likely_category(locked, body.horizon))
    return {"id": pid, "locked_model": hz, "issue": issue}


def _likely_category(cell: dict[str, Any] | None, horizon: int) -> dict[str, Any]:
    """The drought category the model makes most likely at the horizon.

    The shipped drought model gives a full forecast over the next category:
    easing by one, staying, worsening by one, worsening by two or more, all
    from the current category. Its most likely outcome is the model's call to
    set beside the player's, and it always has one. The chance is reported only
    when every probability behind it passed its check; otherwise the call is
    shown without a number, as the Place Card does. Categories run 0 (none or
    D0) to 4; moves that cannot happen from the current category are zero.
    """
    empty: dict[str, Any] = {"drought_now": None, "drought_likely": None, "drought_likely_p": None}
    if not cell or cell.get("usdm") is None:
        return empty
    shown = cell.get("targets", {})
    model = cell.get("model") or {}
    names = ("d_improve1", "d_nochange", "d_intensify1", "d_intensify2")
    now = int(round(float(cell["usdm"])))
    impossible = {"d_improve1": now <= 0, "d_intensify1": now >= 4, "d_intensify2": now >= 3}

    def value(n: str, source: dict[str, Any]) -> float | None:
        if impossible.get(n):
            return 0.0
        v = source.get(f"{n}_h{horizon}")
        v = v.get("p") if isinstance(v, dict) else v
        return None if v is None else float(v)

    raw = {n: value(n, model) for n in names}
    if any(v is None for v in raw.values()):
        # No model numbers in this payload (an older bundle): use what is shown.
        raw = {n: value(n, shown) for n in names}
    if any(v is None for v in raw.values()):
        return empty | {"drought_now": now}
    p = {n: float(v) for n, v in raw.items() if v is not None}
    options = {
        max(now - 1, 0): p["d_improve1"] if now > 0 else 0.0,
        now: p["d_nochange"],
        min(now + 1, 4): max(p["d_intensify1"] - p["d_intensify2"], 0.0),
        min(now + 2, 4): p["d_intensify2"],
    }
    cat, chance = max(options.items(), key=lambda kv: kv[1])
    checked = all(impossible.get(n) or (shown.get(f"{n}_h{horizon}") or {}).get("p") is not None for n in names)
    out: dict[str, Any] = {"drought_now": now, "drought_likely": cat, "drought_likely_p": None}
    if checked:
        out["drought_likely_p"] = round(chance, 4)
    else:
        out["drought_note"] = "some of the model's drought odds here could not be checked, so its chance is not shown"
    return out


@app.get("/predictions/me")
def predictions_me(device_id: str) -> list[dict[str, Any]]:
    """A device's picks, newest first, each scored once its target week is in."""
    with Session(engine) as session:
        rows = session.exec(select(PredictionRow).where(PredictionRow.device_id == device_id)).all()
        picks = [r.model_dump() for r in rows]
    cells = _cells_by_key()
    return sorted((score_pick(p, cells) for p in picks), key=lambda p: str(p["created_at"]), reverse=True)


@app.get("/leaderboard")
def leaderboard(county: str | None = None) -> list[dict[str, Any]]:
    """Players ranked by points from scored picks, then by picks scored and made."""
    del county
    with Session(engine) as session:
        rows = session.exec(select(PredictionRow)).all()
        picks = [r.model_dump() for r in rows]
    cells = _cells_by_key()
    board: dict[str, dict[str, int]] = defaultdict(lambda: {"picks": 0, "scored": 0, "points": 0})
    for p in picks:
        s = score_pick(p, cells)
        b = board[str(p["device_id"])]
        b["picks"] += 1
        if s["status"] == "scored":
            b["scored"] += 1
            b["points"] += int(s["points"])
    ranked = sorted(board.items(), key=lambda kv: (-kv[1]["points"], -kv[1]["scored"], -kv[1]["picks"]))
    return [{"device_id": k[:8], **v} for k, v in ranked]


@app.post("/observations")
def post_observation(body: ObservationIn) -> dict[str, Any]:
    """Store a ground report and return its id and the forecast cell it was logged against, if one
    is within reach; the report never changes the forecast. Rate limited; 400 for an unknown report
    type.
    """
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
    """Every stored ground report, optionally only those inside a bbox given as
    west,south,east,north.
    """
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
    """The Ember checklist for a zone, scored with nothing ticked; 400 for an unknown zone."""
    if zone not in EMBER_ZONES:
        raise HTTPException(400, f"zone must be one of {'|'.join(EMBER_ZONES)}")
    return ember_score({}, zone)


@app.post("/ember/state")
def ember_state(body: EmberIn) -> dict[str, Any]:
    """Save a device's ticked Ember items for a zone and return the checklist scored against them.
    Rate limited; 400 for an unknown zone.
    """
    if body.zone not in EMBER_ZONES:
        raise HTTPException(400, f"zone must be one of {'|'.join(EMBER_ZONES)}")
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
    """A device's saved ticks, scored for the zone asked for.

    This used to answer with the zone the device saved last, whatever zone was
    requested, so switching between the city and wildland-edge lists returned
    the wrong list.
    """
    if zone not in EMBER_ZONES:
        raise HTTPException(400, f"zone must be one of {'|'.join(EMBER_ZONES)}")
    with Session(engine) as session:
        row = session.get(EmberRow, device_id)
    state = json.loads(row.state_json) if row else {}
    return ember_score(state, zone)


@app.get("/manifest")
def manifest() -> Any:
    """The data source manifest from the data directory, or an empty source list when there is none.
    """
    path = settings.data_dir / "MANIFEST.json"
    if not path.exists():
        return {"sources": []}
    return json.loads(path.read_text())
