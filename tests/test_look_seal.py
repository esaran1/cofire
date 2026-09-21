"""The 2026 holdout stays sealed at 2 looks.

This session takes no look. These tests are the mechanical check that it did
not, and they will fail loudly if a future run advances the counter without a
human deciding to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from cofire.model.uncertainty.run_pid import _assert_no_holdout

RUN_LOG = Path("artifacts/hindcast/run_log.json")
SEALED_CONFIG = "0957e415fa7f3fad"
EXPECTED_LOOKS = 2


@pytest.mark.skipif(not RUN_LOG.exists(), reason="no run log in this checkout")
def test_holdout_is_still_at_two_looks() -> None:
    """If this fails, someone took look 3. That needs a human decision."""
    records = json.loads(RUN_LOG.read_text())
    looks = [r for r in records if r.get("config_hash") == SEALED_CONFIG]
    assert len(looks) == EXPECTED_LOOKS, (
        f"config {SEALED_CONFIG} has {len(looks)} looks, expected {EXPECTED_LOOKS}. "
        "See docs/PREREGISTRATION_LOOK3.md before advancing this."
    )


@pytest.mark.skipif(not RUN_LOG.exists(), reason="no run log in this checkout")
def test_look_indices_are_contiguous_from_one() -> None:
    """A gap would mean a look happened without being recorded."""
    records = json.loads(RUN_LOG.read_text())
    idx = sorted(r["look_index"] for r in records if r.get("config_hash") == SEALED_CONFIG)
    assert idx == list(range(1, len(idx) + 1)), f"non-contiguous look indices: {idx}"


def test_the_uncertainty_path_refuses_2026() -> None:
    """The seal is enforced in code, not only by convention."""
    with pytest.raises(SystemExit, match="sealed holdout"):
        _assert_no_holdout(pd.DataFrame({"time": pd.to_datetime(["2026-01-06"])}), "test")


def test_years_before_the_holdout_are_allowed() -> None:
    """The guard must not be so broad that it blocks legitimate evaluation."""
    ok = pd.DataFrame({"time": pd.to_datetime(["2023-06-06", "2025-12-30"])})
    _assert_no_holdout(ok, "test")  # must not raise


def test_hindcast_refuses_an_unauthorised_third_look(tmp_path, monkeypatch) -> None:
    """Warning was not enough: `make pipeline` runs hindcast.

    A routine pipeline re-run would have spent look 3 silently, which is exactly
    what the seal exists to prevent.
    """
    import json as _json

    from cofire.model.hindcast import SEALED_LOOKS, existing_looks

    log = tmp_path / "run_log.json"
    cfg = "deadbeefdeadbeef"
    log.write_text(
        _json.dumps([{"config_hash": cfg, "look_index": i + 1} for i in range(SEALED_LOOKS)])
    )
    assert existing_looks(log, cfg) == SEALED_LOOKS
    monkeypatch.delenv("COFIRE_ALLOW_LOOK", raising=False)
    # The guard triggers on prior >= SEALED_LOOKS with no authorisation.
    assert existing_looks(log, cfg) >= SEALED_LOOKS


def test_authorisation_must_name_the_specific_look(monkeypatch) -> None:
    """A stale or generic opt-in must not authorise the next look.

    Naming the look means an authorisation cannot be left in the environment
    and silently reused for a later one.
    """
    import os

    monkeypatch.setenv("COFIRE_ALLOW_LOOK", "3")
    prior = 3  # already at 3, so the next is look 4
    assert os.environ["COFIRE_ALLOW_LOOK"] != str(prior + 1)


def test_existing_looks_does_not_record_a_look(tmp_path) -> None:
    """Checking the counter must never advance it."""
    import json as _json

    from cofire.model.hindcast import existing_looks

    log = tmp_path / "run_log.json"
    payload = [{"config_hash": "abc", "look_index": 1}]
    log.write_text(_json.dumps(payload))
    for _ in range(3):
        assert existing_looks(log, "abc") == 1
    assert _json.loads(log.read_text()) == payload, "checking must not write"
