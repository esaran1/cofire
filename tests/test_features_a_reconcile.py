"""The decoupled builder must reproduce the store on the overlapping years.

Configuration A reads usdm, erc and erc_pct. The decoupled builder exists so the
record can extend to 2007 without fetching twelve gridMET variables nobody
ships, and it is only trustworthy if it agrees with the store exactly where both
have data.

Three faults this gate caught, none of which changed a value's plausibility:

- Per-year cubes overlap at year boundaries, and the store resolves the
  collision with drop_duplicates(keep="last"). Keeping the first occurrence gave
  50.25 where the store says 27.0.
- Daily extension files resampled per file truncated any week spanning a year
  boundary.
- The 2017 extension file resamples to a week labelled 2018-01-02 covering only
  27 to 31 December, which collided with the cube's complete week and won on
  ordering. That gave 35.2 where the store says 46.0.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest
from cofire.model.config import get_settings

DOMAINS = ("larimer", "pueblo")
A_COLUMNS = ("usdm", "erc", "erc_pct")
OVERLAP = (2018, 2025)


def _load_pair(domain: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    from cofire.model.features import load_features
    from cofire.model.features_a import load as load_a

    os.environ["COFIRE_SUBSET_NAME"] = domain
    get_settings.cache_clear()
    st = get_settings()
    if not (st.processed_dir / "features_a").exists():
        return None
    if not (st.processed_dir / "features_v1").exists():
        return None
    old = load_features(st.processed_dir / "features_v1")
    new = load_a(st)
    if old.empty or new.empty:
        return None
    for d in (old, new):
        d["time"] = pd.to_datetime(d["time"])
    return old, new


@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("column", A_COLUMNS)
def test_decoupled_builder_matches_the_store(domain: str, column: str) -> None:
    pair = _load_pair(domain)
    if pair is None:
        pytest.skip(f"{domain}: feature stores not built in this checkout")
    old, new = pair
    m = old.merge(new, on=["cell_id", "time"], suffixes=("_old", "_new"), how="inner")
    m = m[(m["time"].dt.year >= OVERLAP[0]) & (m["time"].dt.year <= OVERLAP[1])]
    assert len(m) > 10_000, f"{domain}: only {len(m)} overlapping cell-weeks"

    a = pd.to_numeric(m[f"{column}_old"], errors="coerce").to_numpy(dtype=float)
    b = pd.to_numeric(m[f"{column}_new"], errors="coerce").to_numpy(dtype=float)

    nan_mismatch = int((np.isfinite(a) != np.isfinite(b)).sum())
    assert nan_mismatch == 0, f"{domain} {column}: {nan_mismatch} presence mismatches"

    both = np.isfinite(a) & np.isfinite(b)
    diff = np.abs(a[both] - b[both])
    worst = float(diff.max()) if diff.size else 0.0
    if worst > 1e-6:
        i = int(np.argmax(diff))
        row = m[both].iloc[i]
        pytest.fail(
            f"{domain} {column}: max|diff| {worst:.6g} at cell {row['cell_id']} "
            f"{row['time'].date()}, store {a[both][i]:.6g}, decoupled {b[both][i]:.6g}"
        )


def test_the_extension_years_are_present_and_the_store_years_unchanged() -> None:
    """The point of the exercise: more years, same values where they overlap."""
    pair = _load_pair("larimer")
    if pair is None:
        pytest.skip("feature stores not built in this checkout")
    _old, new = pair
    years = set(new["time"].dt.year.unique())
    assert 2012 in years, "2012 is the drought year the extension exists to reach"
    assert min(years) <= 2007
