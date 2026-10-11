"""An adopted arm changes only the issues published after its adoption."""

from __future__ import annotations

import numpy as np
import pandas as pd
from cofire.v12 import live, recal


def test_published_issues_keep_configuration_a_and_new_ones_get_the_arm() -> None:
    entries = [{"domain": "larimer", "target": "d_improve1_h4", "horizon": 4, "a": 0.3, "b": 0.9,
                "applies_from": "2026-10-13"}]
    times = pd.Series(pd.to_datetime(["2026-10-06", "2026-10-06", "2026-10-13", "2026-10-20"]))
    p = np.array([0.1, 0.4, 0.1, 0.4])
    out = live.apply("larimer", "d_improve1_h4", 4, times, p, entries)
    assert np.array_equal(out[:2], p[:2])
    assert np.allclose(out[2:], recal.apply((0.3, 0.9), p[2:]))
    # Other pairs, domains and horizons are never touched.
    for args in (("larimer", "d_improve1_h8", 8), ("pueblo", "d_improve1_h4", 4), ("larimer", "d_ge2_h4", 4)):
        assert np.array_equal(live.apply(*args, times, p, entries), p)


def test_no_live_file_means_configuration_a_everywhere() -> None:
    times = pd.Series(pd.to_datetime(["2026-10-20"]))
    assert np.array_equal(live.apply("larimer", "d_improve1_h4", 4, times, np.array([0.2]), []), np.array([0.2]))
