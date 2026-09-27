"""Every year's USDM archive holds exactly its Tuesdays."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest
from cofire.ship import usdm_calendar as C


def _archive(tmp_path: Path, year: int, drop: set[str] = frozenset(), lower: set[str] = frozenset()) -> Path:
    (tmp_path / "usdm").mkdir(exist_ok=True)
    with zipfile.ZipFile(tmp_path / "usdm" / f"{year}_USDM_M.zip", "w") as zf:
        for w in sorted(C.expected_weeks(year)):
            key = f"{w:%Y%m%d}"
            if key in drop:
                continue
            zf.writestr(f"{'usdm' if key in lower else 'USDM'}_{key}_M.zip", b"x")
    return tmp_path


def test_a_complete_year_passes_even_with_a_lowercase_name(tmp_path: Path) -> None:
    raw = _archive(tmp_path, 2020, lower={"20200623"})
    C.assert_complete(range(2020, 2021), raw)


def test_a_deliberately_removed_week_fails(tmp_path: Path) -> None:
    raw = _archive(tmp_path, 2022, drop={"20221227"})
    assert C.missing(2022, raw) == [pd.Timestamp("2022-12-27")]
    with pytest.raises(C.CalendarError, match="2022-12-27"):
        C.assert_complete(range(2022, 2023), raw)


def test_the_current_year_is_checked_through_the_latest_issue(tmp_path: Path) -> None:
    raw = _archive(tmp_path, 2026)
    C.assert_complete(range(2026, 2027), raw, through=pd.Timestamp("2026-09-22"))


@pytest.mark.skipif(not (C.RAW / "usdm" / "2007_USDM_M.zip").exists(), reason="archives not on disk")
def test_the_archives_on_disk_are_complete() -> None:
    C.assert_complete(range(2007, 2026))
