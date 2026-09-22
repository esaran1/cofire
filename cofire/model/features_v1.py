"""v1 features: ESI, RCI, and the availability guard. HAND-REWRITE.

Joins the new satellite sources onto the existing weekly cell frame, with two
properties the earlier feature path did not have:

1. Every value carries a *valid week* that is strictly older than the issue
   date by the source's real latency, plus a guard week where the archive is
   known to be retrospectively rewritten. `assert_no_future_reads` is called on
   the realised join, so a leak fails loudly rather than silently improving the
   metrics.

2. The interpolation of the biweekly 12-week composite, and the reprocessing
   guard, are both behind flags. The ablation runs with and without each, so
   what they cost is measured rather than argued.

Source groups, for the ablation table:
    gridmet     everything already in the feature store
    esi         esi_4wk, esi_12wk and their anomalies
    rci         rapid change index at 1, 2 and 4 week accumulations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from cofire.model.config import Settings, get_settings
from cofire.model.data.availability import REGISTRY, assert_no_future_reads
from cofire.model.data.esi import interpolate_to_weekly, rapid_change_index, standardised_change

LOGGER = logging.getLogger("cofire.features_v1")

ESI_GROUP = ("esi_4wk", "esi_12wk", "esi_4wk_anom", "esi_12wk_anom")
RCI_GROUP = ("rci_1", "rci_2", "rci_4")


@dataclass
class V1FeatureConfig:
    """Flags the ablation toggles."""

    interpolate_12wk: bool = True
    apply_reprocessing_guard: bool = True


def _nearest_grid(da: xr.DataArray, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Nearest-neighbour onto the gridMET cell centres.

    Nearest rather than bilinear: ESI is 5 km against gridMET's 4 km, so the
    grids are close enough that interpolation would invent structure at a scale
    the source does not resolve.
    """
    return da.sel(
        lat=xr.DataArray(lats, dims="cell"),
        lon=xr.DataArray(lons, dims="cell"),
        method="nearest",
    ).values


def attach_esi(
    frame: pd.DataFrame,
    settings: Settings | None = None,
    cfg: V1FeatureConfig | None = None,
) -> pd.DataFrame:
    """Join ESI 4WK, ESI 12WK and RCI onto a weekly cell frame.

    The join is by *lagged* valid week, never by issue week: for an issue on
    Tuesday t, the newest ESI composite that could have been read is the one
    whose valid week is at least `latency + guard` earlier.
    """
    settings = settings or get_settings()
    cfg = cfg or V1FeatureConfig()
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"])

    esi_dir = settings.processed_dir / "esi"
    p4, p12 = esi_dir / "weekly.nc", esi_dir / "weekly_12wk_stride2.nc"
    if not p4.exists():
        LOGGER.warning("no ESI 4WK at %s; v1 features unavailable", p4)
        return out

    issues = pd.DatetimeIndex(sorted(out["time"].unique()))
    lats = out["lat"].to_numpy(dtype=float)
    lons = out["lon"].to_numpy(dtype=float)

    def lag_for(key: str) -> timedelta:
        av = REGISTRY[key]
        return timedelta(days=av.latency_days) + timedelta(
            weeks=av.guard_weeks if cfg.apply_reprocessing_guard else 0
        )

    # ---- ESI 4WK, weekly at source
    da4 = xr.open_dataset(p4)["esi_4wk"]
    lag4 = lag_for("esi_4wk")
    # For each issue, the newest valid week that was readable by then.
    src_times4 = pd.DatetimeIndex(da4.time.values)
    picked4 = _pick_readable(issues, src_times4, lag4)
    _assert_join("esi_4wk", picked4, cfg)
    out["esi_4wk"] = _map_values(out, da4, picked4, lats, lons)

    # ---- ESI 12WK, biweekly at source, optionally interpolated to weekly
    if p12.exists():
        da12 = xr.open_dataset(p12)["esi_12wk"]
        da12w = interpolate_to_weekly(da12, issues, enabled=cfg.interpolate_12wk)
        lag12 = lag_for("esi_12wk")
        src12 = pd.DatetimeIndex(da12w.time.values)
        picked12 = _pick_readable(issues, src12, lag12)
        _assert_join("esi_12wk", picked12, cfg)
        out["esi_12wk"] = _map_values(out, da12w, picked12, lats, lons)

    # ---- RCI from the 4-week composite, standardised on training weeks only
    train_end = pd.Timestamp(settings.train_end)
    esi_panel = da4.values.reshape(da4.sizes["time"], -1)
    train_mask = np.asarray(src_times4 <= train_end)
    if train_mask.sum() >= 10:
        z = standardised_change(esi_panel, train_mask)
        for acc in (1, 2, 4):
            rci = rapid_change_index(z if acc == 1 else _accumulate(z, acc))
            rci_da = xr.DataArray(
                rci.reshape(da4.shape),
                dims=da4.dims,
                coords=da4.coords,
            )
            out[f"rci_{acc}"] = _map_values(out, rci_da, picked4, lats, lons)
    return out


def _accumulate(z: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean of the standardised change, for slower RCI variants."""
    out = np.copy(z)
    for i in range(z.shape[0]):
        lo = max(0, i - window + 1)
        out[i] = np.nanmean(z[lo : i + 1], axis=0)
    return out


def _pick_readable(
    issues: pd.DatetimeIndex, source_times: pd.DatetimeIndex, lag: timedelta
) -> dict[pd.Timestamp, pd.Timestamp | None]:
    """Newest source week readable by each issue, or None."""
    st = source_times.sort_values()
    picked: dict[pd.Timestamp, pd.Timestamp | None] = {}
    for iss in issues:
        cutoff = iss - lag
        ok = st[st <= cutoff]
        picked[iss] = ok[-1] if len(ok) else None
    return picked


def _assert_join(
    source_key: str, picked: dict[pd.Timestamp, pd.Timestamp | None], cfg: V1FeatureConfig
) -> None:
    """Fail loudly if any realised join would have read the future."""
    for iss, src in picked.items():
        if src is None:
            continue
        assert_no_future_reads(
            source_key,
            [date(src.year, src.month, src.day)],
            date(iss.year, iss.month, iss.day),
            apply_guard=cfg.apply_reprocessing_guard,
        )


def _map_values(
    frame: pd.DataFrame,
    da: xr.DataArray,
    picked: dict[pd.Timestamp, pd.Timestamp | None],
    lats: np.ndarray,
    lons: np.ndarray,
) -> np.ndarray:
    """Look up each row's value at its issue's chosen source week."""
    out = np.full(len(frame), np.nan, dtype="float32")
    times = frame["time"].to_numpy()
    for iss, src in picked.items():
        if src is None:
            continue
        m = times == np.datetime64(iss)
        if not m.any():
            continue
        try:
            slab = da.sel(time=src)
        except KeyError:
            continue
        out[m] = _nearest_grid(slab, lats[m], lons[m])
    return out


def add_esi_anomalies(frame: pd.DataFrame, train_end: pd.Timestamp) -> pd.DataFrame:
    """Per-cell, per-week-of-year anomalies, moments from training weeks only."""
    out = frame.copy()
    t = pd.to_datetime(out["time"])
    out["_woy"] = t.dt.isocalendar().week.astype(int)
    train = out[t <= train_end]
    for col in ("esi_4wk", "esi_12wk"):
        if col not in out.columns:
            continue
        mu = train.groupby(["cell_id", "_woy"])[col].mean()
        joined = out[["cell_id", "_woy"]].join(mu, on=["cell_id", "_woy"], rsuffix="_mu")
        base = pd.to_numeric(joined[col], errors="coerce")
        out[f"{col}_anom"] = (pd.to_numeric(out[col], errors="coerce") - base).astype("float32")
    return out.drop(columns=["_woy"])


def v1_feature_columns(frame: pd.DataFrame) -> dict[str, list[str]]:
    """Source groups present in this frame, for the ablation."""
    return {
        "esi": [c for c in ESI_GROUP if c in frame.columns],
        "rci": [c for c in RCI_GROUP if c in frame.columns],
    }


def build_v1_features(
    settings: Settings | None = None, cfg: V1FeatureConfig | None = None
) -> Path:
    """Attach v1 features to the existing feature store and write it back."""
    from cofire.model.features import load_features

    settings = settings or get_settings()
    cfg = cfg or V1FeatureConfig()
    root = settings.processed_dir / "features"
    frame = load_features(root)
    if frame.empty:
        raise SystemExit("feature store is empty; run `make data` first")

    frame = attach_esi(frame, settings, cfg)
    frame = add_esi_anomalies(frame, pd.Timestamp(settings.train_end))

    out_root = settings.processed_dir / "features_v1"
    out_root.mkdir(parents=True, exist_ok=True)
    tmp = frame.copy()
    tmp["year"] = pd.to_datetime(tmp["time"]).dt.year
    for year, chunk in tmp.groupby("year"):
        chunk.drop(columns=["year"]).to_parquet(out_root / f"year={int(year)}.parquet", index=False)
    LOGGER.info("v1 features written to %s (%s rows)", out_root, len(frame))
    return out_root
