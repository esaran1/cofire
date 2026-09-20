"""Optional sources. Skipped unless a feature flag and credentials are present."""

from __future__ import annotations

import logging

import xarray as xr

from cofire.model.config import Settings, get_settings
from cofire.model.data import DataSource, DateRange, SourceState, SourceStatus

LOGGER = logging.getLogger("cofire.data.optional")


class OptionalSource(DataSource):
    optional = True

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.SKIPPED,
            url=self.url,
            optional=True,
            note="disabled or credentials absent",
        )

    def fetch(self, date_range: DateRange) -> type[None] | None:  # type: ignore[override]
        del date_range
        LOGGER.info("%s skipped (optional)", self.name)
        return None

    def load(self) -> xr.Dataset:
        return xr.Dataset()

    def status(self) -> SourceStatus:
        return self._last


class NfmdSource(OptionalSource):
    name = "NFMD"
    url = "https://fems.fs2c.usda.gov/"

    def fetch(self, date_range: DateRange) -> None:  # type: ignore[override]
        del date_range
        if not self.settings.enable_nfmd:
            self._last.note = "flag COFIRE_ENABLE_NFMD off"
            return
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.UNAVAILABLE,
            url=self.url,
            optional=True,
            note="FEMS/NFMD requires auth in v0; skipped",
        )


class RawsSource(OptionalSource):
    name = "Synoptic RAWS"
    url = "https://api.synopticdata.com/v2/stations/timeseries"

    def fetch(self, date_range: DateRange) -> None:  # type: ignore[override]
        del date_range
        if not self.settings.enable_raws or not self.settings.synoptic_token:
            self._last.note = "no SYNOPTIC_TOKEN"
            return
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.UNAVAILABLE,
            url=self.url,
            optional=True,
            note="token present but v0 does not pull RAWS until the demo window needs it",
        )


class SmapSource(OptionalSource):
    name = "SMAP L4 / VIIRS NDVI"
    url = "https://earthdata.nasa.gov/"

    def fetch(self, date_range: DateRange) -> None:  # type: ignore[override]
        del date_range
        if not self.settings.enable_smap or not self.settings.earthdata_username:
            self._last.note = "no Earthdata credentials"
            return
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.UNAVAILABLE,
            url=self.url,
            optional=True,
            note="credentials present; v0 skips SMAP/VIIRS download",
        )


class HrrrSource(OptionalSource):
    name = "HRRR (Herbie)"
    url = "https://rapidrefresh.noaa.gov/hrrr/"

    def fetch(self, date_range: DateRange) -> None:  # type: ignore[override]
        del date_range
        if not self.settings.enable_hrrr:
            self._last.note = "flag COFIRE_ENABLE_HRRR off"
            return
        self._last = SourceStatus(
            name=self.name,
            state=SourceState.UNAVAILABLE,
            url=self.url,
            optional=True,
            note="Herbie not in core deps; skip",
        )
