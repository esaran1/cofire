"""The leakage audit must be executable, not prose."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from cofire.model.data.availability import (
    REGISTRY,
    Reprocessing,
    SourceAvailability,
    assert_no_future_reads,
    audit_table,
    max_usable_week,
)


def test_latency_pushes_availability_past_the_valid_date() -> None:
    """A value for week t is not readable on day t."""
    av = REGISTRY["esi_4wk"]
    wk = date(2024, 6, 4)
    assert av.available_at(wk) > wk


def test_unknown_reprocessing_adds_a_guard_week() -> None:
    known = SourceAvailability("k", latency_days=2, reprocessing=Reprocessing.APPEND_ONLY)
    unknown = SourceAvailability("u", latency_days=2, reprocessing=Reprocessing.UNKNOWN)
    wk = date(2024, 6, 4)
    assert known.guard_weeks == 0
    assert unknown.guard_weeks == 1
    assert unknown.available_at(wk) - known.available_at(wk) == timedelta(weeks=1)


def test_guard_can_be_disabled_so_the_ablation_can_price_it() -> None:
    """The amendment requires the guard's cost to be measurable."""
    av = REGISTRY["esi_4wk"]
    wk = date(2024, 6, 4)
    assert av.available_at(wk, apply_guard=False) < av.available_at(wk, apply_guard=True)


def test_assert_no_future_reads_rejects_a_value_from_the_issue_week() -> None:
    """The exact leak this guards: reading this week's ESI at this week's issue."""
    issue = date(2024, 6, 4)
    with pytest.raises(AssertionError, match="would not have been readable"):
        assert_no_future_reads("esi_4wk", [issue], issue)


def test_assert_no_future_reads_accepts_a_sufficiently_old_value() -> None:
    issue = date(2024, 6, 4)
    old = issue - timedelta(days=30)
    assert_no_future_reads("esi_4wk", [old], issue)  # must not raise


def test_assert_no_future_reads_names_the_earliest_offender() -> None:
    issue = date(2024, 6, 4)
    weeks = [issue, issue - timedelta(days=1), issue - timedelta(days=2)]
    with pytest.raises(AssertionError) as exc:
        assert_no_future_reads("esi_4wk", weeks, issue)
    assert str(min(weeks)) in str(exc.value)


def test_max_usable_week_is_consistent_with_the_assertion() -> None:
    """Whatever max_usable_week returns must itself pass the assertion."""
    issue = date(2024, 6, 4)
    for key in REGISTRY:
        wk = max_usable_week(key, issue)
        assert_no_future_reads(key, [wk], issue)


def test_max_usable_week_is_tight() -> None:
    """One week later must fail, or the bound is loose and costing skill."""
    issue = date(2024, 6, 4)
    for key in REGISTRY:
        wk = max_usable_week(key, issue) + timedelta(days=1)
        with pytest.raises(AssertionError):
            assert_no_future_reads(key, [wk], issue)


def test_unknown_sources_are_marked_as_such() -> None:
    """ESI is empirically reprocessed, so it must not claim to be immutable.

    Measured: one sampled ESI file was last modified 273 days after its valid
    week. See artifacts/data/reprocessing_probe.json.
    """
    assert REGISTRY["esi_4wk"].reprocessing is Reprocessing.UNKNOWN
    assert REGISTRY["esi_12wk"].reprocessing is Reprocessing.UNKNOWN


def test_audit_table_is_generated_and_complete() -> None:
    rows = audit_table()
    assert len(rows) == len(REGISTRY)
    for r in rows:
        assert r["readable_from"] > r["example_valid_week"]
        assert set(r).issuperset({"latency_days", "reprocessing", "guard_weeks", "note"})


def test_unknown_source_key_raises_rather_than_passing_silently() -> None:
    with pytest.raises(KeyError):
        assert_no_future_reads("not_a_source", [date(2024, 1, 2)], date(2024, 6, 4))
