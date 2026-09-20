from __future__ import annotations

import numpy as np
from cofire.model.conformal import aci_update, ordinal_set, softmax, split_conformal_qhat


def test_conformal_coverage_on_synthetic() -> None:
    rng = np.random.default_rng(2026)
    y = rng.normal(0, 1, size=2000)
    yhat = y + rng.normal(0, 0.3, size=2000)
    resid = y - yhat
    q = split_conformal_qhat(resid, 0.10)
    cover = np.mean(np.abs(resid) <= q)
    assert abs(cover - 0.90) < 0.03


def test_aci_alpha_dynamics() -> None:
    a = 0.10
    up = aci_update(a, missed=True)
    down = aci_update(a, missed=False)
    assert up < a  # miss → alpha decreases → wider next interval via our scaling
    assert down > a


def test_ordinal_set_contains_top_class() -> None:
    scores = softmax(np.array([0.1, 0.2, 3.0, 0.2, 0.1]))
    s = ordinal_set(scores, alpha=0.1)
    assert 2 in s
    assert min(s) >= 0 and max(s) <= 4
