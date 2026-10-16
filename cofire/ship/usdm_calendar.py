"""The USDM release calendar, asserted against what is on disk.

USDM maps are valid on Tuesdays, one a week. The frozen rasterizer fills any
week it cannot find with category 0, "none", so a missing map is silent. The
2022 yearly archive on the server was last rebuilt on 22 December 2022, before
the 27 December map was released, and that week was coded "none" in every
store until it was fetched on its own. This check makes that impossible to
miss: for each year, the weeks present must equal the Tuesdays of that year,
through the latest published issue for the current year.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")


class CalendarError(AssertionError):
    """A year's USDM archive does not hold exactly the expected weeks."""


def expected_weeks(year: int, through: pd.Timestamp | None = None) -> set[pd.Timestamp]:
    """The Tuesdays of `year`, through `through` when it is given."""
    end = pd.Timestamp(f"{year}-12-31")
    if through is not None:
        end = min(end, pd.Timestamp(through))
    return set(pd.date_range(f"{year}-01-01", end, freq="W-TUE"))


def weeks_present(year: int, raw: Path = RAW) -> set[pd.Timestamp]:
    """The weeks whose maps are in the year's USDM archive, read from the member names; empty if
    there is no archive.
    """
    z = raw / "usdm" / f"{year}_USDM_M.zip"
    if not z.exists():
        return set()
    out: set[pd.Timestamp] = set()
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            m = re.search(r"USDM_(\d{8})", n, re.IGNORECASE)
            if m and n.lower().endswith((".zip", ".shp")):
                out.add(pd.Timestamp(m.group(1)))
    return out


def missing(year: int, raw: Path = RAW, through: pd.Timestamp | None = None) -> list[pd.Timestamp]:
    """The expected weeks of `year` that the archive lacks, in order."""
    return sorted(expected_weeks(year, through) - weeks_present(year, raw))


def assert_complete(years: range, raw: Path = RAW, through: pd.Timestamp | None = None) -> None:
    """Raise unless every year holds exactly its Tuesdays (and nothing else)."""
    problems: list[str] = []
    for y in years:
        want, have = expected_weeks(y, through), weeks_present(y, raw)
        lost, extra = sorted(want - have), sorted(have - want)
        if lost:
            problems.append(f"{y}: missing {[str(w.date()) for w in lost]}")
        if extra and through is None:
            problems.append(f"{y}: unexpected {[str(w.date()) for w in extra]}")
    if problems:
        raise CalendarError("USDM archive does not match the release calendar: " + "; ".join(problems))
