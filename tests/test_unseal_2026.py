"""scripts/unseal_2026.py refuses every way the preregistration says it must, and reads nothing from 2026 when it does.

The clock, the environment and the repository checks are all mocked. The
functions that read published forecasts or 2026 outcomes are replaced with
traps, so a test fails if anything is read before every precondition passes.
Nothing here scores 2026.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("unseal_2026", ROOT / "scripts" / "unseal_2026.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["unseal_2026"] = mod
    spec.loader.exec_module(mod)
    return mod


U = _load()
ON_TIME = datetime(2027, 1, 12, 0, 0, 1, tzinfo=UTC)
GOOD_ENV = {"COFIRE_ALLOW_LOOK": "4"}


class Read(Exception):
    """Raised by the traps: something was read."""


@pytest.fixture()
def trapped(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    reads: list[str] = []

    def trap(name: str):  # type: ignore[no-untyped-def]
        def f(*a, **k):  # type: ignore[no-untyped-def]
            reads.append(name)
            raise Read(name)
        return f

    monkeypatch.setattr(U, "published_forecasts", trap("published_forecasts"))
    monkeypatch.setattr(U, "outcomes", trap("outcomes"))
    return reads


def good_hooks(**over: object) -> object:
    base = {"config_hash": lambda: U.CONFIG_HASH, "model_matches": lambda c: (True, []), "look_count": lambda: 3, "tree_clean": lambda: True}
    base.update(over)
    return U.Hooks(**base)


def refused(capsys: pytest.CaptureFixture[str], **kw: object) -> str:
    with pytest.raises(SystemExit) as e:
        U.main(**kw)
    return str(e.value)


def test_the_pins_match_the_record() -> None:
    assert U.sha256(ROOT / U.PREREG) == U.PREREG_SHA256, "the unseal preregistration changed without the script"
    assert U.sha256(ROOT / U.LOOK3_PREREG) == U.LOOK3_PREREG_SHA256
    facts = json.loads((ROOT / "app/lib/facts.json").read_text())
    assert U.CONFIG_HASH == facts["config_hash"] == facts["look3"]["config_hash"]
    assert facts["preregistration_sha256"] == U.LOOK3_PREREG_SHA256
    assert U.unseal_date() == datetime(2027, 1, 12, tzinfo=UTC)
    assert json.loads((ROOT / "app/lib/seal.json").read_text())["unseal_date"] == "2027-01-12"


def test_refuses_before_the_date(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    msg = refused(capsys, now=datetime(2027, 1, 11, 23, 59, 59, tzinfo=UTC), env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks())
    assert "the unseal date has come" in msg and "2027-01-12" in msg
    assert trapped == [] and not (tmp_path / "u").exists()


def test_refuses_today(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    msg = refused(capsys, now=datetime.now(UTC), env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks())
    assert "the unseal date has come" in msg and trapped == []


def test_refuses_without_the_deliberate_flag(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    for env in ({}, {"COFIRE_ALLOW_LOOK": "3"}):
        msg = refused(capsys, now=ON_TIME, env=env, out=tmp_path / "u", hooks=good_hooks())
        assert "COFIRE_ALLOW_LOOK=4" in msg
    assert trapped == []


def test_refuses_when_the_model_hash_differs(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    msg = refused(capsys, now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks(config_hash=lambda: "0" * 64))
    assert "configuration hash matches" in msg and trapped == []


def test_refuses_when_a_model_file_differs(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    msg = refused(capsys, now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks(model_matches=lambda c: (False, ["cofire/model/targets.py"])))
    assert "cofire/model/ matches FREEZE_COMMIT" in msg and "targets.py" in msg and trapped == []


def test_refuses_when_a_preregistration_differs(tmp_path: Path, trapped: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for attr in ("PREREG", "LOOK3_PREREG"):
        edited = tmp_path / f"{attr}.md"
        edited.write_text((ROOT / getattr(U, attr)).read_text() + "\nOne word changed after the fact.\n")
        with monkeypatch.context() as m:
            m.setattr(U, attr, edited)
            msg = refused(capsys, now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks())
        assert f"{edited} is unchanged" in msg
    assert trapped == []


def test_refuses_unless_the_look_counter_reads_three(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    for n in (2, 4):
        msg = refused(capsys, now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks(look_count=lambda n=n: n))
        assert "look counter" in msg
    assert trapped == []


def test_refuses_to_write_into_an_existing_directory(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "u").mkdir()
    (tmp_path / "u" / "probability.csv").write_text("an earlier result\n")
    msg = refused(capsys, now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks())
    assert "output directory is new" in msg and trapped == []
    assert (tmp_path / "u" / "probability.csv").read_text() == "an earlier result\n"


def test_refuses_with_a_dirty_tree(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    msg = refused(capsys, now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks(tree_clean=lambda: False))
    assert "working tree is clean" in msg and trapped == []


def test_every_failure_is_named_at_once(tmp_path: Path, trapped: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    msg = refused(capsys, now=datetime(2026, 10, 15, tzinfo=UTC), env={}, out=tmp_path / "u",
                  hooks=good_hooks(config_hash=lambda: "x" * 64, look_count=lambda: 2))
    assert msg.count("FAIL") == 4 and "nothing from 2026 was read" in msg


def test_reads_only_after_every_precondition_passes(tmp_path: Path, trapped: list[str]) -> None:
    with pytest.raises(Read):
        U.main(now=ON_TIME, env=GOOD_ENV, out=tmp_path / "u", hooks=good_hooks())
    assert trapped == ["published_forecasts"]
    assert not (tmp_path / "u").exists()


def test_a_tampered_forecast_file_stops_scoring(tmp_path: Path) -> None:
    import gzip
    import hashlib

    blob = gzip.compress(b'{"issue":"2026-10-06","domains":{}}', mtime=0)
    (tmp_path / "2026-10-06.json.gz").write_bytes(blob + b"x")
    (tmp_path / "manifest.json").write_text(json.dumps([{"issue": "2026-10-06", "file": "2026-10-06.json.gz", "sha256": hashlib.sha256(blob).hexdigest()}]))
    with pytest.raises(SystemExit, match="does not match the manifest"):
        U.published_forecasts(tmp_path / "manifest.json")


def test_only_counted_forecasts_are_kept() -> None:
    def payload(issue: str) -> dict[str, object]:
        return {"issue": issue, "domains": {"denver": {
            "targets": ["d_ge2_h2", "d_ge2_h8", "f_gt97_h2", "d_ge3_h2"],
            "decisions": {"targets": {"d_ge2_h2": ["probability", ""], "d_ge2_h8": ["probability", ""], "f_gt97_h2": ["base_rate", ""], "d_ge3_h2": ["not_shown", ""]}},
            "cells": [{"id": "c1", "p": [0.5, 0.4, 0.02, None], "h": {"2": [50.0, 30, 70, "x"], "8": [55.0, 30, 70, "x"]}}]}}}
    probs, dry = U.forecast_rows([({"backfilled": True}, payload("2026-12-15")), ({}, payload("2026-12-22"))])
    # 2026-12-15 + 2 weeks is the last 2026 map week: counted. + 8 weeks is 2027: not. Not shown: never.
    assert sorted(zip(probs["issue"].astype(str).str[:10], probs["target"], strict=True)) == [("2026-12-15", "d_ge2_h2"), ("2026-12-15", "f_gt97_h2")]
    assert set(probs["state"]) == {"probability", "base_rate"} and probs["backfilled"].all()
    assert list(dry["horizon"]) == [2]


def test_the_scores_on_synthetic_data() -> None:
    rng = np.random.default_rng(7)
    p = rng.uniform(0, 1, 5000)
    y = (rng.uniform(0, 1, 5000) < p).astype(float)
    weeks = np.repeat(np.arange(50), 100)
    row, diagram = U.score_probability(p, y, weeks, "probability")
    assert row["judged"] and row["verdict"] == "pass" and row["reliability"] < 0.01 and len(diagram) == 10
    bad, _ = U.score_probability(np.clip(p + 0.4, 0, 1), y, weeks, "probability")
    assert bad["verdict"] == "fail"
    few, _ = U.score_probability(p[:50], y[:50], weeks[:50], "probability")
    assert few["verdict"] == "too few to judge"
    rate, _ = U.score_probability(p, y, weeks, "base_rate")
    assert not rate["judged"]
    d = U.score_dryness(np.array([50.0, 60.0, np.nan]), np.array([40.0, 70.0, 50.0]))
    assert d == {"n": 2, "mae": 10.0, "rmse": 10.0, "bias": 0.0}
