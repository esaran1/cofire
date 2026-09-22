"""The download budget must be a hard limit, not a warning."""

from __future__ import annotations

from pathlib import Path

import pytest
from cofire.model.data.ledger import BudgetExceeded, DownloadLedger


def _ledger(tmp_path: Path, budget: int = 1_000) -> DownloadLedger:
    return DownloadLedger(tmp_path / "ledger.json", budget_bytes=budget)


def test_refuses_transfer_over_budget(tmp_path: Path) -> None:
    led = _ledger(tmp_path, budget=1_000)
    led.record("a", "http://x/1", 900)
    with pytest.raises(BudgetExceeded):
        led.check("http://x/2", "a", assume_bytes=200)


def test_allows_transfer_that_exactly_fits(tmp_path: Path) -> None:
    led = _ledger(tmp_path, budget=1_000)
    led.record("a", "http://x/1", 900)
    assert led.check("http://x/2", "a", assume_bytes=100) == 100


def test_totals_and_remaining_track_records(tmp_path: Path) -> None:
    led = _ledger(tmp_path, budget=1_000)
    led.record("a", "http://x/1", 300)
    led.record("b", "http://x/2", 250)
    assert led.total_bytes == 550
    assert led.remaining_bytes == 450


def test_series_projection_refuses_when_the_rest_would_not_fit(tmp_path: Path) -> None:
    """The guarantee must hold even when the server declares no size.

    Measure the first file, then project the remainder before continuing.
    """
    led = _ledger(tmp_path, budget=1_000)
    led.record("series", "http://x/0", 200)  # first file, measured
    assert led.project_series("series", per_file_bytes=200, n_remaining=3) is True  # 600 more fits
    assert led.project_series("series", per_file_bytes=200, n_remaining=5) is False  # 1000 does not


def test_ledger_persists_across_instances(tmp_path: Path) -> None:
    p = tmp_path / "ledger.json"
    a = DownloadLedger(p, budget_bytes=5_000)
    a.record("src", "http://x/1", 1_234)
    b = DownloadLedger(p, budget_bytes=5_000)
    assert b.total_bytes == 1_234
    assert b.budget_bytes == 5_000


def test_undeclared_size_returns_none_rather_than_raising(tmp_path: Path) -> None:
    """A missing Content-Length must not be silently treated as zero cost."""
    led = _ledger(tmp_path, budget=1_000)
    # assume_bytes=None and an unreachable host: head_size returns None.
    assert led.check("http://127.0.0.1:9/nonexistent", "x") is None


def test_summary_reports_per_source(tmp_path: Path) -> None:
    led = _ledger(tmp_path, budget=10_000)
    led.record("esi", "http://x/1", 3_000)
    led.record("eddi", "http://x/2", 1_000)
    s = led.summary()
    assert s["transfers"] == 2
    assert s["by_source_mb"]["esi"] >= s["by_source_mb"]["eddi"]
    assert s["pct_used"] == pytest.approx(40.0, abs=0.1)
