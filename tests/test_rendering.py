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
    """A fire fallback is one number per area and issue; a drought one is no number.

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
        if key.startswith("d_"):
            # Drought targets that failed their check show no number at all.
            assert sel[pcol].isna().all(), f"{key} shows a number in the base-rate state"
            checked += 1
            continue
        spread = sel.groupby(["domain", "time"])[pcol].agg(lambda v: float(np.nanstd(v)))
        assert (spread < 1e-12).all(), f"{key} varies across cells within an issue"
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_base_rate_is_the_training_record_rate_for_the_season() -> None:
    """The shown base rate is how often the event happened from the same category.

    Recomputed independently from the training split for one target and issue.
    It was once the mean of the model's own predictions (0.644), then the
    unconditional seasonal rate (0.11), which ignored that most of Larimer was
    already in D2 or D3.
    """
    from cofire.model.calibration_stages import domain_frame
    from cofire.model.erc_pct import window_weeks
    from cofire.model.targets import HORIZONS, all_event_targets

    # The training feature store is built locally and not committed, so a clean
    # checkout (CI) has the export but nothing to recompute the rate from.
    try:
        frame, st = domain_frame("larimer")
    except (KeyError, SystemExit):
        pytest.skip("training feature store not built in this checkout")
    if frame.empty:
        pytest.skip("training feature store not built in this checkout")
    frame = all_event_targets(frame, HORIZONS)
    train = frame[frame["time"] <= pd.Timestamp(st.train_end)]
    exp = pd.read_parquet(EXPORT)
    issue = pd.Timestamp(exp["time"].max())
    row = exp[(exp["domain"] == "larimer") & (exp["time"] == issue)].iloc[0]
    assert row["d_ge2_h4_state"] == BASE_RATE
    # The card shows no number for a drought target that failed its check; the
    # recorded rate is the one among training cell-weeks in the same category,
    # within +/- 3 weeks of the issue (cofire.ship.export.conditional_base_rate).
    assert pd.isna(row["d_ge2_h4_p"])
    woy = train["time"].dt.isocalendar().week.astype(int).clip(1, 52)
    same = train["usdm"].round() == round(float(row["usdm"]))
    m = same & woy.isin(window_weeks(issue.isocalendar().week))
    if train.loc[m, "time"].nunique() < 8:
        m = same
    expected = float(pd.to_numeric(train.loc[m, "d_ge2_h4"], errors="coerce").dropna().mean())
    # float32 storage in the export; a probability needs no more than 1e-6.
    assert abs(float(row["d_ge2_h4_base_rate"]) - expected) < 1e-6


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
    times = sorted(pd.to_datetime(frame["time"]).unique())
    # Weekly and unbroken from the first 2026 issue to the last complete one.
    assert pd.Timestamp(times[0]) == pd.Timestamp("2026-01-06")
    assert all((b - a) == pd.Timedelta(weeks=1) for a, b in zip(times, times[1:], strict=False))
    assert set(frame["domain"].unique()) == {"denver", "upper_south_platte", "dillon", "larimer", "pueblo"}
    # Every domain carries every issue, so the app's issue list holds everywhere.
    assert frame.groupby("domain")["time"].nunique().nunique() == 1


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_no_issue_is_emitted_before_its_inputs_were_published() -> None:
    frame = pd.read_parquet(EXPORT)
    lag = pd.to_datetime(frame["available_at"]) - pd.to_datetime(frame["time"])
    assert (lag == pd.Timedelta(days=2, hours=13, minutes=30)).all()


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_no_issue_has_a_missing_drought_map_coded_as_none() -> None:
    """The 2026-09-22 fault: a week without its USDM map read as "none" everywhere.

    A domain's mean category collapsing to zero for one week while the weeks
    around it are in drought is that fault, not weather: USDM moves one
    category at a time.
    """
    frame = pd.read_parquet(EXPORT)
    m = frame.groupby(["domain", "time"])["usdm"].mean().unstack(0).sort_index()
    for dom in m.columns:
        s = m[dom].to_numpy()
        for i in range(1, len(s)):
            assert not (s[i] == 0 and s[i - 1] >= 1), f"{dom}: USDM drops to 0 at {m.index[i]}"


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


@pytest.mark.skipif(not EXPORT.exists(), reason="export not built")
def test_no_drought_number_describes_an_impossible_move() -> None:
    """USDM runs 0 to 4, so some moves cannot happen from some categories.

    A fallback rate that ignored the current category showed, for example, a 6%
    chance of worsening two categories from D3.
    """
    import numpy as np

    e = pd.read_parquet(EXPORT)
    c = e["usdm"].round()
    for h in (2, 4, 8):
        # A hidden number (NaN) is not a claim, so it cannot be an impossible one.
        assert (e.loc[c >= 3, f"d_intensify2_h{h}_p"].fillna(0) < 1e-9).all(), f"worsening two from D3+ at h{h}"
        assert (e.loc[c >= 4, f"d_intensify1_h{h}_p"].fillna(0) < 1e-9).all(), f"worsening from D4 at h{h}"
        assert (e.loc[c <= 0, f"d_improve1_h{h}_p"].fillna(0) < 1e-9).all(), f"easing from none at h{h}"
        _ = np
