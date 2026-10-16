"""Open data (cofire/v13/open_data.py): the files say exactly what the bundles say."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import pytest
from cofire.v13 import open_data

TARGETS = ["d_ge2_h2", "d_ge2_h4", "f_gt97_h8"]


def _bundle(domain: str, issue: str, cells: int) -> dict[str, object]:
    return {
        "domain": domain, "issue": issue, "targets": TARGETS,
        "decisions": {"targets": {"d_ge2_h2": ["probability", "calibrated, reliability 0.0072"],
                                  "d_ge2_h4": ["not_shown", "not checked for this area"],
                                  "f_gt97_h8": ["base_rate", "only 3 weeks with the event"]}, "horizons": {}},
        "cells": [{"id": f"39.{i}_-105.{i}", "lat": 39.0 + i / 24, "lon": -105.0 - i / 24, "p": [0.12345 + i / 100, None, 0.0196]} for i in range(cells)],
    }


@pytest.fixture()
def src(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "domains"
    issues = ["2026-09-29", "2026-10-06"]
    order = ["denver", "dillon"]
    for d in order:
        (root / d).mkdir(parents=True)
        for i in issues:
            (root / d / f"{i}.json").write_text(json.dumps(_bundle(d, i, 3 if d == "denver" else 2)))
    (root / "index.json").write_text(json.dumps({"order": order, "issues": issues, "targets": TARGETS,
                                                 "domains": {d: {"label": d.title()} for d in order}}))
    vint = tmp_path / "issue_vintages.json"
    vint.write_text(json.dumps({d: {i: "2026-10-11T22:12:48" for i in issues} for d in order}))
    return root, vint


def test_rows_match_the_bundles(tmp_path: Path, src: tuple[Path, Path]) -> None:
    root, vint = src
    out = tmp_path / "open"
    idx = open_data.build(out, root, vintages_path=vint)
    rows = list(csv.DictReader(io.StringIO((out / "cofire_latest.csv").read_text())))
    assert [f["name"] for f in idx["fields"]] == list(rows[0].keys())
    assert len(rows) == (3 + 2) * len(TARGETS)
    first = rows[0]
    assert first["issue"] == "2026-10-06" and first["vintage"] == "2026-10-11T22:12:48" and first["area"] == "denver"
    assert first["probability"] == "0.1235" and first["state"] == "probability" and first["reason"] == "calibrated, reliability 0.0072"
    # A target the app does not show has no number; a base rate is the base rate.
    hidden = [r for r in rows if r["target"] == "d_ge2_h4"]
    assert all(r["probability"] == "" and r["state"] == "not_shown" for r in hidden)
    assert all(r["probability"] == "0.0196" and r["state"] == "base_rate" for r in rows if r["target"] == "f_gt97_h8")
    assert {r["horizon_weeks"] for r in rows} == {"2", "4", "8"}


def test_every_issue_and_format(tmp_path: Path, src: tuple[Path, Path]) -> None:
    root, vint = src
    out = tmp_path / "open"
    idx = open_data.build(out, root, vintages_path=vint)
    assert [i["issue"] for i in idx["issues"]] == ["2026-09-29", "2026-10-06"]
    for i in idx["issues"]:
        rows = list(csv.DictReader(io.StringIO(gzip.decompress((out / i["csv"]).read_bytes()).decode())))
        assert len(rows) == i["rows"] == 5 * len(TARGETS)
        gj = json.loads(gzip.decompress((out / i["geojson"]).read_bytes()))
        assert len(gj["features"]) == 5 and gj["features"][0]["geometry"]["type"] == "Polygon"
        assert gj["features"][0]["properties"]["p_d_ge2_h4"] is None
        assert gj["reasons"]["dillon"]["f_gt97_h8"] == "only 3 weeks with the event"
    latest = json.loads((out / "cofire_latest.json").read_text())
    assert latest["areas"]["denver"]["cells"][0]["probability"] == [0.1235, None, 0.0196]


def test_index_fingerprints_and_license(tmp_path: Path, src: tuple[Path, Path]) -> None:
    root, vint = src
    out = tmp_path / "open"
    idx = open_data.build(out, root, vintages_path=vint)
    for name, meta in idx["files"].items():
        blob = (out / name).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == meta["sha256"] and len(blob) == meta["bytes"]
    assert idx["license"]["name"] == "CC BY 4.0"
    assert "CC BY 4.0" in (out / "LICENSE.md").read_text()
    assert {u["name"] for u in idx["license"]["upstream"]} >= {"gridMET", "U.S. Drought Monitor"}
    # Rebuilding gives the same bytes (gzip without timestamps).
    again = open_data.build(tmp_path / "open2", root, vintages_path=vint)
    assert {k: v["sha256"] for k, v in again["files"].items()} == {k: v["sha256"] for k, v in idx["files"].items()}


def test_an_unpinned_issue_is_refused_for_the_site(tmp_path: Path, src: tuple[Path, Path]) -> None:
    root, vint = src
    vint.write_text(json.dumps({"denver": {}, "dillon": {}}))
    with pytest.raises(SystemExit, match="no pinned vintage"):
        open_data.build(tmp_path / "open", root, vintages_path=vint)
    idx = open_data.build(tmp_path / "open", root, strict=False, vintages_path=vint)
    assert idx["issues"][0]["vintages"]["denver"] == "unpinned"
