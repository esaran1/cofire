"""ConditionModel interface. All forecast arms implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from cofire.model.config import HORIZONS_WEEKS

PRED_COLS = [
    *[f"usdm_h{h}_hat" for h in HORIZONS_WEEKS],
    *[f"erc_pct_h{h}_hat" for h in HORIZONS_WEEKS],
    *[f"usdm_ge2_h{h}_hat" for h in HORIZONS_WEEKS],
    *[f"usdm_ge3_h{h}_hat" for h in HORIZONS_WEEKS],
]


class ConditionModel(ABC):
    """Fit, predict, save, load. Never trains at API request time."""

    name: str

    @abstractmethod
    def fit(self, train: pd.DataFrame, valid: pd.DataFrame | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return a frame with PRED_COLS aligned to `frame.index`."""
        raise NotImplementedError

    @abstractmethod
    def save(self, path: Path) -> None:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> ConditionModel:
        raise NotImplementedError

    def extra(self) -> dict[str, Any]:
        return {}
