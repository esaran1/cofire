"""How far back gridMET's current revision of the 2026 ERC record reaches.

Reads the current year from its first day for each domain, through the same
reader and ledger accounting as the refresh, and compares it cell-day by
cell-day with the latest held vintage. Nothing is stored as a vintage here;
the result decides the provisional window (docs/DECISIONS.md).

    python -m cofire.ship.gridmet_reach 2026 <n_days>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402

OUT = Path("artifacts/audit/gridmet_revision_reach.json")


def measure(year: int, n_days: int) -> dict[str, Any]:
    from cofire.model.data import erc_extension as ext
    from cofire.model.data.ledger import DownloadLedger
    from cofire.ship import domains, erc_fetch, vintages
    from cofire.ship.safe_fetch import SESSION, SESSION_CAP_BYTES, FetchRefused, session_bytes

    ledger = DownloadLedger(Path("data/ledger.json"))
    out: dict[str, Any] = {"year": year, "days_read": n_days, "domains": {}}
    for d in domains.ORDER:
        have = vintages.assemble(d, year)
        n_lat, n_lon = erc_fetch.rect(d)
        cost = n_days * n_lat * n_lon * 4 + (n_days + n_lat + n_lon) * 8 + erc_fetch._OPEN_OVERHEAD
        if session_bytes(ledger) + cost > SESSION_CAP_BYTES or not ledger.can_afford(cost):
            raise FetchRefused(f"{d}: {cost} B would exceed the session cap or the ledger")
        constraint = f"{ext.OPENDAP.format(year=year)}?energy_release_component-g day[0:{n_days}] bbox={erc_fetch.settings_for(d).bbox}"
        new = erc_fetch._read_days(d, year, 0, n_days)
        ledger.record("gridMET-OPeNDAP", constraint, cost,
                      note=f"session={SESSION}; revision-reach probe, not stored as a vintage; bytes computed from the DAP2 wire format")
        old = have.isel(day=slice(0, n_days))
        a, b = np.asarray(new.values, float), np.asarray(old.values, float)
        diff = np.isfinite(a) & np.isfinite(b) & (a != b)
        per_day = diff.reshape(diff.shape[0], -1).sum(axis=1)
        days = [str(t)[:10] for t in new.day.values]
        changed = [i for i in range(len(days)) if per_day[i] > 0]
        out["domains"][d] = {
            "bytes": cost,
            "changed_days": len(changed),
            "first_changed": days[changed[0]] if changed else None,
            "changed_cell_days": int(diff.sum()),
            "max_abs_change": float(np.nanmax(np.abs(a - b)[diff])) if diff.any() else 0.0,
            "by_month": {m: int(sum(per_day[i] for i in range(len(days)) if days[i][5:7] == m))
                         for m in sorted({x[5:7] for x in days})},
        }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    print(json.dumps(measure(int(sys.argv[1]), int(sys.argv[2])), indent=1))
