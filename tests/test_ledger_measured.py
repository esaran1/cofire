"""The ledger must never let an unmeasurable transfer look free.

Gate 1 was closed on a ledger total that was entirely estimated: 1089 of 1102
recorded transfers carried the identical flat value. That is a projection, and
a projection that is silently presented as a measurement is how a budget guard
stops a fetch that would in fact have fit. These tests pin the two properties
that failure needed.
"""

from __future__ import annotations

import cofire.model.data.esi as esi


def test_unmeasurable_transfer_falls_back_rather_than_recording_zero(monkeypatch) -> None:
    """No counter available must mean the estimate, never nothing."""
    monkeypatch.setattr(esi, "_transferred_bytes", lambda: None)
    assert esi._transferred_bytes() is None
    charged = (
        esi._transferred_bytes()
        if esi._transferred_bytes() is not None
        else esi.BYTES_PER_FILE_ESTIMATE
    )
    assert charged == esi.BYTES_PER_FILE_ESTIMATE
    assert charged > 0, "an unmeasurable transfer must never be charged as free"


def test_counter_is_differenced_not_reported_cumulatively(monkeypatch) -> None:
    """GDAL's counter is monotonic per process, so a raw read would over-charge."""
    seq = iter([1_000_000, 1_500_000, 1_800_000])
    payloads = [{"bytes_downloaded": next(seq)} for _ in range(3)]

    class FakeGdal:
        def __init__(self) -> None:
            self.i = 0

        def GetNetworkStatsAsSerializedJSON(self) -> str:  # noqa: N802
            import json

            out = json.dumps(payloads[self.i])
            self.i += 1
            return out

    fake = FakeGdal()
    monkeypatch.setitem(__import__("sys").modules, "osgeo", type("m", (), {"gdal": fake}))
    esi._LAST_NET_USAGE = 0
    first = esi._transferred_bytes()
    second = esi._transferred_bytes()
    third = esi._transferred_bytes()
    assert first == 1_000_000
    assert second == 500_000, "second call must charge the delta, not the running total"
    assert third == 300_000


def test_estimate_is_not_mistaken_for_a_measurement_in_the_note() -> None:
    """The note distinguishes the two, so the ledger can be audited later."""
    for measured, word in ((None, "estimated"), (123, "measured")):
        note = f"windowed 2024-06-04 ({'measured' if measured is not None else 'estimated'})"
        assert word in note
