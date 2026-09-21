"""Feature engineering for one grid cell × one USDM week.

INTENDED FOR HAND-REWRITE. Keep this file small. Every transform that
normalizes, ranks, or fits a distribution MUST use statistics computed on the
training window only. `TrainingStats` is frozen after `fit_training_stats` and
`transform` is not allowed to look at the full series.

Leakage rules (enforced in tests/test_features.py):
  * SPI/SPEI gamma parameters: training years, per cell, per calendar month
  * ERC/BI percentiles: training years, per cell, per week-of-year
  * fm100/fm1000 anomalies: training mean, per cell, per week-of-year
  * rolling sums and lags are just shifts — they are not leakage as long as
    the caller does not feed future rows (hindcast cutoff handles that)

Observer-report weights (documented, not learned):
  stock_tank_dry +0.15, lawn_crispy +0.10, creek_low +0.12,
  soil_cracked +0.10, vegetation_green -0.08
These columns start at 0. The API nudge is a cached model delta from bumping
a count by 1, not an animation.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from cofire.model.config import HORIZONS_WEEKS, Settings, get_settings

LAGS_WEEKS = (1, 2, 4, 8)
ROLL_WEEKS = (4, 8, 13, 26, 52)
# Weekly stand-ins for 30/90/180/365-day SPI windows.
SPI_WINDOWS = (4, 13, 26, 52)
SPI_LABELS = (30, 90, 180, 365)
GRIDMET_MEAN_VARS = ("tmmx", "tmmn", "rmin", "rmax", "vs", "vpd", "erc", "bi", "fm100", "fm1000", "srad")
GRIDMET_SUM_VARS = ("pr", "pet")
OBS_WEIGHTS: dict[str, float] = {
    "stock_tank_dry": 0.15,
    "lawn_crispy": 0.10,
    "creek_low": 0.12,
    "soil_cracked": 0.10,
    "vegetation_green": -0.08,
}


@dataclass
class GammaParams:
    """Shape/loc/scale of a gamma fit, plus the mass at zero (SPI mixed dist)."""

    shape: float
    loc: float
    scale: float
    p_zero: float
    n: int


@dataclass
class TrainingStats:
    """Everything derived from the training window. Do not mutate after fit."""

    # cell_id -> month 1-12 -> window weeks -> params
    spi_gamma: dict[str, dict[int, dict[int, GammaParams]]] = field(default_factory=dict)
    spei_gamma: dict[str, dict[int, dict[int, GammaParams]]] = field(default_factory=dict)
    # cell_id -> week_of_year -> sorted training values (for percentileofscore)
    erc_by_woy: dict[str, dict[int, np.ndarray]] = field(default_factory=dict)
    bi_by_woy: dict[str, dict[int, np.ndarray]] = field(default_factory=dict)
    fm100_mean: dict[str, dict[int, float]] = field(default_factory=dict)
    fm1000_mean: dict[str, dict[int, float]] = field(default_factory=dict)
    tmmx_mean: dict[str, dict[int, float]] = field(default_factory=dict)
    tmmx_std: dict[str, dict[int, float]] = field(default_factory=dict)
    pr_roll13_mean: dict[str, float] = field(default_factory=dict)
    pr_roll13_std: dict[str, float] = field(default_factory=dict)
    train_end: pd.Timestamp | None = None


# Half-width of the circular week window used for percentile climatologies.
# 3 gives 7 weeks x ~4 training years = ~28 values, enough to resolve a 97th
# percentile. A single week gives ~4, which cannot.
PCT_HALF_WINDOW = 3


def _fit_gamma(values: np.ndarray) -> GammaParams:
    """McKee-style SPI gamma: zeros handled as a point mass, positives ~ Gamma."""
    x = values[np.isfinite(values)]
    if x.size < 8:
        return GammaParams(shape=1.0, loc=0.0, scale=1.0, p_zero=1.0, n=int(x.size))
    p_zero = float(np.mean(x <= 0))
    positive = x[x > 0]
    if positive.size < 5:
        return GammaParams(shape=1.0, loc=0.0, scale=1.0, p_zero=p_zero, n=int(x.size))
    # floc=0: precipitation is non-negative; let scipy estimate shape and scale.
    shape, loc, scale = stats.gamma.fit(positive, floc=0)
    return GammaParams(shape=float(shape), loc=float(loc), scale=float(scale), p_zero=p_zero, n=int(x.size))


def spi_from_params(x: float, params: GammaParams) -> float:
    """SPI = Φ^{-1}(H(x)) with H the mixed CDF (zeros + gamma)."""
    if not np.isfinite(x) or params.n < 8:
        return float("nan")
    if x <= 0:
        # Mid-probability of the zero atom, not 0, so SPI is finite.
        h = params.p_zero / 2.0
    else:
        cdf = float(stats.gamma.cdf(x, params.shape, loc=params.loc, scale=params.scale))
        h = params.p_zero + (1.0 - params.p_zero) * cdf
    h = min(max(h, 1e-6), 1.0 - 1e-6)
    return float(stats.norm.ppf(h))


def add_calendar(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"])
    doy = out["time"].dt.dayofyear.astype(float)
    out["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    out["woy"] = out["time"].dt.strftime("%U").astype(int)
    out["month"] = out["time"].dt.month
    return out


def add_lags_and_rolls(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-cell lags of current-week aggregates and rolling precipitation sums."""
    out = frame.sort_values(["cell_id", "time"]).drop_duplicates(["cell_id", "time"], keep="last").copy()
    grouped = out.groupby("cell_id", sort=False)
    base_cols = [c for c in [*GRIDMET_MEAN_VARS, *GRIDMET_SUM_VARS] if c in out.columns]
    for lag in LAGS_WEEKS:
        for col in base_cols:
            out[f"{col}_lag{lag}"] = grouped[col].shift(lag)
    if "pr" in out.columns:
        for window in ROLL_WEEKS:
            out[f"pr_roll{window}"] = grouped["pr"].transform(lambda s, w=window: s.rolling(w, min_periods=max(2, w // 2)).sum())
    if "pet" in out.columns:
        out["pr_minus_pet"] = out.get("pr", 0) - out["pet"]
        for window in SPI_WINDOWS:
            out[f"wb_roll{window}"] = grouped["pr_minus_pet"].transform(
                lambda s, w=window: s.rolling(w, min_periods=max(2, w // 2)).sum()
            )
        for window in SPI_WINDOWS:
            out[f"pr_win{window}"] = grouped["pr"].transform(
                lambda s, w=window: s.rolling(w, min_periods=max(2, w // 2)).sum()
            )
    if "usdm" in out.columns:
        out["usdm_trend_4w"] = out["usdm"] - grouped["usdm"].shift(4)
    return out


def fit_training_stats(frame: pd.DataFrame, train_end: pd.Timestamp) -> TrainingStats:
    """Fit every distribution/percentile using rows with time <= train_end only."""
    train = frame.loc[pd.to_datetime(frame["time"]) <= train_end].copy()
    stats_out = TrainingStats(train_end=pd.Timestamp(train_end))
    for cell, chunk in train.groupby("cell_id"):
        cell_id = str(cell)
        stats_out.spi_gamma[cell_id] = {}
        stats_out.spei_gamma[cell_id] = {}
        stats_out.erc_by_woy[cell_id] = {}
        stats_out.bi_by_woy[cell_id] = {}
        stats_out.fm100_mean[cell_id] = {}
        stats_out.fm1000_mean[cell_id] = {}
        stats_out.tmmx_mean[cell_id] = {}
        stats_out.tmmx_std[cell_id] = {}
        for month, mchunk in chunk.groupby("month"):
            month_i = int(month)
            stats_out.spi_gamma[cell_id][month_i] = {}
            stats_out.spei_gamma[cell_id][month_i] = {}
            for window in SPI_WINDOWS:
                col = f"pr_win{window}"
                if col in mchunk:
                    stats_out.spi_gamma[cell_id][month_i][window] = _fit_gamma(mchunk[col].to_numpy(dtype=float))
                wb = f"wb_roll{window}"
                if wb in mchunk:
                    # Shift water-balance to be non-negative for a gamma: add a cell-month min.
                    wb_vals = mchunk[wb].to_numpy(dtype=float)
                    offset = np.nanmin(wb_vals) if np.isfinite(wb_vals).any() else 0.0
                    stats_out.spei_gamma[cell_id][month_i][window] = _fit_gamma(wb_vals - offset + 1e-3)
                    stats_out.spei_gamma[cell_id][month_i][window] = GammaParams(
                        **{**stats_out.spei_gamma[cell_id][month_i][window].__dict__, "n": int(np.isfinite(wb_vals).sum())}
                    )
                    # Store the offset in loc so transform can apply the same shift.
                    gp = stats_out.spei_gamma[cell_id][month_i][window]
                    stats_out.spei_gamma[cell_id][month_i][window] = GammaParams(
                        shape=gp.shape, loc=float(offset), scale=gp.scale, p_zero=gp.p_zero, n=gp.n
                    )
        # A circular +/- PCT_HALF_WINDOW week window, not the single week. One
        # week of training holds one value per training year, about 4, and a
        # percentile against 4 points can only return 0, 25, 50, 75 or 100. That
        # coarseness made f_gt80, f_gt90 and f_gt97 the identical target: 17.1%
        # of erc_pct values sat at exactly 100, so every threshold above 80
        # selected the same rows. Widening to +/-3 weeks gives about 28 values
        # per cell-week, which resolves the upper tail the fire targets need.
        woy_groups = {int(w): c for w, c in chunk.groupby("woy")}
        for w in sorted(woy_groups):
            weeks_in_window = [
                ((w - 1 + d) % 52) + 1 for d in range(-PCT_HALF_WINDOW, PCT_HALF_WINDOW + 1)
            ]
            parts = [woy_groups[x] for x in weeks_in_window if x in woy_groups]
            if not parts:
                continue
            pooled = pd.concat(parts)
            if "erc" in pooled:
                stats_out.erc_by_woy[cell_id][w] = np.sort(
                    pooled["erc"].dropna().to_numpy(dtype=float)
                )
            if "bi" in pooled:
                stats_out.bi_by_woy[cell_id][w] = np.sort(
                    pooled["bi"].dropna().to_numpy(dtype=float)
                )
            # Anomaly moments stay on the single week. They are means, not
            # order statistics, so the 4-value sample that ruins a 97th
            # percentile is adequate for a mean, and widening them would blur a
            # genuine seasonal signal.
            wchunk = woy_groups[w]
            if "fm100" in wchunk:
                stats_out.fm100_mean[cell_id][w] = float(wchunk["fm100"].mean())
            if "fm1000" in wchunk:
                stats_out.fm1000_mean[cell_id][w] = float(wchunk["fm1000"].mean())
            if "tmmx" in wchunk:
                stats_out.tmmx_mean[cell_id][w] = float(wchunk["tmmx"].mean())
                stats_out.tmmx_std[cell_id][w] = float(wchunk["tmmx"].std() or 1.0)
        if "pr_roll13" in chunk:
            stats_out.pr_roll13_mean[cell_id] = float(chunk["pr_roll13"].mean())
            stats_out.pr_roll13_std[cell_id] = float(chunk["pr_roll13"].std() or 1.0)
    return stats_out


def _percentile(value: float, hist: np.ndarray | None) -> float:
    """Delegates to the single reference implementation.

    Previously `kind="weak"`, which reports the fraction at or below and so
    skews a value drawn from its own pool upward by 100/(2n). The reference
    uses `kind="mean"`. Measured on Larimer, the two disagreed on 79.9% of
    cell-weeks with a maximum difference of 14.7 percentile points.
    """
    from cofire.model.erc_pct import percentile_of

    return percentile_of(value, hist)


def transform(frame: pd.DataFrame, training_stats: TrainingStats) -> pd.DataFrame:
    """Apply frozen training statistics. Safe to call on validate/calibrate/hindcast."""
    out = frame.copy()
    spi_cols = {label: np.full(len(out), np.nan) for label in SPI_LABELS}
    spei_cols = {label: np.full(len(out), np.nan) for label in SPI_LABELS}
    erc_pct = np.full(len(out), np.nan)
    bi_pct = np.full(len(out), np.nan)
    fm100_anom = np.full(len(out), np.nan)
    fm1000_anom = np.full(len(out), np.nan)
    tmmx_anom = np.full(len(out), np.nan)
    for i, row in enumerate(out.itertuples()):
        cell = str(row.cell_id)
        month = int(row.month)
        woy = int(row.woy)
        for window, label in zip(SPI_WINDOWS, SPI_LABELS, strict=True):
            gp = training_stats.spi_gamma.get(cell, {}).get(month, {}).get(window)
            col = f"pr_win{window}"
            if gp is not None and col in out.columns:
                spi_cols[label][i] = spi_from_params(float(getattr(row, col)), gp)
            sp = training_stats.spei_gamma.get(cell, {}).get(month, {}).get(window)
            wb = f"wb_roll{window}"
            if sp is not None and wb in out.columns:
                # loc stored the training offset; shift the same way before the CDF.
                spei_cols[label][i] = spi_from_params(float(getattr(row, wb)) - sp.loc + 1e-3, sp)
        erc_pct[i] = _percentile(float(getattr(row, "erc", np.nan)), training_stats.erc_by_woy.get(cell, {}).get(woy))
        bi_pct[i] = _percentile(float(getattr(row, "bi", np.nan)), training_stats.bi_by_woy.get(cell, {}).get(woy))
        fm100_mu = training_stats.fm100_mean.get(cell, {}).get(woy, np.nan)
        fm1000_mu = training_stats.fm1000_mean.get(cell, {}).get(woy, np.nan)
        tmmx_mu = training_stats.tmmx_mean.get(cell, {}).get(woy, np.nan)
        tmmx_sd = training_stats.tmmx_std.get(cell, {}).get(woy, 1.0) or 1.0
        fm100_anom[i] = float(getattr(row, "fm100", np.nan)) - fm100_mu
        fm1000_anom[i] = float(getattr(row, "fm1000", np.nan)) - fm1000_mu
        tmmx_anom[i] = (float(getattr(row, "tmmx", np.nan)) - tmmx_mu) / tmmx_sd
    for label in SPI_LABELS:
        out[f"spi_{label}"] = spi_cols[label]
        out[f"spei_{label}"] = spei_cols[label]
    out["erc_pct"] = erc_pct
    out["bi_pct"] = bi_pct
    out["fm100_anom"] = fm100_anom
    out["fm1000_anom"] = fm1000_anom
    out["tmmx_anom"] = tmmx_anom
    stacked = np.vstack([erc_pct, bi_pct])
    with np.errstate(all="ignore"):
        out["fire_index"] = np.nanmean(stacked, axis=0)
    for name in OBS_WEIGHTS:
        col = f"obs_{name}"
        if col not in out.columns:
            out[col] = 0.0
    if "swe_pct_median" not in out.columns:
        out["swe_pct_median"] = np.nan
    if "elev_mean" not in out.columns:
        out["elev_mean"] = np.nan
        out["elev_roughness"] = np.nan
    return out


def add_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Future USDM category and ERC percentile at each horizon. Shifts per cell."""
    out = frame.sort_values(["cell_id", "time"]).drop_duplicates(["cell_id", "time"], keep="last").copy()
    grouped = out.groupby("cell_id", sort=False)
    for h in HORIZONS_WEEKS:
        if "usdm" in out.columns:
            out[f"usdm_h{h}"] = grouped["usdm"].shift(-h)
        if "erc_pct" in out.columns:
            out[f"erc_pct_h{h}"] = grouped["erc_pct"].shift(-h)
        if "fire_index" in out.columns:
            out[f"fire_index_h{h}"] = grouped["fire_index"].shift(-h)
    return out


FEATURE_COLUMNS = [
    *[v for v in (*GRIDMET_MEAN_VARS, *GRIDMET_SUM_VARS)],
    *[f"{v}_lag{lag}" for lag in LAGS_WEEKS for v in (*GRIDMET_MEAN_VARS, *GRIDMET_SUM_VARS)],
    *[f"pr_roll{w}" for w in ROLL_WEEKS],
    *[f"spi_{label}" for label in SPI_LABELS],
    *[f"spei_{label}" for label in SPI_LABELS],
    "erc_pct",
    "bi_pct",
    "fm100_anom",
    "fm1000_anom",
    "tmmx_anom",
    "swe_pct_median",
    "elev_mean",
    "elev_roughness",
    "doy_sin",
    "doy_cos",
    "usdm",
    "usdm_trend_4w",
    *[f"obs_{name}" for name in OBS_WEIGHTS],
]


def available_features(frame: pd.DataFrame) -> list[str]:
    return [c for c in FEATURE_COLUMNS if c in frame.columns]


def persist_features(frame: pd.DataFrame, root: Path) -> None:
    """Parquet feature store partitioned by year."""
    root.mkdir(parents=True, exist_ok=True)
    tmp = frame.copy()
    tmp["year"] = pd.to_datetime(tmp["time"]).dt.year
    for year, chunk in tmp.groupby("year"):
        chunk.drop(columns=["year"]).to_parquet(root / f"year={int(year)}.parquet", index=False)


def load_features(root: Path, years: Iterable[int] | None = None) -> pd.DataFrame:
    files = sorted(root.glob("year=*.parquet"))
    if years is not None:
        want = {int(y) for y in years}
        files = [p for p in files if int(p.stem.split("=")[1]) in want]
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def cubes_to_frame(settings: Settings | None = None) -> pd.DataFrame:
    """Stack weekly cubes into a long table. Missing sources become NaN columns."""
    import xarray as xr

    settings = settings or get_settings()
    grid_files = sorted((settings.processed_dir / "gridmet").glob("weekly_*.nc"))
    if not grid_files:
        raise FileNotFoundError("no gridMET weekly cubes — run `make data` first")
    opened = [xr.open_dataset(str(p)) for p in grid_files]
    gm = xr.concat(opened, dim="time") if len(opened) > 1 else opened[0]
    gm = gm.sortby("time")
    # Yearly weekly cubes overlap by one Tuesday at each year boundary.
    time_index = pd.Index(gm["time"].values)
    gm = gm.isel(time=~time_index.duplicated(keep="last"))
    frame = gm.to_dataframe().reset_index()
    for ds in opened:
        ds.close()
    gm.close()
    frame = frame.rename(columns={"day": "time"})
    frame["time"] = pd.to_datetime(frame["time"])
    frame["cell_id"] = [
        f"{float(lat):.4f}_{float(lon):.4f}"
        for lat, lon in zip(frame["lat"].to_numpy(), frame["lon"].to_numpy(), strict=False)
    ]

    def _merge_cube(path: Path, var: str) -> pd.DataFrame:
        if not path.exists():
            return frame
        ds = xr.open_dataset(path)
        extra = ds.to_dataframe().reset_index()
        ds.close()
        extra["time"] = pd.to_datetime(extra["time"])
        cols = [c for c in extra.columns if c in {"time", "lat", "lon", var} or c.endswith(var)]
        return frame.merge(extra[cols], on=["time", "lat", "lon"], how="left")

    frame = _merge_cube(settings.processed_dir / "usdm" / "weekly.nc", "usdm")
    frame = _merge_cube(settings.processed_dir / "snotel" / "swe_pct_median.nc", "swe_pct_median")
    elev_path = settings.processed_dir / "elevation" / "grid.nc"
    if elev_path.exists():
        elev = xr.open_dataset(elev_path).to_dataframe().reset_index()
        frame = frame.merge(elev, on=["lat", "lon"], how="left")
    return frame


def build_feature_store(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw = cubes_to_frame(settings)
    raw = add_calendar(raw)
    raw = add_lags_and_rolls(raw)
    train_end = pd.Timestamp(settings.train_end)
    training_stats = fit_training_stats(raw, train_end)
    feats = transform(raw, training_stats)
    feats = add_targets(feats)
    root = settings.processed_dir / "features"
    persist_features(feats, root)
    # Persist stats for conformal / what-if export.
    import pickle

    stats_path = settings.artifacts_dir / "training_stats.pkl"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_bytes(pickle.dumps(training_stats))
    return root


if __name__ == "__main__":
    build_feature_store()
