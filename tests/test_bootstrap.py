from __future__ import annotations

import numpy as np
from cofire.model.uncertainty.bootstrap import bootstrap_interval


def test_bootstrap_coverage_on_synthetic() -> None:
    rng = np.random.default_rng(1)
    resid = rng.normal(0, 1, size=500)
    point = 10.0
    hits = 0
    n = 200
    y = point + rng.choice(resid, size=n, replace=True)
    for yi in y:
        lo, hi = bootstrap_interval(point, resid, 300, rng, q=0.90)
        hits += int(lo <= yi <= hi)
    cover = hits / n
    assert 0.80 <= cover <= 0.98
