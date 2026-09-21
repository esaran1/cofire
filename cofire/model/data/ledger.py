"""Network download budget ledger. INTENDED FOR HAND-REWRITE.

Every byte fetched in a session passes through here. The budget is a hard
limit, not a warning: a transfer that would push the cumulative total past it is
refused before a single byte moves.

How the projection works
------------------------
A HEAD request gives Content-Length for most servers, and that is checked
against the remaining budget directly. Where Content-Length is absent (chunked
transfer, dynamic subsetting endpoints), the caller fetches the first file of a
series, records its actual size with `record`, and then calls `project_series`
to ask whether the remaining N-1 files of the same size would fit. That keeps
the guarantee even when the server will not declare a size up front.

Clipping a full-extent file to the domain on arrival does not refund anything.
The bytes crossed the wire; the budget is about the wire, not about disk.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from cofire.model.http import USER_AGENT

LOGGER = logging.getLogger("cofire.data.ledger")

# Hard session budget, all sources combined.
DEFAULT_BUDGET_BYTES = 2_500_000_000  # 2.5 GB

# A HEAD that takes longer than this is treated as "size unknown".
HEAD_TIMEOUT_S = 20


class BudgetExceeded(RuntimeError):
    """Raised before a transfer that would breach the budget."""


@dataclass
class Transfer:
    source: str
    url: str
    bytes: int
    timestamp: str
    note: str = ""


class DownloadLedger:
    """Append-only record of bytes transferred, with a hard ceiling."""

    def __init__(self, path: Path, budget_bytes: int = DEFAULT_BUDGET_BYTES) -> None:
        self.path = path
        self.budget_bytes = budget_bytes
        self._transfers: list[Transfer] = []
        # Appended adjustments to the recorded totals. A ledger is an audit
        # record, so a mis-estimate is corrected by appending a correction, not
        # by editing the entries that were written at the time.
        self._corrections: list[dict[str, object]] = []
        self._load()

    # ---------------------------------------------------------------- state

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            blob = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            LOGGER.warning("ledger at %s is unreadable; starting a new one", self.path)
            return
        self.budget_bytes = int(blob.get("budget_bytes", self.budget_bytes))
        self._transfers = [Transfer(**t) for t in blob.get("transfers", [])]
        self._corrections = list(blob.get("corrections", []))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "budget_bytes": self.budget_bytes,
                    "recorded_bytes": self.recorded_bytes,
                    "correction_bytes": self.correction_bytes,
                    "total_bytes": self.total_bytes,
                    "remaining_bytes": self.remaining_bytes,
                    "corrections": self._corrections,
                    "transfers": [asdict(t) for t in self._transfers],
                },
                indent=2,
            )
        )

    @property
    def recorded_bytes(self) -> int:
        """What the transfer entries say, exactly as they were written."""
        return sum(t.bytes for t in self._transfers)

    @property
    def correction_bytes(self) -> int:
        """Net adjustment from appended corrections. Usually negative."""
        total = 0
        for c in self._corrections:
            raw = c.get("delta_bytes", 0)
            total += int(raw) if isinstance(raw, (int, float, str)) else 0
        return total

    @property
    def total_bytes(self) -> int:
        """The best current estimate of true spend: recorded plus corrections."""
        return max(0, self.recorded_bytes + self.correction_bytes)

    def add_correction(self, reason: str, delta_bytes: int, evidence: str = "") -> None:
        """Append a correction to the totals, leaving the entries untouched.

        Used when a per-file estimate is later measured and found wrong. The
        original entries stay exactly as recorded, which is what makes the
        ledger an audit record rather than a running guess.
        """
        self._corrections.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "reason": reason,
                "delta_bytes": int(delta_bytes),
                "evidence": evidence,
            }
        )
        self._save()

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.budget_bytes - self.total_bytes)

    # ------------------------------------------------------------- checking

    def head_size(self, url: str) -> int | None:
        """Content-Length from a HEAD request, or None when undeclared."""
        try:
            r = requests.head(
                url, allow_redirects=True, timeout=HEAD_TIMEOUT_S, headers={"User-Agent": USER_AGENT}
            )
            if r.status_code >= 400:
                return None
            cl = r.headers.get("Content-Length")
            return int(cl) if cl is not None else None
        except (requests.RequestException, ValueError):
            return None

    def can_afford(self, n_bytes: int) -> bool:
        return self.total_bytes + max(0, n_bytes) <= self.budget_bytes

    def check(self, url: str, source: str, *, assume_bytes: int | None = None) -> int | None:
        """Refuse a transfer that would breach the budget.

        Returns the projected size when known, None when the server declines to
        declare one. A None return is not permission to ignore the budget: the
        caller must `record` the real size afterwards, and use `project_series`
        before continuing a multi-file series.
        """
        projected = assume_bytes if assume_bytes is not None else self.head_size(url)
        if projected is None:
            LOGGER.info("%s: size undeclared for %s; will measure after transfer", source, url[:90])
            return None
        if not self.can_afford(projected):
            raise BudgetExceeded(
                f"{source}: {projected / 1e6:.1f} MB would exceed the "
                f"{self.budget_bytes / 1e9:.2f} GB budget "
                f"(used {self.total_bytes / 1e6:.1f} MB)"
            )
        return projected

    def project_series(self, source: str, per_file_bytes: int, n_remaining: int) -> bool:
        """Would n_remaining more files of this size fit? Used when the server
        gives no Content-Length: measure file one, then project the rest."""
        projected = per_file_bytes * max(0, n_remaining)
        ok = self.can_afford(projected)
        if not ok:
            LOGGER.warning(
                "%s: projected %.1f MB for %s more files exceeds the remaining %.1f MB",
                source,
                projected / 1e6,
                n_remaining,
                self.remaining_bytes / 1e6,
            )
        return ok

    # ------------------------------------------------------------ recording

    def record(self, source: str, url: str, n_bytes: int, note: str = "") -> None:
        self._transfers.append(
            Transfer(
                source=source,
                url=url,
                bytes=int(n_bytes),
                timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
                note=note,
            )
        )
        self._save()

    def record_file(self, source: str, url: str, path: Path, note: str = "") -> int:
        n = path.stat().st_size if path.exists() else 0
        self.record(source, url, n, note)
        return n

    # -------------------------------------------------------------- report

    def summary(self) -> dict[str, Any]:
        by_source: dict[str, int] = {}
        for t in self._transfers:
            by_source[t.source] = by_source.get(t.source, 0) + t.bytes
        return {
            "budget_gb": round(self.budget_bytes / 1e9, 3),
            "used_mb": round(self.total_bytes / 1e6, 1),
            "remaining_mb": round(self.remaining_bytes / 1e6, 1),
            "pct_used": round(100 * self.total_bytes / max(1, self.budget_bytes), 1),
            "transfers": len(self._transfers),
            "by_source_mb": {k: round(v / 1e6, 1) for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])},
        }

    def report(self) -> str:
        s = self.summary()
        lines = [
            f"Download budget: {s['used_mb']} MB of {s['budget_gb']} GB used "
            f"({s['pct_used']}%), {s['remaining_mb']} MB remaining, {s['transfers']} transfers."
        ]
        for src, mb in s["by_source_mb"].items():
            lines.append(f"  {src}: {mb} MB")
        return "\n".join(lines)


_LEDGER: DownloadLedger | None = None


def get_ledger(path: Path | None = None, budget_bytes: int = DEFAULT_BUDGET_BYTES) -> DownloadLedger:
    """Process-wide ledger. One budget per session, shared by every source."""
    global _LEDGER
    if _LEDGER is None or path is not None:
        _LEDGER = DownloadLedger(path or Path("data/ledger.json"), budget_bytes)
    return _LEDGER
