"""Configuration A's feature builder, decoupled from the full variable set.

Configuration A reads four things: USDM category, raw ERC, `erc_pct`, and
calendar fields. The full-variable builder in `features.py` stays untouched for
the ML arms, which are not shipped and are not re-run.

Why this exists. The weekly gridMET cube carries all thirteen gridMET
variables, and USDM rasterises onto that cube as its grid template. Extending
the record to 2007 through the full builder would therefore have required
fetching twelve variables that configuration A never reads, at 189 MB against
86 MB of remaining budget. The template needs only coordinates, so it is built
from coordinates.

Three rules, each one a failure this codebase has already hit:

- The grid template is coordinates only. No gridMET variable defines it.
- Missing variables outside their coverage are **absent**, never zero-filled. A
  zero ERC is a real value meaning no fire danger, and it would be read as one.
- Every path is subset-scoped. Globbing across `raw/` returned Larimer's file
  when the active subset was Pueblo, and the reconciliation gate caught it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

from cofire.model.config import Settings, get_settings  # noqa: E402
from cofire.model.data import DateRange  # noqa: E402
from cofire.model.data.erc_extension import cache_path as erc_cache_path  # noqa: E402
from cofire.model.dates import tuesdays  # noqa: E402
from cofire.model.features import PCT_HALF_WINDOW, _percentile  # noqa: E402

LOGGER = logging.getLogger("cofire.features_a")

# Everything configuration A reads. Nothing else is built.
A_COLUMNS = ("usdm", "erc", "erc_pct")


@dataclass(frozen=True)
class GridTemplate:
    """Coordinates and a weekly time index. No variables."""

    lat: np.ndarray
    lon: np.ndarray
    weeks: pd.DatetimeIndex

    def as_dataset(self) -> xr.Dataset:
        """A template `_rasterize_zips` can consume: it reads lat and lon only."""
        return xr.Dataset(coords={"lat": self.lat, "lon": self.lon, "time": self.weeks})

    @property
    def cell_ids(self) -> list[str]:
        return [f"{la:.4f}_{lo:.4f}" for la in self.lat for lo in self.lon]


def build_template(settings: Settings | None = None) -> GridTemplate:
    """Grid coordinates from the reconciled store, weeks from the split.

    Coordinates come from an existing processed cube because that is the grid
    everything else in the store is already on; taking them from a bbox
    calculation would risk a half-cell offset against the data already built.
    """
    settings = settings or get_settings()
    grid_dir = settings.processed_dir / "gridmet"
    cubes = sorted(grid_dir.glob("weekly_*.nc"))
    if not cubes:
        raise SystemExit(f"no processed cube to take coordinates from at {grid_dir}")
    with xr.open_dataset(cubes[0]) as ds:
        lat = np.asarray(ds["lat"].values, dtype=float)
        lon = np.asarray(ds["lon"].values, dtype=float)

    weeks = pd.DatetimeIndex(
        list(tuesdays(settings.train_start, settings.calibrate_end))
    )
    return GridTemplate(lat=lat, lon=lon, weeks=weeks)


def weekly_erc(template: GridTemplate, settings: Settings | None = None) -> xr.DataArray:
    """Weekly-mean ERC over the template grid, from every available source.

    Two sources, both already reconciled cell for cell against the store: the
    extension cache for 2004 to 2017 and the processed cubes for 2018 onward.
    Years present in neither are absent from the result rather than filled.
    """
    settings = settings or get_settings()
    # Extension first, processed store second. The dedup below keeps the LAST
    # occurrence, so ordering the authoritative source last makes the store win
    # any collision. The 2017 extension file resamples to a week labelled
    # 2018-01-02 that covers only 27 to 31 December, and preferring it over the
    # cube's complete week gave 35.2 where the store says 46.0.
    frames: list[xr.DataArray] = []
    store_frames: list[xr.DataArray] = []

    for p in sorted((settings.processed_dir / "gridmet").glob("weekly_*.nc")):
        with xr.open_dataset(p) as ds:
            if "erc" in ds.data_vars:
                store_frames.append(ds["erc"].load())

    # 2004 to 2017: the reconciled extension cache. Daily files are concatenated
    # *before* resampling, because a week spanning a year boundary would
    # otherwise be averaged over only the days inside one file. That truncation
    # is what made the first reconciliation attempt disagree with the store at
    # every January week.
    daily: list[xr.DataArray] = []
    for p in sorted(
        erc_cache_path(settings.subset_name, 0).parent.glob(f"{settings.subset_name}_*.nc")
    ):
        with xr.open_dataset(p) as ds:
            name = next(
                (v for v in ds.data_vars if "energy_release" in str(v) or str(v) == "erc"),
                None,
            )
            if name is None:
                continue
            da = ds[name].load()
            daily.append(da.rename({"day": "time"}) if "day" in da.dims else da)
    if daily:
        joined = xr.concat(daily, dim="time").sortby("time")
        # Drop any weekly bin the daily record cannot fill. A W-TUE bin needs
        # seven days; the final bin of the extension holds however many days
        # remain before the store takes over, and a partial mean is not the
        # same quantity as a full one.
        # W-TUE is right-closed and right-labelled: the value at a Tuesday is
        # the mean of the week *ending* that Tuesday, which is the convention
        # the processed store uses. Verified against the store: 6.6667 for
        # 2023-01-03 matches the Dec 28 to Jan 3 window, not Jan 3 to Jan 9.
        grouped = joined.resample(time="W-TUE")
        weekly = grouped.mean().rename("erc")
        counts = grouped.count(dim="time")
        n_per_week = counts.max(dim=[d for d in counts.dims if d != "time"])
        frames.append(weekly.isel(time=(n_per_week >= 7).values))

    frames.extend(store_frames)

    if not frames:
        raise SystemExit("no ERC source found")
    out = xr.concat(frames, dim="time").sortby("time")

    # Per-year cubes overlap at year boundaries: the week ending 2023-01-03
    # appears in both weekly_2022.nc and weekly_2023.nc with different values,
    # 25.90 and 14.41 as domain means. The store resolves this with
    # `drop_duplicates(..., keep="last")` at features.py:127 and :293, so the
    # later file wins. This path matches that rule exactly rather than choosing
    # its own, because a builder that resolves ties differently from the store
    # it must reproduce will disagree at every year boundary.
    times = pd.DatetimeIndex(out["time"].values)
    keep = (
        pd.DataFrame({"i": np.arange(times.size), "t": times})
        .drop_duplicates("t", keep="last")["i"]
        .to_numpy()
    )
    return out.isel(time=np.sort(keep))


def weekly_usdm(template: GridTemplate, settings: Settings | None = None) -> xr.DataArray:
    """USDM category on the template grid, rasterised from the cached zips.

    Rasterises through the existing `UsdmSource._rasterize_zips`, which reads
    only `lat` and `lon` from its template, so the coordinates-only template is
    sufficient and the rasterisation code is shared rather than reimplemented.
    """
    from cofire.model.data.usdm import UsdmSource

    settings = settings or get_settings()
    src = UsdmSource(settings)
    raw = settings.raw_dir / "usdm"
    rng = DateRange(start=settings.train_start, end=settings.calibrate_end)
    src._rasterize_zips(raw, template.as_dataset(), rng)
    with xr.open_dataset(src._raster_path()) as ds:
        name = next(iter(ds.data_vars))
        return ds[name].load()


def erc_percentile(
    erc: xr.DataArray, train_end: pd.Timestamp, half_window: int = PCT_HALF_WINDOW
) -> xr.DataArray:
    """Per-cell week-of-year percentile of ERC, training years only.

    The same construction the full builder uses: a circular window of
    `half_window` weeks either side, because a single week holds about one
    value per training year and a percentile against four values can only
    return 0, 25, 50, 75 or 100.
    """
    t = pd.DatetimeIndex(erc["time"].values)
    woy = t.isocalendar().week.astype(int).clip(1, 52).to_numpy()
    train_mask = t <= train_end
    vals = np.asarray(erc.values, dtype=float)
    out = np.full(vals.shape, np.nan, dtype=float)

    n_lat, n_lon = vals.shape[1], vals.shape[2]
    for i in range(n_lat):
        for j in range(n_lon):
            series = vals[:, i, j]
            by_week: dict[int, list[float]] = {}
            for k in np.where(train_mask)[0]:
                v = series[k]
                if np.isfinite(v):
                    by_week.setdefault(int(woy[k]), []).append(float(v))
            pooled: dict[int, np.ndarray] = {}
            for w in range(1, 53):
                window = [((w - 1 + d) % 52) + 1 for d in range(-half_window, half_window + 1)]
                vs = [x for ww in window for x in by_week.get(ww, [])]
                if vs:
                    pooled[w] = np.sort(np.asarray(vs, dtype=float))
            for k in range(len(series)):
                hist = pooled.get(int(woy[k]))
                out[k, i, j] = _percentile(float(series[k]), hist)
    return xr.DataArray(out, dims=erc.dims, coords=erc.coords, name="erc_pct")


def build(settings: Settings | None = None, out_name: str = "features_a") -> Path:
    """Build configuration A's feature frame over the full available record."""
    settings = settings or get_settings()
    template = build_template(settings)
    LOGGER.info(
        "template: %d lat x %d lon, %d weeks %s..%s",
        template.lat.size, template.lon.size, len(template.weeks),
        template.weeks.min().date(), template.weeks.max().date(),
    )

    erc = weekly_erc(template, settings)
    usdm = weekly_usdm(template, settings)
    LOGGER.info("erc weeks %d, usdm weeks %d", erc.sizes["time"], usdm.sizes["time"])

    # Inner join on time: a week without both is not a usable row, and filling
    # either would invent data.
    common = np.intersect1d(erc["time"].values, usdm["time"].values)
    erc = erc.sel(time=common)
    usdm = usdm.sel(time=common)
    pct = erc_percentile(erc, pd.Timestamp(settings.train_end))

    rows = []
    lat = np.asarray(erc["lat"].values, dtype=float)
    lon = np.asarray(erc["lon"].values, dtype=float)
    times = pd.DatetimeIndex(erc["time"].values)
    for i, la in enumerate(lat):
        for j, lo in enumerate(lon):
            rows.append(
                pd.DataFrame(
                    {
                        "time": times,
                        "cell_id": f"{la:.4f}_{lo:.4f}",
                        "lat": la,
                        "lon": lo,
                        "erc": erc.values[:, i, j],
                        "usdm": usdm.values[:, i, j],
                        "erc_pct": pct.values[:, i, j],
                    }
                )
            )
    frame = pd.concat(rows, ignore_index=True)
    frame["woy"] = frame["time"].dt.isocalendar().week.astype(int)
    frame["month"] = frame["time"].dt.month
    doy = frame["time"].dt.dayofyear.to_numpy(dtype=float)
    frame["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    frame["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    out_root = settings.processed_dir / out_name
    out_root.mkdir(parents=True, exist_ok=True)
    for year, chunk in frame.groupby(frame["time"].dt.year):
        chunk.to_parquet(out_root / f"year={int(year)}.parquet", index=False)
    LOGGER.info("wrote %s (%d rows, %d weeks)", out_root, len(frame), times.size)
    return out_root


def load(settings: Settings | None = None, out_name: str = "features_a") -> pd.DataFrame:
    settings = settings or get_settings()
    root = settings.processed_dir / out_name
    files = sorted(root.glob("year=*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def add_horizons(frame: pd.DataFrame, horizons: tuple[int, ...] = (2, 4, 8)) -> pd.DataFrame:
    """Future USDM and ERC percentile, the labels the targets are built from."""
    out = frame.sort_values(["cell_id", "time"]).reset_index(drop=True)
    g = out.groupby("cell_id")
    for h in horizons:
        out[f"usdm_h{h}"] = g["usdm"].shift(-h)
        out[f"erc_pct_h{h}"] = g["erc_pct"].shift(-h)
    return out
