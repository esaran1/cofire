"""Orchestrate core + optional fetches. Incremental: skip years already on disk."""

from __future__ import annotations

import logging

from cofire.model.config import get_settings
from cofire.model.data import DateRange
from cofire.model.data.boundaries import BoundariesSource
from cofire.model.data.elevation import ElevationSource
from cofire.model.data.gridmet import GridmetSource
from cofire.model.data.manifest import write_manifest
from cofire.model.data.nifc import NifcSource
from cofire.model.data.optional import HrrrSource, NfmdSource, RawsSource, SmapSource
from cofire.model.data.snotel import SnotelSource
from cofire.model.data.usdm import UsdmSource
from cofire.model.log import setup_logging

LOGGER = logging.getLogger("cofire.data")


def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_dir)
    date_range = DateRange(start=settings.fetch_start, end=settings.data_end)
    LOGGER.info(
        "fetching %s to %s bbox=%s subset=%s",
        date_range.start,
        date_range.end,
        settings.bbox,
        settings.dev_subset,
    )
    gridmet = GridmetSource(settings)
    boundaries = BoundariesSource(settings)
    usdm = UsdmSource(settings)
    snotel = SnotelSource(settings)
    elev = ElevationSource(settings)
    nifc = NifcSource(settings)
    optionals = [NfmdSource(settings), RawsSource(settings), SmapSource(settings), HrrrSource(settings)]

    # Grid first: every other rasterizer needs the native 4 km template.
    gridmet.fetch(date_range)
    boundaries.fetch(date_range)
    usdm.fetch(date_range)
    # Persist station metadata before grid assignment.
    try:
        stations = snotel._colorado_snotel()  # noqa: SLF001
        snotel.persist_stations(stations)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("SNOTEL stations unavailable: %s", exc)
    snotel.fetch(date_range)
    elev.fetch(date_range)
    try:
        nifc.fetch(date_range)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("NIFC unavailable: %s", exc)
    for src in optionals:
        src.fetch(date_range)

    digest = write_manifest(
        settings.data_dir / "MANIFEST.json",
        [
            gridmet.status(),
            boundaries.status(),
            usdm.status(),
            snotel.status(),
            elev.status(),
            nifc.status(),
            *[o.status() for o in optionals],
        ],
    )
    LOGGER.info("MANIFEST hash=%s", digest)


if __name__ == "__main__":
    run()
