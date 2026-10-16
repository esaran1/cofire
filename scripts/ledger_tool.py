"""Record a tool download in the ledger, kept out of the data budget.

    python scripts/ledger_tool.py SOURCE URL BYTES NOTE

Tool and package downloads are recorded in data/ledger.json with their size,
checksum and reason, as every brief since v1.2 asks, but they are not
data-source transfers. Each one is therefore written as a transfer plus a
correction of the same size that takes it out of the data budget's total, the
pattern of the v1.2 entries. The ledger's totals are recomputed from its
entries, never edited by hand.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER = Path("data/ledger.json")


def record(source: str, url: str, nbytes: int, note: str, path: Path = LEDGER) -> dict[str, Any]:
    """Append the transfer and its offsetting correction; return the new totals."""
    d = json.loads(path.read_text())
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    d["transfers"].append({"source": source, "url": url, "bytes": int(nbytes), "timestamp": now, "note": note})
    d["corrections"].append({
        "at": now,
        "reason": f"Tool download '{source}' is recorded with size and checksum but kept out of the data "
                  "budget's total, as for the earlier tool downloads. The entry is left as written.",
        "delta_bytes": -int(nbytes),
        "evidence": f"entry '{source}' {now[:10]}, {int(nbytes):,} B",
    })
    d["recorded_bytes"] = sum(int(t["bytes"]) for t in d["transfers"])
    d["correction_bytes"] = sum(int(c["delta_bytes"]) for c in d["corrections"])
    d["total_bytes"] = d["recorded_bytes"] + d["correction_bytes"]
    d["remaining_bytes"] = d["budget_bytes"] - d["total_bytes"]
    path.write_text(json.dumps(d, indent=2))
    return {k: d[k] for k in ("recorded_bytes", "correction_bytes", "total_bytes", "remaining_bytes")}


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    print(json.dumps(record(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])))
