"""A fitted artifact may not have seen data outside its split.

The fault: training_stats.pkl carried train_end 2022-12-31 while the split in
effect ended 2021, so ten fitted statistics were fitted through the validation
years. erc_by_woy among them, which means the percentile target saw its own
evaluation period.
"""

from __future__ import annotations

from datetime import date

import pytest
from cofire.model.config import get_settings
from cofire.model.fit_window import (
    HOLDOUT_YEAR,
    THROUGH_CALIBRATION,
    TRAIN_ONLY,
    FitWindow,
    FitWindowError,
    check,
    checked_load,
    read_sidecar,
    write_sidecar,
)


def test_a_window_inside_the_train_split_passes() -> None:
    s = get_settings()
    check(FitWindow(s.train_start, s.train_end, TRAIN_ONLY), "ok")


def test_the_training_stats_fault_is_rejected() -> None:
    """The exact artifact and window that leaked."""
    s = get_settings()
    bad = FitWindow(s.train_start, date(2022, 12, 31), TRAIN_ONLY)
    with pytest.raises(FitWindowError, match="past the train split end"):
        check(bad, "training_stats.pkl")


def test_a_window_touching_the_holdout_is_rejected() -> None:
    s = get_settings()
    with pytest.raises(FitWindowError, match="sealed holdout"):
        check(FitWindow(s.train_start, date(HOLDOUT_YEAR, 3, 1), TRAIN_ONLY), "x")


def test_calibrators_may_see_the_calibration_split() -> None:
    """A Platt calibrator or PID warm-up is fitted there by design."""
    s = get_settings()
    w = FitWindow(s.train_start, s.calibrate_end, THROUGH_CALIBRATION)
    check(w, "calibrator")
    with pytest.raises(FitWindowError):
        check(FitWindow(s.train_start, s.calibrate_end, TRAIN_ONLY), "training artifact")


def test_a_window_starting_before_the_split_is_rejected() -> None:
    s = get_settings()
    with pytest.raises(FitWindowError, match="before the train split start"):
        check(FitWindow(date(1990, 1, 1), s.train_end, TRAIN_ONLY), "x")


def test_sidecar_round_trips(tmp_path) -> None:
    s = get_settings()
    art = tmp_path / "thing.pkl"
    art.write_bytes(b"x")
    w = FitWindow(s.train_start, s.train_end, TRAIN_ONLY)
    write_sidecar(art, w, "thing")
    assert read_sidecar(art) == w


def test_an_artifact_without_a_window_fails_strict_loading(tmp_path) -> None:
    """Silence is not evidence of a clean fit."""
    art = tmp_path / "thing.pkl"
    art.write_bytes(b"x")
    with pytest.raises(FitWindowError, match="no fit window recorded"):
        checked_load(art)
    assert checked_load(art, strict=False).scope == "unknown"


def test_loading_an_artifact_fitted_through_a_validation_year_fails(tmp_path) -> None:
    """The end-to-end case the invariant exists for."""
    s = get_settings()
    art = tmp_path / "training_stats.pkl"
    art.write_bytes(b"x")
    write_sidecar(art, FitWindow(s.train_start, date(2022, 12, 31), TRAIN_ONLY))
    with pytest.raises(FitWindowError, match="seen its own evaluation period"):
        checked_load(art)
