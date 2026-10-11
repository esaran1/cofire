"""Weekly refresh: the newest USDM map and ERC days, through the frozen path.

    python -m cofire.ship.refresh

1. The look counter must read 3, before and after.
2. The target issue is the latest Tuesday whose USDM map has been released
   (Thursday 08:30 ET) and whose seven ERC days are all on the server.
3. Missing USDM weekly maps are fetched through `safe_fetch` and added to the
   yearly archive as members, which is what the archive is made of.
4. Every domain's daily ERC is extended by the new days only, over the
   reconciled OPeNDAP path, with an overlap week and an older gate day.
5. Each ERC fetch becomes a vintage (`cofire.ship.vintages`): revisions
   inside the provisional window are accepted and logged, anything older
   fails the gate. Issues already published keep the vintage they were built
   from; only new issues use the latest.
6. The export is rebuilt through the target issue, scoring nothing and
   emitting only issues whose inputs were complete and published, then the
   bundles, the demo fixture and the story.

Idempotent: with nothing new on the servers it fetches nothing and leaves the
export unchanged. Resumable: every step skips what is already on disk. Each
run appends to `artifacts/ship/refresh_log.json`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import pandas as pd  # noqa: E402

from cofire.ship import domains, erc_fetch  # noqa: E402
from cofire.ship.export import (  # noqa: E402
    latest_published,
    usdm_weeks_available,
    utc_now,
)
from cofire.ship.safe_fetch import (  # noqa: E402
    SESSION,
    FetchRefused,
    safe_extract,
    safe_fetch,
    session_bytes,
)

LOGGER = logging.getLogger("cofire.ship.refresh")

RAW = Path("data/raw")
USDM_URL = "https://droughtmonitor.unl.edu/data/shapefiles_m/USDM_{d:%Y%m%d}_M.zip"
LOG = Path("artifacts/ship/refresh_log.json")
# Sizes of the national weekly maps as published, the peers for the size check.
# In CI the local archive is the data pack's Colorado clip, whose entries are
# about 1/170 the size of a national map, so they cannot be the peers; the
# first map fetched in CI was refused for exactly that (run 37072550722).
NATIONAL_SIZES = Path("artifacts/ship/usdm_national_sizes.json")


def national_peers(archive: Path, n: int = 8) -> list[int]:
    """The last `n` national weekly map sizes: from the record, else the national archive."""
    if NATIONAL_SIZES.exists():
        sizes: dict[str, int] = json.loads(NATIONAL_SIZES.read_text())
        if sizes:
            return [sizes[k] for k in sorted(sizes)][-n:]
    if archive.exists() and not archive.parent.is_symlink():
        with zipfile.ZipFile(archive) as zf:
            return [i.file_size for i in zf.infolist()][-n:]
    return []


def record_national_size(name: str, n_bytes: int) -> None:
    sizes: dict[str, int] = json.loads(NATIONAL_SIZES.read_text()) if NATIONAL_SIZES.exists() else {}
    sizes[name] = n_bytes
    NATIONAL_SIZES.write_text(json.dumps(dict(sorted(sizes.items())), indent=1) + "\n")
EXPORT = Path("artifacts/ship/forecast_issues.parquet")


def _ledger() -> Any:
    from cofire.model.data.ledger import DownloadLedger
    from cofire.ship.ci_budget import CI_BUDGET_BYTES, CI_LEDGER, ledger_path

    path = ledger_path()
    if path == CI_LEDGER:
        return DownloadLedger(path, budget_bytes=CI_BUDGET_BYTES)
    return DownloadLedger(path)


def usdm_week(week: pd.Timestamp, ledger: Any) -> dict[str, Any]:
    """Fetch one weekly USDM map and add it to its year's archive."""
    archive = RAW / "usdm" / f"{week.year}_USDM_M.zip"
    name = f"USDM_{week:%Y%m%d}_M.zip"
    if archive.exists():
        with zipfile.ZipFile(archive) as zf:
            if name in zf.namelist():
                return {"week": str(week.date()), "fetched": False}
    peers = national_peers(archive)
    incoming = RAW / "usdm" / "incoming" / name
    res = safe_fetch(USDM_URL.format(d=week), incoming, "zip", "USDM-weekly", peers=peers, ledger=ledger)
    with tempfile.TemporaryDirectory() as d:
        files = safe_extract(incoming, Path(d))
        if not any(f.suffix.lower() == ".shp" for f in files):
            incoming.unlink()
            raise FetchRefused(f"{name} holds no shapefile")
    from cofire.ship import datapack

    # Locally the national archive gets the map as published. The data pack's
    # Colorado archive gets the clipped map; in CI, where data/raw/usdm is the
    # pack's archive, that is the only copy.
    if not (RAW / "usdm").is_symlink():
        part = archive.with_name(archive.name + ".part")
        if archive.exists():
            shutil.copy2(archive, part)
        with zipfile.ZipFile(part, "a") as zf:
            zf.write(incoming, arcname=name)
        part.replace(archive)
    if datapack.CLIPPED.exists():
        datapack.append_clipped(incoming, week.year)
    record_national_size(name, res.n_bytes)
    incoming.unlink()
    return {"week": str(week.date()), "fetched": True, "bytes": res.n_bytes, "sha256": res.sha256}


def same_export(previous: bytes, current: Path, atol: float = 1e-9) -> bool:
    """Same rows and columns, numbers equal within `atol`, everything else exact."""
    import io

    import numpy as np

    a = pd.read_parquet(io.BytesIO(previous))
    b = pd.read_parquet(current)
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            if not np.allclose(x.to_numpy(float), y.to_numpy(float), atol=atol, rtol=0, equal_nan=True):
                return False
        elif not x.astype(str).equals(y.astype(str)):
            return False
    return True


def run(now: pd.Timestamp | None = None) -> dict[str, Any]:
    from cofire.model.freeze import look_count
    from cofire.ship import bundles, demo, export, story

    assert look_count() == 3, "look counter must read 3 before a refresh"
    now = utc_now() if now is None else now
    ledger = _ledger()
    bytes_before = session_bytes(ledger)
    target = latest_published(now)
    log: dict[str, Any] = {"run_at": str(now), "session": SESSION, "target_published": str(target.date())}

    have = usdm_weeks_available(RAW, range(target.year, target.year + 1))
    tuesdays = pd.date_range(f"{target.year}-01-01", target, freq="W-TUE")
    log["usdm"] = [usdm_week(w, ledger) for w in tuesdays if w not in have]
    from cofire.ship.usdm_calendar import assert_complete

    assert_complete(range(2007, target.year), RAW)
    assert_complete(range(target.year, target.year + 1), RAW, through=target)

    # Each fetch becomes a vintage; the vintage gate accepts revisions inside
    # the provisional window, logs them, and refuses anything older.
    log["erc"] = [erc_fetch.extend(d, target.year, ledger, now=now) for d in domains.ORDER]
    log["revised_cell_days"] = {e["domain"]: e.get("revised_cell_days", 0) for e in log["erc"]}

    target = min([target, *[export.erc_complete_issue(d, target.year) for d in domains.ORDER]])
    log["target"] = str(target.date())
    previous = EXPORT.read_bytes() if EXPORT.exists() else None
    export.write(last_issue=target, now=now)
    log["export_changed"] = previous is None or not same_export(previous, EXPORT)
    if previous is not None and not log["export_changed"]:
        # Equal to the last export within floating-point noise (least-squares
        # sums differ at 1e-12 between Linux and macOS): keep the old bytes, so
        # a week with nothing new commits nothing.
        EXPORT.write_bytes(previous)
    f = pd.read_parquet(EXPORT)
    log["issues"] = [str(pd.Timestamp(f["time"].min()).date()), str(pd.Timestamp(f["time"].max()).date())]
    assert (pd.to_datetime(f["available_at"]) <= now).all(), "an issue was emitted before its inputs were published"
    assert pd.Timestamp(f["time"].max()) == target, f"last issue {f['time'].max()} is not the target {target}"
    usdm_now = f[f["time"] == target].groupby("domain")["usdm"].mean()
    log["usdm_mean_at_target"] = {k: round(float(v), 3) for k, v in usdm_now.items()}

    bundles.build()
    demo.build()
    story.write()
    # Each new issue is published once, with its hash, and never changed.
    from cofire.v12 import forward

    log["published"] = [e["issue"] for e in forward.publish(now=now)]
    log["bytes"] = session_bytes(ledger) - bytes_before
    assert look_count() == 3, "look counter moved during a refresh"
    log["looks"] = 3
    log["outcome"] = "updated" if log["export_changed"] else "no change"
    log_append(log)
    return log


def log_append(entry: dict[str, Any]) -> None:
    runs = json.loads(LOG.read_text()) if LOG.exists() else []
    runs.append(entry)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(runs, indent=1, default=str) + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = run()
    print(json.dumps({k: v for k, v in out.items() if k not in ("erc", "usdm")}, indent=1, default=str))
    print("erc", [(e["domain"], e.get("new_days"), e.get("last_day")) for e in out["erc"]])
    print("usdm", out["usdm"])
