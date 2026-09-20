"""Write data/MANIFEST.json from every source.status()."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from cofire.model.data import SourceStatus


def write_manifest(path: Path, sources: Iterable[SourceStatus]) -> str:
    rows = [s.as_dict() for s in sources]
    blob = json.dumps(rows, sort_keys=True)
    digest = hashlib.sha256(blob.encode()).hexdigest()
    payload = {
        "written_at": datetime.now(UTC).isoformat(),
        "hash": digest,
        "sources": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return digest
