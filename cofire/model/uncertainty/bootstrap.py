"""300-sample residual bootstrap intervals for both model arms.

Standard literature baseline: resample calibrate-split residuals with
replacement and add them to the point forecast. Same residual pool is used
for LightGBM and PI-ConvLSTM so the comparison is not confounded by retraining.
qhat/widths are frozen after the calibrate split; hindcast is evaluation only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cofire.model.config import HORIZONS_WEEKS, SEED, get_settings


@dataclass
class BootstrapState:
    residuals: dict[tuple[str, int], np.ndarray]  # (arm, horizon) → residual draws
    n_samples: int
    seed: int = SEED


def fit_bootstrap(frame: pd.DataFrame, arm: str, n_samples: int | None = None, seed: int = SEED) -> BootstrapState:
    settings = get_settings()
    n = n_samples or settings.bootstrap_samples
    resid: dict[tuple[str, int], np.ndarray] = {}
    for h in HORIZONS_WEEKS:
        y_col, hat = f"erc_pct_h{h}", f"erc_pct_h{h}_hat"
        if y_col not in frame.columns or hat not in frame.columns:
            continue
        r = (frame[y_col] - frame[hat]).to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        resid[(arm, h)] = r
        y_col, hat = f"usdm_h{h}", f"usdm_h{h}_hat"
        if y_col in frame.columns:
            ru = (frame[y_col] - frame[hat]).to_numpy(dtype=float)
            resid[(f"{arm}_usdm", h)] = ru[np.isfinite(ru)]
    return BootstrapState(residuals=resid, n_samples=n, seed=seed)


def bootstrap_interval(
    point: float,
    residuals: np.ndarray,
    n_samples: int,
    rng: np.random.Generator,
    q: float = 0.90,
) -> tuple[float, float]:
    if residuals.size == 0 or not np.isfinite(point):
        return float("nan"), float("nan")
    draws = rng.choice(residuals, size=n_samples, replace=True)
    lo = float(np.quantile(point + draws, (1.0 - q) / 2.0))
    hi = float(np.quantile(point + draws, 1.0 - (1.0 - q) / 2.0))
    return lo, hi


def attach_bootstrap(frame: pd.DataFrame, state: BootstrapState, arm: str) -> pd.DataFrame:
    rng = np.random.default_rng(state.seed)
    out = frame.copy()
    for h in HORIZONS_WEEKS:
        resid = state.residuals.get((arm, h), np.asarray([]))
        los, his = [], []
        for point in out.get(f"erc_pct_h{h}_hat", pd.Series(np.nan, index=out.index)):
            lo, hi = bootstrap_interval(float(point), resid, state.n_samples, rng)
            los.append(lo)
            his.append(hi)
        out[f"erc_pct_h{h}_boot_lo"] = los
        out[f"erc_pct_h{h}_boot_hi"] = his
    return out
