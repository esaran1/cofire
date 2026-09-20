"""USDM-aligned Tuesday week index."""

from __future__ import annotations

from datetime import date, timedelta


def next_tuesday(d: date) -> date:
    """Return d if it is Tuesday, else the following Tuesday. Monday=0, Tuesday=1."""
    offset = (1 - d.weekday()) % 7
    return d + timedelta(days=offset)


def previous_tuesday(d: date) -> date:
    offset = (d.weekday() - 1) % 7
    return d - timedelta(days=offset)


def tuesdays(start: date, end: date) -> list[date]:
    """Inclusive list of Tuesdays in [start, end]."""
    cur = next_tuesday(start)
    out: list[date] = []
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=7)
    return out


def week_of_year(d: date) -> int:
    """ISO week is fine for climatology keys; USDM Tuesdays are unique per week."""
    return int(d.strftime("%U"))


def issue_on_or_before(d: date) -> date:
    return previous_tuesday(d)
