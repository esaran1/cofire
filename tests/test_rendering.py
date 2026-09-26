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


def test_continuous_rendering_follows_the_preregistration_and_the_audit() -> None:
    """Pre-registered states, unless the real-time interval audit says otherwise.

    The look-3 interval tests passed under same-week updates a real forecaster
    cannot make. Where the real-time audit finds the intervals invalid, the
    pre-registered consequence of a failed interval test applies to every
    horizon: `uncalibrated`, with the audit's reason.
    """
    import json

    audit = Path("artifacts/audit/pid_realtime.json")
    got = {(d.domain, d.horizon): d for d in continuous_decisions()}
    if audit.exists() and not json.loads(audit.read_text())["verdict"]["realtime_valid"]:
        assert {d.state for d in got.values()} == {"uncalibrated"}
        assert all("real-time" in d.reason for d in got.values())
        return
    expected = {
        ("larimer", 2): INTERVAL,
        ("larimer", 4): HISTORICAL_RANGE,
        ("larimer", 8): HISTORICAL_RANGE,
        ("pueblo", 2): INTERVAL,
        ("pueblo", 4): INTERVAL,
        ("pueblo", 8): INTERVAL,
    }
    assert {k: d.state for k, d in got.items()} == expected


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
def test_base_rate_targets_are_identical_across_cells_within_an_issue() -> None:
    """One number per county and issue, and it moves with the season.

    The earlier version of this test checked identity across every issue at
    once, which a single year-round number passes. That is how a base rate
    computed as the average of a year of model predictions got through.
    """
    frame = pd.read_parquet(EXPORT)
    checked = 0
    for col in [c for c in frame.columns if c.endswith("_state")]:
        key = col[: -len("_state")]
        pcol = f"{key}_p"
        if pcol not in frame.columns:
            continue
        sel = frame[frame[col] == BASE_RATE]
        if sel.empty:
            continue
        spread = sel.groupby(["domain", "time"])[pcol].agg(lambda v: float(np.nanstd(v)))
        assert (spread < 1e-12).all(), f"{key} varies across cells within an issue"
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_base_rate_is_the_training_record_rate_for_the_season() -> None:
    """The shown base rate equals how often the event happened, not a model mean.

    Recomputed independently from the training split for one target and issue.
    On 22 September the shown value for Larimer D2-or-worse in 4 weeks was 0.644
    before this was fixed; the record for late September says about 0.11.
    """
    from cofire.model.calibration_stages import domain_frame
    from cofire.model.erc_pct import window_weeks
    from cofire.model.targets import HORIZONS, all_event_targets

    frame, st = domain_frame("larimer")
    frame = all_event_targets(frame, HORIZONS)
    train = frame[frame["time"] <= pd.Timestamp(st.train_end)]
    issue = pd.Timestamp("2026-09-22")
    woy = train["time"].dt.isocalendar().week.astype(int).clip(1, 52)
    y = pd.to_numeric(train.loc[woy.isin(window_weeks(issue.isocalendar().week)), "d_ge2_h4"], errors="coerce")
    expected = float(y.dropna().mean())

    exp = pd.read_parquet(EXPORT)
    row = exp[(exp["domain"] == "larimer") & (exp["time"] == issue)].iloc[0]
    assert row["d_ge2_h4_state"] == BASE_RATE
    # float32 storage in the export; a probability needs no more than 1e-6.
    assert abs(float(row["d_ge2_h4_p"]) - expected) < 1e-6


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_the_typical_range_uses_real_percentiles() -> None:
    """Bounds must be ordered and inside 0 to 100, not median plus or minus half a width."""
    frame = pd.read_parquet(EXPORT)
    for h in (2, 4, 8):
        lo, hi = frame[f"erc_pct_h{h}_clim_lo"], frame[f"erc_pct_h{h}_clim_hi"]
        assert (lo < hi).all() and (lo >= 0).all() and (hi <= 100).all()


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


def test_hindcast_criteria_labels_state_the_recorded_thresholds() -> None:
    """The plain-language test names must carry the thresholds the look used.

    The Hindcast page rewrites each pre-registered test in plain words, which
    means the threshold is written there as well as in the artifact. If the two
    ever disagree the page describes a test that was not run.
    """
    import json
    import re

    facts = json.loads(Path("app/lib/facts.json").read_text())
    page = Path("app/app/hindcast/page.tsx").read_text()
    block = page[page.index("const CRITERIA") : page.index("};", page.index("const CRITERIA"))]
    labels = dict(re.findall(r'"(\d)":\s*"([^"]+)"', block))
    by_test = facts["look3"]["by_test"]
    assert set(labels) == set(by_test), "every recorded test needs a label, and no more"
    for k, t in by_test.items():
        nums = re.findall(r"\d+(?:\.\d+)?", t["threshold"])
        for n in nums:
            want = f"{float(n):.2f}".rstrip("0").rstrip(".") if "." in n else n
            assert want in labels[k] or n in labels[k] or f"{float(n):.2f}" in labels[k], (
                f"test {k} threshold {t['threshold']!r} is not stated in {labels[k]!r}"
            )
