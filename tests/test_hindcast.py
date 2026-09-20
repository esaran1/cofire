from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from cofire.model.hindcast import CutoffError, assert_cutoff


def test_cutoff_raises_on_future_rows() -> None:
    frame = pd.DataFrame({"time": ["2026-05-05", "2026-05-12"]})
    with pytest.raises(CutoffError):
        assert_cutoff(frame, date(2026, 5, 5))


def test_cutoff_allows_issue_date() -> None:
    frame = pd.DataFrame({"time": ["2026-05-05", "2026-04-28"]})
    assert_cutoff(frame, date(2026, 5, 5))
