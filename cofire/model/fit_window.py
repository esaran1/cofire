"""Every fitted artifact records the window it was fitted on, and is checked.

The fault this closes: `artifacts/training_stats.pkl` carried
`train_end = 2022-12-31` while the split in effect ended 2021, so ten fitted
statistics, `erc_by_woy` among them, were fitted through the validation years.
A percentile target that saw its own evaluation period is a leak, and nothing
in the loading path noticed because nothing was checked.

The invariant: an artifact declares `[fit_start, fit_end]`, and the loader
asserts that window lies inside the split the artifact is entitled to. Training
artifacts must lie inside the train split; calibrators and controller warm-up
state may extend through the calibration split, because that is what they are
fitted on. Nothing may touch the sealed holdout year.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

from cofire.model.config import Settings, get_settings  # noqa: E402

LOGGER = logging.getLogger("cofire.fit_window")

HOLDOUT_YEAR = 2026

# What each kind of artifact is allowed to see.
TRAIN_ONLY = "train"
THROUGH_CALIBRATION = "calibration"


class FitWindowError(AssertionError):
    """An artifact was fitted outside the split it is entitled to."""


@dataclass(frozen=True)
class FitWindow:
    """The window an artifact was fitted on, and what it is entitled to see."""

    fit_start: date
    fit_end: date
    scope: str = TRAIN_ONLY

    def to_dict(self) -> dict[str, str]:
        return {
            "fit_start": self.fit_start.isoformat(),
            "fit_end": self.fit_end.isoformat(),
            "scope": self.scope,
        }

    @staticmethod
    def from_dict(d: dict[str, str]) -> FitWindow:
        return FitWindow(
            fit_start=date.fromisoformat(d["fit_start"]),
            fit_end=date.fromisoformat(d["fit_end"]),
            scope=d.get("scope", TRAIN_ONLY),
        )


def allowed_bounds(scope: str, settings: Settings | None = None) -> tuple[date, date]:
    """The window a given scope may be fitted within."""
    settings = settings or get_settings()
    if scope == THROUGH_CALIBRATION:
        return settings.train_start, settings.calibrate_end
    return settings.train_start, settings.train_end


def check(window: FitWindow, name: str, settings: Settings | None = None) -> None:
    """Raise unless `window` lies inside what its scope permits.

    Called by every loader. A warning would not be enough: the point of the
    invariant is that a leaking artifact cannot be used, and a warning in a long
    unattended run is a line of log nobody reads.
    """
    settings = settings or get_settings()
    lo, hi = allowed_bounds(window.scope, settings)

    if window.fit_end.year >= HOLDOUT_YEAR or window.fit_start.year >= HOLDOUT_YEAR:
        raise FitWindowError(
            f"{name}: fitted on {window.fit_start}..{window.fit_end}, which touches "
            f"the sealed holdout year {HOLDOUT_YEAR}"
        )
    if window.fit_end > hi:
        raise FitWindowError(
            f"{name}: fitted through {window.fit_end}, past the {window.scope} "
            f"split end {hi}. This is the training_stats.pkl fault: a statistic "
            f"fitted through the validation years has seen its own evaluation period."
        )
    if window.fit_start < lo:
        raise FitWindowError(
            f"{name}: fitted from {window.fit_start}, before the {window.scope} "
            f"split start {lo}"
        )


def write_sidecar(path: Path, window: FitWindow, name: str = "") -> Path:
    """Record an artifact's fit window beside it.

    A sidecar rather than a change to every artifact format, so that existing
    pickles and JSON blobs gain the invariant without being rewritten.
    """
    side = path.with_suffix(path.suffix + ".fitwindow.json")
    side.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(window.to_dict())
    payload["artifact"] = name or path.name
    side.write_text(json.dumps(payload, indent=2))
    return side


def read_sidecar(path: Path) -> FitWindow | None:
    side = path.with_suffix(path.suffix + ".fitwindow.json")
    if not side.exists():
        return None
    return FitWindow.from_dict(json.loads(side.read_text()))


def checked_load(path: Path, settings: Settings | None = None, strict: bool = True) -> FitWindow:
    """Assert an artifact's declared window before its caller uses it.

    `strict=False` returns the window without raising, for the audit itself:
    the audit needs to report a bad window rather than be stopped by it.
    """
    window = read_sidecar(path)
    if window is None:
        if strict:
            raise FitWindowError(
                f"{path.name}: no fit window recorded. Every fitted artifact must "
                "declare one; see docs/DECISIONS.md on the training_stats fault."
            )
        return FitWindow(date(1900, 1, 1), date(1900, 1, 1), scope="unknown")
    if strict:
        check(window, path.name, settings)
    return window
