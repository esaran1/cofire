"""Split conformal + adaptive conformal inference (ACI).

INTENDED FOR HAND-REWRITE. Target coverage 0.90. `qhat` is computed on the
calibrate split and frozen. Only alpha updates online (learning rate 0.01).
The hindcast is reported, never used to retune qhat.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import ACI_LR, COVERAGE_TARGET, HORIZONS_WEEKS


@dataclass
class CellState:
    qhat: float
    alpha: float
    coverage_target: float = COVERAGE_TARGET
    n_cal: int = 0


def split_conformal_qhat(residuals: np.ndarray, alpha: float) -> float:
    """Quantile of |residual| with the finite-sample correction (n+1)/n."""
    r = np.sort(np.abs(residuals[np.isfinite(residuals)]))
    n = r.size
    if n == 0:
        return float("nan")
    q_level = min(1.0, np.ceil((n + 1) * (1.0 - alpha)) / n)
    idx = min(n - 1, max(0, int(np.ceil(q_level * n) - 1)))
    return float(r[idx])


def aci_update(alpha: float, missed: bool, target: float = COVERAGE_TARGET, lr: float = ACI_LR) -> float:
    """alpha_{t+1} = clip(alpha_t + lr * (target - err_t), 0.01, 0.5). err=1 on a miss."""
    err = 1.0 if missed else 0.0
    nxt = alpha + lr * (target - err)
    return float(np.clip(nxt, 0.01, 0.5))


def ordinal_set(scores: np.ndarray, alpha: float) -> list[int]:
    """Include classes from highest score down until cumulative mass ≥ 1-alpha."""
    order = np.argsort(-scores)
    picked: list[int] = []
    acc = 0.0
    for cls in order:
        picked.append(int(cls))
        acc += float(scores[cls])
        if acc >= 1.0 - alpha:
            break
    return sorted(picked)


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - np.max(logits)
    e = np.exp(z)
    return np.asarray(e / np.clip(e.sum(), 1e-9, None), dtype=float)


class ConformalCalibrator:
    """Per-cell, per-horizon, per-target (erc continuous; usdm ordinal sets)."""

    def __init__(self, coverage: float = COVERAGE_TARGET) -> None:
        self.coverage = coverage
        self.erc: dict[tuple[str, int], CellState] = {}
        self.usdm_q: dict[tuple[str, int], CellState] = {}

    def fit(self, frame: pd.DataFrame) -> None:
        """frame must have y and yhat columns on the calibrate split."""
        for h in HORIZONS_WEEKS:
            y_col, hat_col = f"erc_pct_h{h}", f"erc_pct_h{h}_hat"
            if y_col in frame.columns and hat_col in frame.columns:
                for cell, chunk in frame.groupby("cell_id"):
                    resid = (chunk[y_col] - chunk[hat_col]).to_numpy(dtype=float)
                    q = split_conformal_qhat(resid, 1.0 - self.coverage)
                    self.erc[(str(cell), h)] = CellState(qhat=q, alpha=1.0 - self.coverage, n_cal=int(np.isfinite(resid).sum()))
            y_col, hat_col = f"usdm_h{h}", f"usdm_h{h}_hat"
            if y_col in frame.columns and hat_col in frame.columns:
                for cell, chunk in frame.groupby("cell_id"):
                    resid = (chunk[y_col] - chunk[hat_col]).to_numpy(dtype=float)
                    q = split_conformal_qhat(resid, 1.0 - self.coverage)
                    self.usdm_q[(str(cell), h)] = CellState(qhat=q, alpha=1.0 - self.coverage, n_cal=int(np.isfinite(resid).sum()))

    def interval(self, cell_id: str, horizon: int, point: float, kind: str = "erc") -> tuple[float, float, float, float]:
        store = self.erc if kind == "erc" else self.usdm_q
        state = store.get((cell_id, horizon), CellState(qhat=10.0, alpha=1.0 - self.coverage))
        # Wider alpha → smaller 1-alpha → we use qhat from the frozen 0.90 fit,
        # then scale by alpha / alpha_target as a cheap ACI width update.
        scale = (1.0 - self.coverage) / max(state.alpha, 1e-3)
        half = state.qhat * scale
        lo, hi = point - half, point + half
        width_norm = min(1.0, max(0.0, (2 * half) / 100.0)) if kind == "erc" else min(1.0, max(0.0, (2 * half) / 4.0))
        confidence = 1.0 - width_norm
        return float(lo), float(hi), float(state.alpha), float(confidence)

    def ordinal_prediction_set(self, cell_id: str, horizon: int, point: float, ge2: float, ge3: float) -> list[int]:
        """Softmax-style scores from the point and exceedance probabilities."""
        p3 = float(np.clip(ge3, 0, 1))
        p2 = float(np.clip(ge2, 0, 1))
        p_ge2 = max(p2, p3)
        # Rough 5-class scores from exceedances + proximity to the point.
        scores = np.zeros(5, dtype=float)
        for cat in range(5):
            scores[cat] = np.exp(-((cat - point) ** 2) / 2.0)
        scores = scores / scores.sum()
        scores[2:] = scores[2:] * 0.5 + 0.5 * p_ge2 / 3.0
        scores[3:] = scores[3:] * 0.5 + 0.5 * p3 / 2.0
        scores = scores / scores.sum()
        state = self.usdm_q.get((cell_id, horizon), CellState(qhat=1.0, alpha=1.0 - self.coverage))
        return ordinal_set(scores, state.alpha)

    def observe(self, cell_id: str, horizon: int, y: float, lo: float, hi: float, kind: str = "erc") -> None:
        store = self.erc if kind == "erc" else self.usdm_q
        key = (cell_id, horizon)
        if key not in store:
            return
        missed = not (lo <= y <= hi)
        store[key].alpha = aci_update(store[key].alpha, missed, self.coverage)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        blob = {
            "coverage": self.coverage,
            "erc": {f"{c}|{h}": asdict(s) for (c, h), s in self.erc.items()},
            "usdm": {f"{c}|{h}": asdict(s) for (c, h), s in self.usdm_q.items()},
        }
        (path / "conformal.json").write_text(json.dumps(blob))

    @classmethod
    def load(cls, path: Path) -> ConformalCalibrator:
        blob = json.loads((path / "conformal.json").read_text())
        inst = cls(coverage=float(blob["coverage"]))
        for key, val in blob["erc"].items():
            c, h = key.split("|")
            inst.erc[(c, int(h))] = CellState(**val)
        for key, val in blob["usdm"].items():
            c, h = key.split("|")
            inst.usdm_q[(c, int(h))] = CellState(**val)
        return inst


def attach_intervals(frame: pd.DataFrame, cal: ConformalCalibrator, update_aci: bool = False) -> pd.DataFrame:
    out = frame.copy()
    for h in HORIZONS_WEEKS:
        lo_col, hi_col = f"erc_pct_h{h}_lo", f"erc_pct_h{h}_hi"
        a_col, conf_col = f"erc_pct_h{h}_alpha", f"erc_pct_h{h}_conf"
        out[lo_col] = np.nan
        out[hi_col] = np.nan
        out[a_col] = np.nan
        out[conf_col] = np.nan
        out[f"usdm_h{h}_set"] = [[] for _ in range(len(out))]
        for i, row in out.iterrows():
            cell = str(row["cell_id"])
            point = float(row.get(f"erc_pct_h{h}_hat", np.nan))
            if not np.isfinite(point):
                continue
            lo, hi, alpha, conf = cal.interval(cell, h, point, "erc")
            out.at[i, lo_col] = lo
            out.at[i, hi_col] = hi
            out.at[i, a_col] = alpha
            out.at[i, conf_col] = conf
            ge2 = float(row.get(f"usdm_ge2_h{h}_hat", 0.3))
            ge3 = float(row.get(f"usdm_ge3_h{h}_hat", 0.1))
            usdm_hat = float(row.get(f"usdm_h{h}_hat", 0.0))
            out.at[i, f"usdm_h{h}_set"] = cal.ordinal_prediction_set(cell, h, usdm_hat, ge2, ge3)
            if update_aci and np.isfinite(row.get(f"erc_pct_h{h}", np.nan)):
                cal.observe(cell, h, float(row[f"erc_pct_h{h}"]), lo, hi, "erc")
    return out


if __name__ == "__main__":
    from cofire.model.calibrate import run_calibrate

    run_calibrate()
