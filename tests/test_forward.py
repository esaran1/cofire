"""Published forecasts are immutable: every file matches its manifest entry,
and no manifest entry is ever edited or removed."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from cofire.v12 import forward


def test_every_published_file_matches_its_entry() -> None:
    m = forward.manifest()
    assert m, "no forecasts published"
    for e in m:
        data = (forward.ROOT / e["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == e["sha256"], e["issue"]
        assert len(data) == e["bytes"]
    assert [e["issue"] for e in m] == sorted(e["issue"] for e in m)
    files = {p.name for p in forward.ROOT.glob("*.json.gz")}
    assert files == {e["file"] for e in m}, "a file without an entry, or an entry without a file"


def test_the_app_copy_lists_the_same_entries() -> None:
    app = json.loads(Path("app/lib/forward.json").read_text())
    assert [(a["issue"], a["sha256"]) for a in app] == [(e["issue"], e["sha256"]) for e in forward.manifest()]


def test_append_only_rule() -> None:
    a = [{"issue": "2026-01-06", "sha256": "x"}]
    assert forward.is_append_only(a, a + [{"issue": "2026-01-13", "sha256": "y"}])
    assert not forward.is_append_only(a, [{"issue": "2026-01-06", "sha256": "z"}])
    assert not forward.is_append_only(a + [{"issue": "2026-01-13"}], a)


def test_no_earlier_manifest_entry_was_ever_modified() -> None:
    """Every committed version of the manifest is a prefix of the current one."""
    try:
        shas = subprocess.run(["git", "log", "--format=%H", "--", str(forward.MANIFEST)],
                              capture_output=True, text=True, check=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("no git history")
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], capture_output=True, text=True).stdout.strip()
    if not shas or shallow == "true":
        pytest.skip("manifest not yet committed, or a shallow clone")
    current = forward.manifest()
    for sha in shas:
        old = json.loads(subprocess.run(["git", "show", f"{sha}:{forward.MANIFEST}"], capture_output=True,
                                        text=True, check=True).stdout)
        assert forward.is_append_only(old, current), f"manifest at {sha[:7]} is not a prefix of the current one"


def test_publishing_never_rewrites_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(forward, "ROOT", tmp_path)
    monkeypatch.setattr(forward, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(forward, "APP_COPY", tmp_path / "app.json")
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    first = "2026-01-06"
    (bundles / "index.json").write_text(json.dumps({"issues": [first]}))
    monkeypatch.setattr(forward, "BUNDLES", bundles)
    (tmp_path / "manifest.json").write_text("[]")
    (tmp_path / f"{first}.json.gz").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="never rewritten|backfill"):
        forward.publish(backfill=True)
