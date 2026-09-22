"""The shipping path serves frozen choices and never reselects."""

from __future__ import annotations

import json

import numpy as np
from cofire.model.shipping import ShippingChoice, load, save
from cofire.model.uncertainty.shipping_pid import longest_miss_run, run_reference_pid


def test_choices_round_trip(tmp_path) -> None:
    c = [ShippingChoice("f_gt90_h4", 4, "transition", True, 0.13, 0.002, 0.001)]
    save(c, out_dir=tmp_path)
    back = load(out_dir=tmp_path)
    assert back[("f_gt90_h4", 4)].family == "transition"
    assert back[("f_gt90_h4", 4)].pooled is True


def test_every_shipped_choice_is_an_empirical_model() -> None:
    """No ML arm may reach the serving path."""
    from pathlib import Path

    p = Path("artifacts/shipping/choices.json")
    if not p.exists():
        return
    allowed = {"markov", "transition", "damped"}
    for row in json.loads(p.read_text()):
        assert row["family"] in allowed, f"{row['target']} ships {row['family']}"


def test_drought_targets_ship_markov() -> None:
    from pathlib import Path

    p = Path("artifacts/shipping/choices.json")
    if not p.exists():
        return
    for row in json.loads(p.read_text()):
        if row["target"].startswith("d_"):
            assert row["family"] == "markov", f"{row['target']} ships {row['family']}"


def test_longest_miss_run_counts_consecutive_failures() -> None:
    """Average coverage can hide a long block of misses; this is the check."""
    assert longest_miss_run(np.array([1, 1, 0, 0, 0, 1, 0], dtype=bool)) == 3
    assert longest_miss_run(np.ones(10, dtype=bool)) == 0
    assert longest_miss_run(np.zeros(5, dtype=bool)) == 5


def test_reference_pid_holds_nominal_on_a_stationary_stream() -> None:
    rng = np.random.default_rng(0)
    s = np.abs(rng.normal(size=1500))
    out = run_reference_pid(s)
    assert 0.85 < out.coverage < 0.95, f"held {out.coverage:.3f}"
    assert out.longest_miss_run < 100


def test_reference_pid_recovers_from_a_level_shift() -> None:
    """The property that made ACI unusable at h8."""
    rng = np.random.default_rng(1)
    s = np.concatenate([np.abs(rng.normal(size=600)), np.abs(rng.normal(scale=5.0, size=600))])
    out = run_reference_pid(s)
    late = out.covered[800:]
    assert late.mean() > 0.75, f"coverage after the shift was {late.mean():.3f}"
