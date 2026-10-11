"""Vintages: kept forever, revised only inside the window, old issues pinned."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from cofire.ship import vintages
from cofire.ship.safe_fetch import FetchRefused


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(vintages, "ROOT", tmp_path / "v")
    monkeypatch.setattr(vintages, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(vintages, "REVISIONS", tmp_path / "rev")
    monkeypatch.setattr(vintages, "ISSUES", tmp_path / "issues.json")
    return tmp_path


def _series(start: str, end: str, value: float = 40.0) -> xr.DataArray:
    days = pd.date_range(start, end, freq="D")
    return xr.DataArray(np.full((len(days), 2, 2), value), dims=("day", "lat", "lon"),
                        coords={"day": days, "lat": [39.7, 39.6], "lon": [-105.0, -104.9]}, name=vintages.VAR)


T0, T1 = pd.Timestamp("2026-09-20T03:00:00"), pd.Timestamp("2026-09-27T20:00:00")


def test_a_revision_inside_the_window_is_accepted_logged_and_versioned(store: Path) -> None:
    vintages.record("denver", 2026, _series("2026-01-01", "2026-09-18"), T0, window_days=240, root=store / "v")
    new = _series("2026-09-05", "2026-09-25")
    new.loc[{"day": "2026-09-10"}] = 55.0  # revised, 15 days before the newest day
    rec = vintages.record("denver", 2026, new, T1, window_days=240, root=store / "v")
    assert rec["revisions"]["n_cell_days"] == 4 and rec["revisions"]["first_date"] == "2026-09-10"
    log = pd.read_csv(rec["revisions"]["log"])
    assert set(log["old"]) == {40.0} and set(log["new"]) == {55.0}
    assert len(vintages.records("denver", 2026)) == 2
    assert float(vintages.assemble("denver", 2026).sel(day="2026-09-10").mean()) == 55.0
    assert str(vintages.assemble("denver", 2026)["day"].values[-1])[:10] == "2026-09-25"


def test_a_revision_older_than_the_window_fails_the_gate(store: Path) -> None:
    vintages.record("denver", 2026, _series("2026-01-01", "2026-09-18"), T0, window_days=240, root=store / "v")
    new = _series("2026-01-01", "2026-09-25")
    new.loc[{"day": "2026-01-10"}] = 55.0  # 258 days before the newest day
    with pytest.raises(FetchRefused, match="older than the 240-day window"):
        vintages.record("denver", 2026, new, T1, window_days=240, root=store / "v")
    assert len(vintages.records("denver", 2026)) == 1, "a refused fetch leaves no vintage"


def test_an_old_issue_is_unchanged_after_a_new_vintage_lands(store: Path) -> None:
    vintages.record("denver", 2026, _series("2026-01-01", "2026-09-18"), T0, window_days=240, root=store / "v")
    before = vintages.assemble("denver", 2026, as_of=T0)
    vintages.pin_issues({"denver": {"2026-09-15": T0.isoformat()}})
    vintages.record("denver", 2026, _series("2026-09-05", "2026-09-25", 60.0), T1, window_days=240, root=store / "v")
    after = vintages.assemble("denver", 2026, as_of=pd.Timestamp(vintages.issue_vintages()["denver"]["2026-09-15"]))
    xr.testing.assert_identical(before, after)
    assert float(vintages.assemble("denver", 2026).sel(day="2026-09-10").mean()) == 60.0
    with pytest.raises(AssertionError, match="refusing to repin"):
        vintages.pin_issues({"denver": {"2026-09-15": T1.isoformat()}})


def test_a_vintage_is_never_overwritten(store: Path) -> None:
    da = _series("2026-01-01", "2026-01-31")
    vintages.record("denver", 2026, da, T0, root=store / "v")
    with pytest.raises(FetchRefused, match="never overwritten"):
        vintages.record("denver", 2026, da, T0, root=store / "v")


def test_published_issues_are_pinned_and_the_adopted_revision_is_logged() -> None:
    pins = vintages.issue_vintages()
    assert set(pins) == {"denver", "upper_south_platte", "dillon", "larimer", "pueblo"}
    lar = vintages.records("larimer", 2026)
    assert len(lar) >= 2 and lar[1]["revisions"]["n_cell_days"] > 0
    assert pins["larimer"]["2026-09-15"] == lar[0]["fetched_at"], "old issues keep the store's vintage"


def test_the_gate_day_lies_a_year_and_a_week_back_in_the_previous_file() -> None:
    from cofire.ship.erc_fetch import GATE_MARGIN_DAYS, gate_target

    assert vintages.WINDOW_DAYS == 365 and GATE_MARGIN_DAYS == 7
    # Server newest day 2026-10-09 (day index 281): the gate is 2025-10-02.
    assert gate_target(2026, 282) == (2025, pd.Timestamp("2025-10-02").dayofyear - 1)
    # 2026-01-31, where the 2026-10-09 revisions began, is inside the window.
    newest = pd.Timestamp("2026-10-09")
    assert newest - pd.Timestamp("2026-01-31") < pd.Timedelta(days=vintages.WINDOW_DAYS)
