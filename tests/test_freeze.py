"""The freeze: what the configuration hash covers, and what the seal counts.

Two faults this closes, both of which would let a sealed holdout be looked at
again without anyone noticing:

1. The hash in `hindcast.py` covers a handful of hyperparameters, so every line
   of model code could change without changing it. A hash that does not move
   when the model moves cannot certify a freeze.
2. That counter is keyed on the config hash, so changing the configuration
   resets the count to zero and hands back a fresh set of looks at data that
   has already been seen. The seal belongs to the year.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cofire.model.freeze import (
    HOLDOUT_YEAR,
    config_hash,
    look_count,
    model_files_match,
    record_look,
)


def test_hash_moves_when_model_source_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cofire.model.freeze as fz

    src = tmp_path / "model"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(fz, "MODEL_DIR", src)
    monkeypatch.setattr(fz, "SHIPPED_ARTIFACTS", ())
    before = fz.config_hash()
    (src / "a.py").write_text("x = 2\n")
    assert fz.config_hash() != before


def test_hash_moves_when_a_file_is_renamed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Contents alone is not enough: a rename changes what gets imported."""
    import cofire.model.freeze as fz

    src = tmp_path / "model"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(fz, "MODEL_DIR", src)
    monkeypatch.setattr(fz, "SHIPPED_ARTIFACTS", ())
    before = fz.config_hash()
    (src / "a.py").rename(src / "b.py")
    assert fz.config_hash() != before


def test_hash_moves_when_a_fitted_artifact_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cofire.model.freeze as fz

    src = tmp_path / "model"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n")
    art = tmp_path / "choices.json"
    art.write_text('{"a": 1}')
    monkeypatch.setattr(fz, "MODEL_DIR", src)
    monkeypatch.setattr(fz, "SHIPPED_ARTIFACTS", (art,))
    before = fz.config_hash()
    art.write_text('{"a": 2}')
    assert fz.config_hash() != before


def test_hash_moves_when_a_fit_window_sidecar_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The window an artifact declares is part of the configuration."""
    import cofire.model.freeze as fz

    src = tmp_path / "model"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n")
    art = tmp_path / "choices.json"
    art.write_text('{"a": 1}')
    side = tmp_path / "choices.json.fitwindow.json"
    side.write_text('{"fit_start": "2007-01-01", "fit_end": "2021-12-31", "scope": "train"}')
    monkeypatch.setattr(fz, "MODEL_DIR", src)
    monkeypatch.setattr(fz, "SHIPPED_ARTIFACTS", (art,))
    before = fz.config_hash()
    side.write_text('{"fit_start": "2007-01-01", "fit_end": "2022-12-31", "scope": "train"}')
    assert fz.config_hash() != before


def test_hash_is_stable_across_calls() -> None:
    assert config_hash() == config_hash()


def test_seal_is_keyed_on_the_year_not_the_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Changing the configuration must not hand back a fresh set of looks."""
    import cofire.model.freeze as fz

    log = tmp_path / "look_log.json"
    monkeypatch.setattr(fz, "_legacy_look_count", lambda year: 0)
    log.write_text(json.dumps([
        {"holdout_year": 2026, "config_hash": "aaa"},
        {"holdout_year": 2026, "config_hash": "bbb"},
    ]))
    assert fz.look_count(2026, log) == 2, "two looks under two configs is still two looks"


def test_legacy_looks_are_carried_forward() -> None:
    """The two looks already taken at 2026 count, whatever code took them."""
    assert look_count(HOLDOUT_YEAR) >= 2


def test_recording_a_look_increments_the_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cofire.model.freeze as fz

    log = tmp_path / "look_log.json"
    monkeypatch.setattr(fz, "_legacy_look_count", lambda year: 2)
    assert fz.look_count(2026, log) == 2
    n = fz.record_look(2026, "cfg", "look 3", log)
    assert n == 3
    assert fz.look_count(2026, log) == 3


def test_recording_is_append_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cofire.model.freeze as fz

    log = tmp_path / "look_log.json"
    monkeypatch.setattr(fz, "_legacy_look_count", lambda year: 0)
    fz.record_look(2026, "a", "first", log)
    fz.record_look(2026, "b", "second", log)
    records = json.loads(log.read_text())
    assert len(records) == 2
    assert records[0]["note"] == "first"


def test_model_files_match_detects_a_change() -> None:
    """The post-look invariant must be a real diff against the freeze commit."""
    ok, changed = model_files_match("HEAD")
    assert ok, f"unexpected diff against HEAD: {changed}"


def test_model_files_match_reports_a_bad_ref() -> None:
    ok, changed = model_files_match("not-a-real-ref")
    assert not ok
    assert changed
