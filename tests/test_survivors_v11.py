"""The five-domain survivor table keeps the current claims and the stated rules."""

from __future__ import annotations

import json

import pandas as pd
from cofire.ship import survivors_v11

T = pd.read_csv(survivors_v11.OUT / "survivors_v11.csv")


def test_every_current_survivor_still_survives() -> None:
    cur = T[T["current_survivor"]]
    assert len(cur) == 11 and cur["survivor"].all()


def test_a_survivor_meets_every_condition() -> None:
    s = T[T["survivor"]]
    assert (s["estimable"] & s["ci_above_zero"] & s["bh_reject"] & s["holm_reject"]).all()
    assert (s["n_positive_weeks"] >= 12).all() and (s["paired_lo"] > 0).all()


def test_agreement_rule_matches_its_statement() -> None:
    for tg, g in T.groupby("target"):
        e = g[g["estimable"]]
        expected = bool(len(e) and e["survivor"].all() and e["survivor"].sum() >= 2)
        assert (g["target_agrees_across_domains"] == expected).all(), tg


def test_new_domain_rendering_follows_estimability_and_reliability() -> None:
    n = T[T["domain"].isin(["denver", "upper_south_platte", "dillon"])]
    prob = n[n["render"] == "probability"]
    assert (prob["estimable"] & (prob["reliability_cell"] <= survivors_v11.RELIABILITY_MAX)).all()
    assert (n.loc[~n["estimable"], "render"] == "base_rate").all()


def test_summary_is_consistent_with_the_table() -> None:
    s = json.loads((survivors_v11.OUT / "survivors_v11_summary.json").read_text())
    assert s["n_survivors"] == int(T["survivor"].sum()) == 21
    assert s["current_survivors_hold"] == 11
