"""Optional external drought NetCDF. See docs/EXTERNAL_MODEL.md."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from cofire.model.config import HORIZONS_WEEKS, get_settings
from cofire.model.models import PRED_COLS, ConditionModel


class ExternalDroughtModel(ConditionModel):
    """Loads predictions from a NetCDF matching the grid. Does not train.

    When the file is missing, `predict` returns NaNs and `available` is False.
    Fire-condition columns are always NaN: this slot is drought-only.
    """

    name = "external_drought"

    def __init__(self, nc_path: Path | None = None) -> None:
        settings = get_settings()
        self.nc_path = Path(nc_path) if nc_path is not None else settings.external_drought_nc
        self.ds: xr.Dataset | None = None
        if self.nc_path.exists():
            self.ds = xr.open_dataset(self.nc_path)

    @property
    def available(self) -> bool:
        return self.ds is not None

    def fit(self, train: pd.DataFrame, valid: pd.DataFrame | None = None) -> None:
        del train, valid
        return None

    def as_feature(self, frame: pd.DataFrame) -> pd.Series:
        """Issue-time drought from `drought_now`, else NaN."""
        if self.ds is None or "drought_now" not in self.ds:
            return pd.Series(np.nan, index=frame.index)
        return self._lookup(frame, "drought_now")

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=frame.index)
        for col in PRED_COLS:
            out[col] = np.nan
        if self.ds is None:
            return out
        for h in HORIZONS_WEEKS:
            var = f"drought_h{h}"
            if var in self.ds:
                out[f"usdm_h{h}_hat"] = self._lookup(frame, var)
        return out

    def _lookup(self, frame: pd.DataFrame, var: str) -> pd.Series:
        assert self.ds is not None
        da = self.ds[var]
        values = []
        for row in frame.itertuples():
            t = pd.Timestamp(row.time)
            try:
                values.append(float(da.sel(time=t, lat=row.lat, lon=row.lon, method="nearest")))
            except (KeyError, ValueError):
                values.append(float("nan"))
        return pd.Series(values, index=frame.index)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "nc_path.txt").write_text(str(self.nc_path))

    @classmethod
    def load(cls, path: Path) -> ExternalDroughtModel:
        nc = Path((path / "nc_path.txt").read_text().strip())
        return cls(nc_path=nc)
