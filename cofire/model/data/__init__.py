"""Data source contract: fetch → cache → load → status."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

import xarray as xr


class SourceState(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "source unavailable"
    SKIPPED = "skipped"


@dataclass
class DateRange:
    start: date
    end: date


@dataclass
class SourceStatus:
    name: str
    state: SourceState
    url: str
    path: str | None = None
    checksum: str | None = None
    note: str = ""
    optional: bool = False
    records: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "url": self.url,
            "path": self.path,
            "checksum": self.checksum,
            "note": self.note,
            "optional": self.optional,
            "records": self.records,
            "extra": self.extra,
        }


class DataSource(ABC):
    name: str
    optional: bool = False
    url: str = ""

    @abstractmethod
    def fetch(self, date_range: DateRange) -> Path:
        """Download or reuse cache. Returns a local path. Idempotent."""

    @abstractmethod
    def load(self) -> xr.Dataset:
        """Open the processed product as xarray (empty dataset if unavailable)."""

    @abstractmethod
    def status(self) -> SourceStatus:
        """Snapshot used to write data/MANIFEST.json."""
