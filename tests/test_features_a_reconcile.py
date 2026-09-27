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
# erc_pct is gated against the reference, not the store: see below.
A_COLUMNS = ("usdm", "erc")
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


FIXED_USDM_WEEK = "2022-12-27"  # docs/DECISIONS.md, the missing 2022-12-27 map


@pytest.mark.parametrize("domain", DOMAINS)
def test_erc_pct_equals_the_reference(domain: str) -> None:
    """erc_pct is gated against the reference, not against the store.

    The store's erc_pct is the value shown to be wrong: it was fitted through
    2022-12-31, past a split ending 2021, and used kind="weak". Comparing to it
    would enforce the defect. The reference is the definition.
    """
    from cofire.model.erc_pct import erc_percentile_reference

    pair = _load_pair(domain)
    if pair is None:
        pytest.skip(f"{domain}: feature stores not built in this checkout")
    _old, new = pair
    st = get_settings()
    mask = (new["time"] <= pd.Timestamp(st.train_end)).to_numpy()
    ref = erc_percentile_reference(new[["cell_id", "time", "erc"]], mask)
    got = pd.to_numeric(new["erc_pct"], errors="coerce").to_numpy(dtype=float)
    k = np.isfinite(got) & np.isfinite(ref)
    assert k.sum() > 10_000
    worst = float(np.abs(got[k] - ref[k]).max())
    assert worst <= 1e-6, f"{domain}: erc_pct differs from the reference by {worst:.6g}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_erc_pct_is_approximately_uniform_on_training_data(domain: str) -> None:
    """A week-of-year percentile has a near-uniform marginal per cell.

    The check that would have caught both the single-week pool, which gave nine
    distinct values, and a wrong percentile formula.
    """
    pair = _load_pair(domain)
    if pair is None:
        pytest.skip(f"{domain}: feature stores not built in this checkout")
    _old, new = pair
    st = get_settings()
    tr = new[new["time"] <= pd.Timestamp(st.train_end)]
    widths = tr.groupby("cell_id")["erc_pct"].apply(lambda s: s.quantile(0.95) - s.quantile(0.05))
    assert 80.0 <= float(widths.mean()) <= 100.0, f"{domain}: mean width {widths.mean():.2f}"


@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("column", ("usdm", "erc"))
def test_decoupled_builder_matches_the_store(domain: str, column: str) -> None:
    pair = _load_pair(domain)
    if pair is None:
        pytest.skip(f"{domain}: feature stores not built in this checkout")
    old, new = pair
    m = old.merge(new, on=["cell_id", "time"], suffixes=("_old", "_new"), how="inner")
    m = m[(m["time"].dt.year >= OVERLAP[0]) & (m["time"].dt.year <= OVERLAP[1])]
    assert len(m) > 10_000, f"{domain}: only {len(m)} overlapping cell-weeks"
    if column == "usdm":
        # The legacy store predates the 2022-12-27 fix: that week's map was
        # missing from the server's 2022 archive and was coded "none". The
        # rebuilt store carries the real map, so this one week is expected to
        # differ, and only because the legacy store reads 0 there.
        fixed = m["time"] == pd.Timestamp(FIXED_USDM_WEEK)
        assert (pd.to_numeric(m.loc[fixed, "usdm_old"]) == 0).all()
        m = m[~fixed]

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
