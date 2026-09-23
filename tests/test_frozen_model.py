"""Nothing under `cofire/model/` changes after the freeze.

The preregistration is only binding if the code it describes cannot move
afterwards. `artifacts/FREEZE_COMMIT` names the commit the preregistration was
recorded at, and this test fails if any model file differs from it.

Before the freeze commit exists the test skips, so it can be committed
alongside the thing it guards.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cofire.model.freeze import config_hash, model_files_match

FREEZE_FILE = Path("artifacts/FREEZE_COMMIT")


def _freeze_commit() -> str:
    if not FREEZE_FILE.exists():
        pytest.skip("no FREEZE_COMMIT recorded yet")
    return FREEZE_FILE.read_text().strip()


def _require_commit(ref: str) -> None:
    """Fail clearly if the freeze commit is not in this checkout's history.

    `model_files_match` reports any git failure as a changed file, so a shallow
    clone without the freeze commit read as "the model changed" when nothing
    had. That helper is inside the frozen tree and cannot be edited, so the
    check happens here. It fails rather than skips: a guard that quietly skips
    when it cannot run is not a guard.
    """
    import subprocess

    found = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"], capture_output=True
    ).returncode == 0
    assert found, (
        f"FREEZE_COMMIT {ref[:12]} is not in this checkout's history, so the "
        "frozen model cannot be checked. This is a shallow clone, not a model "
        "change: fetch full history (actions/checkout with fetch-depth: 0, or "
        "`git fetch --unshallow`)."
    )


def test_no_model_file_differs_from_the_freeze() -> None:
    ref = _freeze_commit()
    _require_commit(ref)
    ok, changed = model_files_match(ref)
    assert ok, (
        "these files under cofire/model/ differ from FREEZE_COMMIT "
        f"{ref[:12]}: {changed}. Nothing about the model changes after the "
        "freeze; if a change is genuinely required, the preregistration is "
        "void and a new one must be recorded."
    )


def test_config_hash_matches_the_preregistration() -> None:
    _freeze_commit()
    doc = Path("docs/PREREGISTRATION_LOOK3.md").read_text()
    recorded = ""
    for line in doc.splitlines():
        if "**Config hash** sha256" in line:
            recorded = line.split("`")[1]
            break
    assert recorded, "the preregistration records no config hash"
    assert config_hash() == recorded, (
        "the recomputed configuration hash does not match the preregistration"
    )
