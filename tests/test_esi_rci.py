"""RCI construction and ESI leakage discipline."""

from __future__ import annotations

import numpy as np
from cofire.model.data.esi import esi_url, rapid_change_index, standardised_change


def test_url_uses_day_of_year() -> None:
    from datetime import date

    # 2020-01-08 is DOY 8.
    assert esi_url(date(2020, 1, 8)).endswith("DFPPM_4WK_2020008.tif")


def test_standardisation_uses_training_weeks_only() -> None:
    """Moments must come from the training mask, never from later weeks.

    Later weeks are given a wildly different scale; if they leaked into the
    moments the training-period z-scores would be visibly squashed.
    """
    rng = np.random.default_rng(0)
    esi = np.concatenate([rng.normal(0, 1, size=(40, 3)), rng.normal(0, 50, size=(20, 3))])
    mask = np.zeros(60, dtype=bool)
    mask[:40] = True
    z = standardised_change(esi, mask)
    train_sd = float(np.nanstd(z[:40]))
    # Training-period z should be about unit scale, because its own moments made it.
    assert 0.5 < train_sd < 2.0, train_sd
    # The later high-variance block should show up as large z, not be normalised away.
    assert float(np.nanstd(z[40:])) > 5 * train_sd


def test_rci_accumulates_consecutive_same_sign_runs() -> None:
    """A sustained run must score far above a single week of the same size."""
    # Column 0: five consecutive -1 changes. Column 1: one -1 then zeros.
    z = np.zeros((5, 2), dtype="float32")
    z[:, 0] = -1.0
    z[0, 1] = -1.0
    rci = rapid_change_index(z)
    assert rci[-1, 0] < rci[0, 0], "a longer run must score more strongly"
    assert abs(rci[-1, 0]) > abs(rci[0, 1]) * 5, "sustained drying must dominate a single week"


def test_rci_resets_when_the_sign_flips() -> None:
    z = np.array([[-1.0], [-1.0], [-1.0], [1.0]], dtype="float32")
    rci = rapid_change_index(z)
    assert rci[2, 0] < 0
    assert rci[3, 0] > 0, "a sign flip must start a new run"
    assert abs(rci[3, 0]) < abs(rci[2, 0]), "the new run starts short"


def test_rci_sign_follows_the_direction_of_change() -> None:
    drying = rapid_change_index(np.full((4, 1), -1.0, dtype="float32"))
    wetting = rapid_change_index(np.full((4, 1), 1.0, dtype="float32"))
    assert drying[-1, 0] < 0 and wetting[-1, 0] > 0
    assert abs(drying[-1, 0]) == abs(wetting[-1, 0])


def test_rci_handles_nan_without_propagating() -> None:
    z = np.array([[-1.0], [np.nan], [-1.0]], dtype="float32")
    out = rapid_change_index(z)
    assert np.all(np.isfinite(out))
