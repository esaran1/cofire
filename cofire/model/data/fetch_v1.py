"""Fetch the v1 sources for both domains, staged and resumable.

Runs ESI then EDDI per domain. Each source caches to its own NetCDF, so an
interrupted run resumes by skipping what is already on disk rather than
refetching it and spending the budget twice.

macOS threading note: this module never imports torch, and LightGBM is not
involved, so the OpenMP deadlock path documented in DECISIONS.md cannot be hit
here. OMP_NUM_THREADS is pinned anyway for consistency with the rest of the
pipeline.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

from cofire.model.config import get_settings  # noqa: E402
from cofire.model.data import DateRange, SourceState  # noqa: E402
from cofire.model.data.eddi import EddiSource  # noqa: E402
from cofire.model.data.esi import EsiSource  # noqa: E402
from cofire.model.data.ledger import BudgetExceeded, get_ledger  # noqa: E402
from cofire.model.log import setup_logging  # noqa: E402

LOGGER = logging.getLogger("cofire.data.fetch_v1")


def run(start: date = date(2018, 1, 1), end: date = date(2026, 9, 15)) -> dict[str, str]:
    settings = get_settings()
    setup_logging(settings.log_dir)
    ledger = get_ledger(Path("data/ledger.json"))
    rng = DateRange(start=start, end=end)
    out: dict[str, str] = {}

    for src in (EsiSource(settings), EddiSource(settings)):
        try:
            LOGGER.info("%s: fetching for subset=%s", src.name, settings.subset_name)
            src.fetch(rng)
            st = src.status()
            out[src.name] = st.state.value
            LOGGER.info("%s: %s (%s)", src.name, st.state.value, st.note)
        except BudgetExceeded as exc:
            out[src.name] = "budget"
            LOGGER.warning("%s skipped: %s", src.name, exc)
        except Exception as exc:  # noqa: BLE001
            out[src.name] = SourceState.UNAVAILABLE.value
            LOGGER.warning("%s failed: %s", src.name, exc)

    LOGGER.info("ledger: %s", ledger.report().replace("\n", " | "))
    return out


if __name__ == "__main__":
    res = run()
    for k, v in res.items():
        print(f"{k}: {v}")
    print(get_ledger().report())
