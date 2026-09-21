"""A ledger is an audit record: corrections append, they never rewrite.

The ESI entries were charged a flat per-file estimate that measurement later
showed to be 3x too high. The fix must not edit the 1309 entries that were
written at the time, because what makes a ledger worth having is that it says
what was recorded when it was recorded.
"""

from __future__ import annotations

import json

from cofire.model.data.ledger import DownloadLedger


def _ledger(tmp_path) -> DownloadLedger:
    led = DownloadLedger(tmp_path / "ledger.json", budget_bytes=1_000_000)
    led.record("src", "http://example/a", 300_000, "one")
    led.record("src", "http://example/b", 300_000, "two")
    return led


def test_correction_changes_the_total_without_touching_the_entries(tmp_path) -> None:
    led = _ledger(tmp_path)
    before = [t.bytes for t in led._transfers]
    led.add_correction("measured smaller", -400_000, "evidence")
    assert [t.bytes for t in led._transfers] == before, "entries must be untouched"
    assert led.recorded_bytes == 600_000, "the recorded figure stays as written"
    assert led.total_bytes == 200_000, "the total reflects the correction"


def test_correction_frees_real_headroom(tmp_path) -> None:
    """The point of the correction: a mis-estimate must not block a fetch."""
    led = _ledger(tmp_path)
    assert led.remaining_bytes == 400_000
    led.add_correction("measured smaller", -400_000, "evidence")
    assert led.remaining_bytes == 800_000
    assert led.can_afford(700_000), "corrected headroom must be usable"


def test_corrections_persist_with_their_evidence(tmp_path) -> None:
    """A correction without its reasoning is just a smaller number."""
    led = _ledger(tmp_path)
    led.add_correction("flat estimate was 3x high", -400_000, "measured 555136 B per read")
    blob = json.loads((tmp_path / "ledger.json").read_text())
    assert len(blob["corrections"]) == 1
    c = blob["corrections"][0]
    assert c["delta_bytes"] == -400_000
    assert "3x high" in c["reason"]
    assert "555136" in c["evidence"]
    assert "at" in c
    # Both figures are serialised, so a reader can see the adjustment.
    assert blob["recorded_bytes"] == 600_000
    assert blob["total_bytes"] == 200_000


def test_corrections_survive_a_reload(tmp_path) -> None:
    led = _ledger(tmp_path)
    led.add_correction("measured", -400_000, "e")
    again = DownloadLedger(tmp_path / "ledger.json", budget_bytes=1_000_000)
    assert again.total_bytes == 200_000
    assert again.recorded_bytes == 600_000


def test_total_never_goes_below_zero(tmp_path) -> None:
    """An over-large correction must not manufacture budget."""
    led = _ledger(tmp_path)
    led.add_correction("absurd", -99_000_000, "e")
    assert led.total_bytes == 0
    assert led.remaining_bytes == led.budget_bytes
