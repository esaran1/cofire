"""Stage 1's online recalibration passes the delayed-feedback gate, and fails
it the moment the delay is shortened."""

from __future__ import annotations

import pytest
from cofire.v12 import recal
from research.v12 import gate

ONLINE = {k: v for k, v in recal.VARIANTS.items() if isinstance(v, recal.Online)}


@pytest.mark.parametrize("name", sorted(ONLINE))
@pytest.mark.parametrize("h", [2, 4, 8])
def test_every_online_variant_passes_with_the_real_delay(name: str, h: int) -> None:
    r = gate.check(name, ONLINE[name], h, delay=h)
    assert r.passed, f"{name} h{h} leaked at probe {r.first_leak}"


@pytest.mark.parametrize("name", sorted(ONLINE))
@pytest.mark.parametrize("delay", [0, 1])
def test_the_gate_fails_a_variant_whose_delay_is_removed_or_short(name: str, delay: int) -> None:
    # h = 2: delay 1 uses the week one before it is resolved; delay 0 uses its own week.
    r = gate.check(name, ONLINE[name], 2, delay=delay)
    assert not r.passed and r.leaking_probes
