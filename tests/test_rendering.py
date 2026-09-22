"""The rendering rules are the ones the preregistration fixed before the look.

The point of deciding rendering in advance is that no 2026 result can be read
into a presentation choice afterwards. These tests assert the code implements
the document, and that the export carries the decision with it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cofire.ship.rendering import (
    BASE_RATE,
    HISTORICAL_RANGE,
    INTERVAL,
    RELIABILITY_MAX,
    all_decisions,
    continuous_decisions,
)

DOC = Path("docs/PREREGISTRATION_LOOK3.md")
EXPORT = Path("artifacts/ship/forecast_issues.parquet")


def test_reliability_threshold_matches_the_model_constant() -> None:
    """One threshold, stated in two places, asserted to be one number."""
    from cofire.model.look3 import RELIABILITY_MAX as MODEL_MAX

    assert RELIABILITY_MAX == MODEL_MAX


def test_continuous_rendering_matches_the_preregistration() -> None:
    """Larimer h2 and Pueblo h2/h4/h8 show intervals; Larimer h4/h8 do not."""
    expected = {
        ("larimer", 2): INTERVAL,
        ("larimer", 4): HISTORICAL_RANGE,
        ("larimer", 8): HISTORICAL_RANGE,
        ("pueblo", 2): INTERVAL,
        ("pueblo", 4): INTERVAL,
        ("pueblo", 8): INTERVAL,
    }
    got = {(d.domain, d.horizon): d.state for d in continuous_decisions()}
    assert got == expected


def test_the_document_states_the_same_six() -> None:
    doc = DOC.read_text()
    assert "| larimer | 2 | point forecast plus PID interval |" in doc
    assert "| larimer | 4 | point forecast plus labelled historical week-of-year range |" in doc
    assert "| pueblo | 8 | point forecast plus PID interval |" in doc


def test_every_decision_carries_a_reason() -> None:
    frame = all_decisions()
    assert not frame.empty
    assert frame["reason"].str.len().min() > 20, "a reason must say something"


def test_reliability_failures_render_as_base_rate() -> None:
    """A target that failed the look-3 criterion must not show a per-cell number."""
    rel = pd.read_csv(Path("artifacts/look3/reliability.csv"))
    failed = {
        (str(r["domain"]), str(r["target"]))
        for _, r in rel[rel["reliability"] > RELIABILITY_MAX].iterrows()
    }
    assert failed, "the fixture should contain at least one failure"
    states = {
        (str(r["domain"]), str(r["target"])): str(r["state"])
        for _, r in all_decisions().iterrows()
    }
    for key in failed:
        assert states[key] == BASE_RATE, f"{key} failed reliability but renders {states[key]}"


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_base_rate_targets_are_identical_across_cells() -> None:
    """'Visibly identical across cells' has to be true of the numbers, not the caption."""
    frame = pd.read_parquet(EXPORT)
    checked = 0
    for col in [c for c in frame.columns if c.endswith("_state")]:
        key = col[: -len("_state")]
        pcol = f"{key}_p"
        if pcol not in frame.columns:
            continue
        for dom in ("larimer", "pueblo"):
            m = (frame["domain"] == dom) & (frame[col] == BASE_RATE)
            if not m.any():
                continue
            vals = frame.loc[m, pcol].to_numpy(dtype=float)
            assert np.nanstd(vals) < 1e-12, f"{dom} {key} varies across cells"
            checked += 1
    assert checked > 0


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_the_export_reads_no_realized_outcome() -> None:
    """The structural guarantee: the columns are not there to be read."""
    from cofire.ship.export import realized_columns

    frame = pd.read_parquet(EXPORT)
    assert realized_columns(frame) == []


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_the_export_covers_every_issue_to_the_last(  ) -> None:
    frame = pd.read_parquet(EXPORT)
    assert pd.Timestamp(frame["time"].max()) == pd.Timestamp("2026-09-22")
    assert set(frame["domain"].unique()) == {"larimer", "pueblo"}


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_every_shown_target_has_a_state_and_reason() -> None:
    frame = pd.read_parquet(EXPORT)
    for col in [c for c in frame.columns if c.endswith("_p")]:
        key = col[: -len("_p")]
        assert f"{key}_state" in frame.columns, f"{key} has no rendering state"
        assert frame[f"{key}_reason"].notna().all(), f"{key} has rows without a reason"
