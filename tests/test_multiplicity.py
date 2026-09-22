"""Multiplicity control, and the rule that a loss is never a discovery."""

from __future__ import annotations

from cofire.model.confirm import benjamini_hochberg, bootstrap_pvalue, event_family, holm


def test_bh_rejects_nothing_when_everything_is_null() -> None:
    assert not any(benjamini_hochberg([0.4, 0.6, 0.8, 0.95], q=0.10))


def test_bh_rejects_a_clear_signal_among_nulls() -> None:
    keep = benjamini_hochberg([0.0001, 0.5, 0.6, 0.7, 0.8], q=0.10)
    assert keep[0] and not any(keep[1:])


def test_bh_is_a_step_up_procedure() -> None:
    """A large p can still be rejected if enough smaller ones are.

    This is what distinguishes BH from a per-hypothesis threshold, and it is
    why BH is more powerful than Bonferroni at the same q.
    """
    pvals = [0.001, 0.002, 0.003, 0.004]
    keep = benjamini_hochberg(pvals, q=0.10)
    assert all(keep), "four consistently small p-values should all be rejected"


def test_holm_stops_at_the_first_failure_in_sorted_order() -> None:
    """Step-down: testing runs in ascending p and halts at the first failure.

    Input order does not matter, only rank. Here 0.06 fails at rank 2, where the
    threshold is 0.10/3 = 0.033, so the 0.07 that follows it must not reject
    even though 0.07 < alpha. That halting is the whole point of the step-down.
    """
    keep = holm([0.001, 0.07, 0.06], alpha=0.10)
    assert keep[0] is True, "0.001 passes 0.10/3"
    assert keep[2] is False, "0.06 fails 0.10/2 and halts the procedure"
    assert keep[1] is False, "0.07 follows the halt and must not reject"


def test_holm_is_more_conservative_than_bh() -> None:
    pvals = [0.02, 0.03, 0.04, 0.05]
    assert sum(holm(pvals, 0.10)) <= sum(benjamini_hochberg(pvals, 0.10))


def test_horizon_variants_share_a_family() -> None:
    assert event_family("d_intensify2_h2") == event_family("d_intensify2_h8")
    assert event_family("d_intensify1_h4") != event_family("d_intensify2_h4")
    assert event_family("f_gt90_h2") == "f_gt90"


def test_pvalue_is_one_when_the_interval_is_missing() -> None:
    """A target with no interval must not enter the procedure with p=0."""
    assert bootstrap_pvalue(float("nan"), float("nan"), 0.5) == 1.0


def test_pvalue_shrinks_as_the_interval_moves_off_zero() -> None:
    wide = bootstrap_pvalue(-0.10, 0.30, 0.10)
    narrow = bootstrap_pvalue(0.08, 0.12, 0.10)
    assert narrow < wide
