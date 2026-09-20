"""Validation-weighted average of arms that produced a prediction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.models import PRED_COLS, ConditionModel


class EnsembleModel(ConditionModel):
    name = "ensemble"

    def __init__(self, members: dict[str, ConditionModel], weights: dict[str, float] | None = None) -> None:
        self.members = members
        self.weights = weights or {k: 1.0 / len(members) for k in members}

    def fit(self, train: pd.DataFrame, valid: pd.DataFrame | None = None) -> None:
        del train, valid
        return None

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        stacked: dict[str, list[pd.Series]] = {c: [] for c in PRED_COLS}
        wts: dict[str, list[float]] = {c: [] for c in PRED_COLS}
        for name, model in self.members.items():
            pred = model.predict(frame)
            w = float(self.weights.get(name, 0.0))
            for col in PRED_COLS:
                if col not in pred.columns:
                    continue
                series = pred[col]
                if series.notna().sum() == 0:
                    continue
                stacked[col].append(series)
                wts[col].append(w)
        out = pd.DataFrame(index=frame.index)
        for col in PRED_COLS:
            if not stacked[col]:
                out[col] = np.nan
                continue
            arr = np.vstack([s.to_numpy(dtype=float) for s in stacked[col]])
            ww = np.asarray(wts[col], dtype=float)
            ww = ww / ww.sum()
            # NaNs in a member drop that member for that row.
            mask = np.isfinite(arr)
            num = np.nansum(arr * ww[:, None], axis=0)
            den = (mask * ww[:, None]).sum(axis=0)
            out[col] = np.where(den > 0, num / den, np.nan)
        return out

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "weights.json").write_text(pd.Series(self.weights).to_json())

    @classmethod
    def load(cls, path: Path) -> EnsembleModel:
        weights = dict(pd.read_json(path / "weights.json", typ="series"))
        return cls(members={}, weights={str(k): float(v) for k, v in weights.items()})
