"""Probabilistic fields must degrade to null, never crash the card.

A null `why[].value` once took down an entire Place Card while the endpoint
still returned 200 and tsc still passed. The v1 probabilistic outputs are
absent far more often than SHAP values are: a target is skipped where the event
never occurs in training, and fire targets have no Markov reference at all. So
the absent case is the common case and it is pinned here.
"""

from __future__ import annotations

import json

from cofire.model.export import _finite


def _horizon_entry(row: dict[str, object], h: int) -> dict[str, object]:
    """The v1 block of the horizon payload, as export.py builds it."""
    return {
        "p_intensify": {
            "value": _finite(row.get(f"d_intensify1_h{h}_hat")),
            "baseline": _finite(row.get(f"d_intensify1_h{h}_markov")),
        },
        "p_d2plus": {
            "value": _finite(row.get(f"d_ge2_h{h}_hat")),
            "baseline": _finite(row.get(f"d_ge2_h{h}_markov")),
        },
        "p_fire_gt90": {"value": _finite(row.get(f"f_gt90_h{h}_hat")), "baseline": None},
    }


def test_present_probabilities_carry_their_baseline() -> None:
    row = {
        "d_intensify1_h4_hat": 0.31,
        "d_intensify1_h4_markov": 0.18,
        "d_ge2_h4_hat": 0.44,
        "d_ge2_h4_markov": 0.40,
        "f_gt90_h4_hat": 0.12,
    }
    e = _horizon_entry(row, 4)
    assert e["p_intensify"] == {"value": 0.31, "baseline": 0.18}
    assert e["p_d2plus"] == {"value": 0.44, "baseline": 0.40}


def test_absent_probabilities_serialise_as_null_not_nan() -> None:
    """NaN is not valid JSON and would break the client parse."""
    e = _horizon_entry({}, 4)
    text = json.dumps(e)
    assert "NaN" not in text, "NaN is not valid JSON"
    assert json.loads(text)["p_intensify"]["value"] is None


def test_fire_has_no_markov_baseline() -> None:
    """A USDM transition matrix cannot forecast ERC exceedance.

    Filling this with some other baseline and still calling it Markov is the
    substitution that makes a results table untrustworthy.
    """
    e = _horizon_entry({"f_gt90_h4_hat": 0.2}, 4)
    assert e["p_fire_gt90"]["baseline"] is None
    assert e["p_fire_gt90"]["value"] == 0.2


def test_a_probability_without_its_baseline_still_renders() -> None:
    """Half-present data is the case that crashed the card before."""
    e = _horizon_entry({"d_intensify1_h4_hat": 0.5}, 4)
    assert e["p_intensify"]["value"] == 0.5
    assert e["p_intensify"]["baseline"] is None
    json.dumps(e)  # must not raise
