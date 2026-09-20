"""LightGBM arm: ordinal drought + ERC percentile, per horizon."""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from cofire.model.config import HORIZONS_WEEKS, SEED
from cofire.model.features import available_features
from cofire.model.models import PRED_COLS, ConditionModel


def _xy(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    cols = available_features(frame)
    mask = frame[target].notna() if target in frame.columns else pd.Series(False, index=frame.index)
    x = frame.loc[mask, cols].replace([np.inf, -np.inf], np.nan)
    y = frame.loc[mask, target].to_numpy(dtype=float)
    return x, y, cols


class LightGBMConditionModel(ConditionModel):
    name = "lightgbm"

    def __init__(self, seed: int = SEED) -> None:
        self.seed = seed
        self.models: dict[str, lgb.Booster] = {}
        self.feature_names: list[str] = []

    def _fit_one(self, x: pd.DataFrame, y: np.ndarray, valid: tuple[pd.DataFrame, np.ndarray] | None, objective: str) -> lgb.Booster:
        params = {
            "objective": objective,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_data_in_leaf": 8,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 1,
            "verbosity": -1,
            "seed": self.seed,
            "num_threads": 1,
        }
        dtrain = lgb.Dataset(x, label=y, free_raw_data=False)
        valid_sets = [dtrain]
        valid_names = ["train"]
        if valid is not None and len(valid[1]) > 0:
            dvalid = lgb.Dataset(valid[0], label=valid[1], free_raw_data=False)
            valid_sets.append(dvalid)
            valid_names.append("valid")
        return lgb.train(
            params,
            dtrain,
            num_boost_round=200,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(0)],
        )

    def fit(self, train: pd.DataFrame, valid: pd.DataFrame | None = None) -> None:
        self.feature_names = available_features(train)
        for h in HORIZONS_WEEKS:
            for target, obj in (
                (f"usdm_h{h}", "regression"),
                (f"erc_pct_h{h}", "regression"),
            ):
                x, y, _ = _xy(train, target)
                val_xy = _xy(valid, target)[:2] if valid is not None else None
                if y.size == 0:
                    continue
                self.models[target] = self._fit_one(x, y, val_xy, obj)
            for target in (f"usdm_ge2_h{h}", f"usdm_ge3_h{h}"):
                thresh = 2 if "ge2" in target else 3
                src = f"usdm_h{h}"
                if src not in train.columns:
                    continue
                work = train.copy()
                work[target] = (work[src] >= thresh).astype(float)
                x, y, _ = _xy(work, target)
                val_xy = None
                if valid is not None:
                    v = valid.copy()
                    v[target] = (v[src] >= thresh).astype(float)
                    val_xy = _xy(v, target)[:2]
                if y.size == 0:
                    continue
                self.models[target] = self._fit_one(x, y, val_xy, "binary")

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        cols = self.feature_names or available_features(frame)
        x = frame.reindex(columns=cols).replace([np.inf, -np.inf], np.nan)
        out = pd.DataFrame(index=frame.index)
        for col in PRED_COLS:
            key = col.replace("_hat", "")
            model = self.models.get(key)
            if model is None:
                out[col] = np.nan
                continue
            pred = model.predict(x)
            out[col] = pred
        return out

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        meta = {"feature_names": self.feature_names, "keys": list(self.models)}
        (path / "meta.json").write_text(json.dumps(meta))
        for key, booster in self.models.items():
            booster.save_model(str(path / f"{key}.txt"))

    @classmethod
    def load(cls, path: Path) -> LightGBMConditionModel:
        inst = cls()
        meta = json.loads((path / "meta.json").read_text())
        inst.feature_names = list(meta["feature_names"])
        for key in meta["keys"]:
            inst.models[key] = lgb.Booster(model_file=str(path / f"{key}.txt"))
        return inst
