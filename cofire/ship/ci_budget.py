"""The weekly refresh's own download budget, apart from the local ledger.

CI transfers are recorded in `artifacts/ci/ledger.json`; the local project
ledger (`data/ledger.json`) is for this machine's fetches. Each CI run is one
session (`refresh-<run id>`) with a hard ceiling of three times the measured
size of a steady-state run:

    largest 2026 weekly USDM map   3,412,666 B  (38 maps, median 2,355,010)
    ERC, five domains              180,093 B  (7 new days + 14 re-read, one gate
                                               day, DDS; DAP2 wire bytes)
    per run                       3,592,759 B
    ceiling (x3)                 10,778,277 B

`safe_fetch` and the ERC reader refuse any transfer that would cross the
ceiling, and `check` fails the job afterwards if a run's total exceeds it, so
an overrun can neither happen quietly nor pass unnoticed.

    python -m cofire.ship.ci_budget check
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PER_RUN_BYTES = 3_592_759
CEILING_BYTES = 3 * PER_RUN_BYTES
CI_LEDGER = Path("artifacts/ci/ledger.json")
# A backstop over the year, far above 52 runs at the measured size.
CI_BUDGET_BYTES = 1_000_000_000


def ledger_path() -> Path:
    return Path(os.environ.get("COFIRE_LEDGER_PATH", "data/ledger.json"))


def check(session: str, path: Path = CI_LEDGER, ceiling: int = CEILING_BYTES) -> dict[str, object]:
    blob = json.loads(path.read_text()) if path.exists() else {"transfers": []}
    tag = f"session={session}"
    rows = [t for t in blob["transfers"] if tag in t.get("note", "").split("; ")]
    total = sum(int(t["bytes"]) for t in rows)
    rejected = [t for t in rows if "REJECTED" in t.get("note", "")]
    return {"session": session, "transfers": len(rows), "bytes": total, "ceiling": ceiling,
            "rejected": len(rejected), "ok": total <= ceiling}


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit(__doc__)
    r = check(os.environ["COFIRE_FETCH_SESSION"])
    print(json.dumps(r))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(f"Refresh transfer: {r['bytes']:,} B of a {r['ceiling']:,} B ceiling "
                     f"({r['transfers']} transfers, {r['rejected']} rejected)\n")
    if not r["ok"]:
        print(f"::error::refresh transferred {r['bytes']} B, over the {r['ceiling']} B per-run ceiling")
        sys.exit(1)
