from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from cofire.model.hindcast import CutoffError, append_run_log, assert_cutoff


def test_cutoff_raises_on_future_rows() -> None:
    frame = pd.DataFrame({"time": ["2026-05-05", "2026-05-12"]})
    with pytest.raises(CutoffError):
        assert_cutoff(frame, date(2026, 5, 5))


def test_cutoff_allows_issue_date() -> None:
    frame = pd.DataFrame({"time": ["2026-05-05", "2026-04-28"]})
    assert_cutoff(frame, date(2026, 5, 5))


def test_merge_pred_prefers_incoming_hats() -> None:
    """Saved parquets carry *_hat; scoring must use the incoming pred/baseline, not the stored hats."""
    from cofire.model.eval import evaluate_arm, merge_pred, persistence_pred

    truth = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-01-06", "2026-01-13"]),
            "usdm": [2.0, 3.0],
            "usdm_h2": [3.0, 4.0],
            "usdm_h2_hat": [2.0, 2.0],  # stored model
        }
    )
    pers = persistence_pred(truth)
    merged = merge_pred(truth, pers)
    assert list(merged["usdm_h2_hat"]) == list(pers["usdm_h2_hat"])
    metrics = evaluate_arm("persistence", pers, truth)
    assert metrics["usdm_h2_mae"] == 1.0  # |3-2| and |4-3| / 2


def test_discovery_date_parses_epoch_ms() -> None:
    from cofire.model.hindcast import _discovery_date

    row = pd.Series({"attr_FireDiscoveryDateTime": 1771361280000})
    d = _discovery_date(row)
    assert d is not None and d.year == 2026


def test_run_log_records_repeated_looks(tmp_path: Path) -> None:
    path = tmp_path / "run_log.json"
    n1 = append_run_log(path, "abc", "cfg1")
    n2 = append_run_log(path, "abc", "cfg1")
    n3 = append_run_log(path, "def", "cfg2")
    assert n1 == 1 and n2 == 2 and n3 == 1
    records = json.loads(path.read_text())
    assert len(records) == 3
    assert records[1]["config_hash"] == "cfg1"
