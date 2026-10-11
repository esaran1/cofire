"""Stage 5: every issued forecast, published once and never changed.

Each weekly refresh writes each new issue's live forecast (the five domains'
bundles, exactly as the app serves them) to `artifacts/forecasts/<issue>.json.gz`
and appends one entry to `artifacts/forecasts/manifest.json`: the issue, the
file, its sha256 and size, and when it was published. A published file is
never rewritten and a manifest entry is never edited; tests check both
against the files and against the manifest's own git history.

Issues that existed before this stage were published in one backfill and are
marked `backfilled: true`: their timestamp is the backfill's, not the issue's,
and the scoreboard says so.

Nothing here scores anything. Scoring opens on 2027-01-12, when the 2026 seal
lifts.

    python -m cofire.v12.forward publish [--backfill]
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path("artifacts/forecasts")
MANIFEST = ROOT / "manifest.json"
APP_COPY = Path("app/lib/forward.json")
BUNDLES = Path("artifacts/ship/domains")


def manifest() -> list[dict[str, Any]]:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []


def payload(issue: str) -> bytes:
    from cofire.ship import domains

    doms = {d: json.loads((BUNDLES / d / f"{issue}.json").read_text()) for d in domains.ORDER}
    body = json.dumps({"issue": issue, "domains": doms}, separators=(",", ":"), sort_keys=True).encode()
    # mtime=0 so the same forecast always gzips to the same bytes.
    return gzip.compress(body, compresslevel=9, mtime=0)


def is_append_only(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> bool:
    """`new` keeps every entry of `old`, unchanged and in order, and only adds after them."""
    return len(new) >= len(old) and new[: len(old)] == old


def publish(backfill: bool = False, now: pd.Timestamp | None = None) -> list[dict[str, Any]]:
    from cofire.ship.export import utc_now

    now = utc_now() if now is None else now
    issues = json.loads((BUNDLES / "index.json").read_text())["issues"]
    old = manifest()
    have = {e["issue"] for e in old}
    if not old and not backfill:
        raise RuntimeError("no manifest yet: run the one-time backfill first")
    added = []
    for issue in issues:
        if issue in have:
            continue
        path = ROOT / f"{issue}.json.gz"
        if path.exists():
            raise RuntimeError(f"{path} exists but is not in the manifest; published files are never rewritten")
        data = payload(issue)
        ROOT.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        added.append({"issue": issue, "file": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "published_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "backfilled": bool(backfill)})
    new = old + added
    assert is_append_only(old, new)
    MANIFEST.write_text(json.dumps(new, indent=1) + "\n")
    APP_COPY.write_text(json.dumps([{k: e[k] for k in ("issue", "sha256", "published_at", "backfilled")}
                                    for e in new], indent=1) + "\n")
    return added


if __name__ == "__main__":
    if sys.argv[1] == "publish":
        out = publish(backfill="--backfill" in sys.argv)
        print(f"published {len(out)}: {out[0]['issue'] if out else '-'} to {out[-1]['issue'] if out else '-'}")
    else:
        raise SystemExit(__doc__)
