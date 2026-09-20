"""NRCS SNOTEL via AWDB REST: SWE percent of median, assigned to HUC8 then grid."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus
from cofire.model.dates import tuesdays
from cofire.model.http import USER_AGENT, SourceFetchError, sha256_bytes

LOGGER = logging.getLogger("cofire.data.snotel")

STATIONS_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/stations"
DATA_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"


class SnotelSource(DataSource):
    name = "NRCS SNOTEL"
    optional = False
    url = STATIONS_URL

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last = SourceStatus(name=self.name, state=SourceState.UNAVAILABLE, url=self.url, note="not fetched")

    def _out_path(self) -> Path:
        return self.settings.processed_dir / "snotel" / "swe_pct_median.nc"

    def fetch(self, date_range: DateRange) -> Path:
        try:
            stations = self._colorado_snotel()
            daily = self._pull_daily(stations, date_range)
            weekly = self._percent_of_median(daily, date_range)
            path = self._write_grid(weekly)
            payload = path.read_bytes()
            self._last = SourceStatus(
                name=self.name,
                state=SourceState.OK,
                url=self.url,
                path=str(path),
                checksum=sha256_bytes(payload),
                records=len(stations),
                note=f"{len(stations)} CO SNOTEL stations",
            )
            return path
        except SourceFetchError as exc:
            LOGGER.warning("%s", exc)
            self._last = SourceStatus(
                name=self.name, state=SourceState.UNAVAILABLE, url=exc.url, note=str(exc)
            )
            return self._out_path()

    def _colorado_snotel(self) -> pd.DataFrame:
        try:
            response = requests.get(STATIONS_URL, timeout=90, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            rows = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SourceFetchError(self.name, STATIONS_URL, str(exc)) from exc
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise SourceFetchError(self.name, STATIONS_URL, "empty station list")
        mask = (frame.get("stateCode") == "CO") & (frame.get("networkCode") == "SNTL")
        out = frame.loc[mask].copy()
        if out.empty:
            raise SourceFetchError(self.name, STATIONS_URL, "no CO SNOTEL stations after filter")
        out["huc8"] = out["huc"].astype(str).str[:8]
        return out

    def _pull_daily(self, stations: pd.DataFrame, date_range: DateRange) -> pd.DataFrame:
        triplets = stations["stationTriplet"].tolist()
        cache = self.settings.cache_dir / "snotel_daily.parquet"
        if cache.exists():
            cached = pd.read_parquet(cache)
            cached["date"] = pd.to_datetime(cached["date"]).dt.date
            if cached["date"].min() <= date_range.start and cached["date"].max() >= date_range.end:
                return cached
        chunks: list[pd.DataFrame] = []
        batch = 25
        for i in range(0, len(triplets), batch):
            group = triplets[i : i + batch]
            params = {
                "stationTriplets": ",".join(group),
                "elements": "WTEQ,PREC",
                "duration": "DAILY",
                "beginDate": date_range.start.isoformat(),
                "endDate": date_range.end.isoformat(),
                "centralTendencyType": "NONE",
            }
            try:
                response = requests.get(DATA_URL, params=params, timeout=120, headers={"User-Agent": USER_AGENT})
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                LOGGER.warning("SNOTEL batch %s failed: %s", i, exc)
                continue
            chunks.extend(_flatten_awdb(payload))
        if not chunks:
            raise SourceFetchError(self.name, DATA_URL, "no daily SWE rows returned")
        daily = pd.concat(chunks, ignore_index=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        daily.to_parquet(cache, index=False)
        daily["date"] = pd.to_datetime(daily["date"]).dt.date
        return daily

    def _percent_of_median(self, daily: pd.DataFrame, date_range: DateRange) -> pd.DataFrame:
        """Median SWE by station and day-of-year on the training window only."""
        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"])
        daily["doy"] = daily["date"].dt.dayofyear
        train_end = pd.Timestamp(self.settings.train_end)
        train = daily[daily["date"] <= train_end]
        med = train.groupby(["stationTriplet", "doy"], as_index=False)["swe"].median()
        med = med.rename(columns={"swe": "swe_median"})
        merged = daily.merge(med, on=["stationTriplet", "doy"], how="left")
        merged["swe_pct"] = np.where(
            merged["swe_median"].fillna(0) > 0,
            100.0 * merged["swe"] / merged["swe_median"],
            np.nan,
        )
        merged["huc8"] = merged["stationTriplet"].map(
            self._station_huc8_map() if False else dict(
                zip(
                    daily.get("stationTriplet", pd.Series(dtype=str)),
                    daily.get("huc8", pd.Series(dtype=str)),
                    strict=False,
                )
            )
        )
        # Re-join HUC8 from the station file stored beside the cache.
        stations_path = self.settings.cache_dir / "snotel_stations.parquet"
        if stations_path.exists():
            st = pd.read_parquet(stations_path)
            merged = merged.drop(columns=["huc8"], errors="ignore").merge(
                st[["stationTriplet", "huc8"]], on="stationTriplet", how="left"
            )
        weekly = (
            merged.set_index("date")
            .groupby(["stationTriplet", "huc8"])
            .resample("W-TUE")["swe_pct"]
            .mean()
            .reset_index()
        )
        basin = weekly.groupby(["date", "huc8"], as_index=False)["swe_pct"].mean()
        basin = basin[(basin["date"] >= pd.Timestamp(date_range.start)) & (basin["date"] <= pd.Timestamp(date_range.end))]
        return basin

    def _station_huc8_map(self) -> dict[str, str]:
        path = self.settings.cache_dir / "snotel_stations.parquet"
        if not path.exists():
            return {}
        st = pd.read_parquet(path)
        return dict(zip(st["stationTriplet"], st["huc8"].astype(str), strict=False))

    def _write_grid(self, basin_weekly: pd.DataFrame) -> Path:
        """Assign each grid cell the SWE % of its HUC8; cells without stations get domain mean."""
        grid_files = sorted((self.settings.processed_dir / "gridmet").glob("weekly_*.nc"))
        if not grid_files:
            raise SourceFetchError(self.name, "", "gridMET weekly cube missing")
        template = xr.open_dataset(grid_files[0])
        lats = template["lat"].values
        lons = template["lon"].values
        template.close()
        huc_path = self.settings.processed_dir / "boundaries" / "cell_huc8.parquet"
        weeks = tuesdays(self.settings.fetch_start, self.settings.data_end)
        cube = np.full((len(weeks), len(lats), len(lons)), np.nan, dtype=np.float32)
        domain_mean = basin_weekly.groupby("date")["swe_pct"].mean()
        if huc_path.exists():
            cells = pd.read_parquet(huc_path)
            huc_lookup = {(round(r.lat, 4), round(r.lon, 4)): str(r.huc8) for r in cells.itertuples()}
        else:
            huc_lookup = {}
            LOGGER.warning("cell_huc8.parquet missing; assigning domain-mean SWE to every cell")
        basin_map: dict[tuple[pd.Timestamp, str], float] = {}
        for row in basin_weekly.itertuples():
            basin_map[(pd.Timestamp(row.date), str(row.huc8))] = float(row.swe_pct)
        for ti, week in enumerate(weeks):
            ts = pd.Timestamp(week)
            fallback = float(domain_mean.get(ts, np.nan))
            for yi, lat in enumerate(lats):
                for xi, lon in enumerate(lons):
                    huc = huc_lookup.get((round(float(lat), 4), round(float(lon), 4)))
                    val = basin_map.get((ts, huc), fallback) if huc else fallback
                    cube[ti, yi, xi] = val
        ds = xr.Dataset(
            {"swe_pct_median": (("time", "lat", "lon"), cube)},
            coords={"time": pd.to_datetime(weeks), "lat": lats, "lon": lons},
        )
        out = self._out_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(out)
        return out

    def load(self) -> xr.Dataset:
        path = self._out_path()
        if not path.exists():
            return xr.Dataset()
        return xr.open_dataset(path)

    def status(self) -> SourceStatus:
        return self._last

    def persist_stations(self, stations: pd.DataFrame) -> None:
        path = self.settings.cache_dir / "snotel_stations.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        stations.to_parquet(path, index=False)


def _flatten_awdb(payload: object) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    rows = payload if isinstance(payload, list) else []
    for station in rows:
        if not isinstance(station, dict):
            continue
        triplet = str(station.get("stationTriplet", ""))
        for series in station.get("data") or station.get("dataList") or []:
            if not isinstance(series, dict):
                continue
            element = str(series.get("stationElement", {}).get("elementCode") or series.get("elementCd") or "")
            if element not in {"WTEQ", "PREC"}:
                continue
            values = series.get("values") or []
            dates = series.get("dates") or []
            if not dates and isinstance(values, list) and values and isinstance(values[0], dict):
                recs = [
                    {
                        "stationTriplet": triplet,
                        "date": r.get("date"),
                        "swe": r.get("value") if element == "WTEQ" else np.nan,
                        "prec": r.get("value") if element == "PREC" else np.nan,
                    }
                    for r in values
                ]
                frames.append(pd.DataFrame(recs))
                continue
            recs = []
            for d, v in zip(dates, values, strict=False):
                recs.append(
                    {
                        "stationTriplet": triplet,
                        "date": d,
                        "swe": v if element == "WTEQ" else np.nan,
                        "prec": v if element == "PREC" else np.nan,
                    }
                )
            if recs:
                frames.append(pd.DataFrame(recs))
    return frames
