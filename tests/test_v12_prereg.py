"""The v1.2 preregistration cannot change after it was recorded."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def test_the_preregistration_matches_its_recorded_hash() -> None:
    recorded = re.search(r"PREREGISTRATION_V12\.md`, sha256\s*`([0-9a-f]{64})`", Path("STATUS.md").read_text())
    assert recorded, "STATUS.md does not record the v1.2 preregistration hash"
    actual = hashlib.sha256(Path("docs/PREREGISTRATION_V12.md").read_bytes()).hexdigest()
    assert actual == recorded.group(1)
