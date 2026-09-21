"""Both Settings construction paths must return the same split.

The defect this pins: `apply_subset_defaults` is called by `get_settings()` and
not by a bare `Settings()`, so the two disagreed. Bare construction gave
train_start 2004 while the factory gave the dev-subset override. Analysis code
in this project constructs both, so a calibration path and an evaluation path
could silently run on different training windows, which is the same class of
fault as the original ACI bug.

The override itself also forced train 2019 to 2022 for every dev subset, and
both domains run as dev subsets, so the effective training window was two years
once the LODO folds were carved out.
"""

from __future__ import annotations

import pytest
from cofire.model.config import Settings, get_settings

DOMAINS = ("larimer", "pueblo")
SPLIT_FIELDS = (
    "train_start",
    "train_end",
    "valid_start",
    "valid_end",
    "calibrate_start",
    "calibrate_end",
    "hindcast_start",
)


@pytest.mark.parametrize("domain", DOMAINS)
def test_both_construction_paths_agree(domain: str, monkeypatch) -> None:
    monkeypatch.setenv("COFIRE_SUBSET_NAME", domain)
    get_settings.cache_clear()
    bare = Settings()
    factory = get_settings()
    for field in SPLIT_FIELDS:
        assert getattr(bare, field) == getattr(factory, field), (
            f"{domain}: {field} is {getattr(bare, field)} from Settings() but "
            f"{getattr(factory, field)} from get_settings()"
        )
    get_settings.cache_clear()


@pytest.mark.parametrize("domain", DOMAINS)
def test_the_training_window_is_not_two_years(domain: str, monkeypatch) -> None:
    """The defect that motivated the back-extension."""
    monkeypatch.setenv("COFIRE_SUBSET_NAME", domain)
    get_settings.cache_clear()
    s = get_settings()
    span = s.train_end.year - s.train_start.year + 1
    assert span >= 10, f"{domain}: training window is {span} years"
    get_settings.cache_clear()


def test_the_split_is_ordered_and_does_not_overlap() -> None:
    s = get_settings()
    assert s.train_end < s.valid_start
    assert s.valid_end < s.calibrate_start
    assert s.calibrate_end < s.hindcast_start


def test_training_starts_no_earlier_than_the_usdm_record() -> None:
    """A drought target cannot be built without its label.

    ERC reaches 2004, USDM reaches 2007, so the split starts at 2007. If USDM
    were ever extended further back this bound moves with it.
    """
    s = get_settings()
    assert s.train_start.year >= 2007
