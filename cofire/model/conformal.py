"""Split conformal + adaptive conformal inference (ACI).

INTENDED FOR HAND-REWRITE. Target coverage 0.90. `qhat` is computed on the
calibrate split and frozen. Only alpha updates online (learning rate 0.01).
The hindcast is reported, never used to retune qhat.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    # Sorted |residual| pool from the calibrate split, so the interval can be
    # re-quantiled at the *current* alpha instead of linearly rescaling a frozen
    # 0.90 qhat. The pool is fit on calibrate only and never refit on a holdout.
    resid_abs: list[float] = field(default_factory=list)

    def qhat_at(self, alpha: float) -> float:
        """Empirical (1-alpha) quantile of |residual| with the (n+1)/n correction."""
        if not self.resid_abs:
            # No stored pool (legacy state): fall back to the frozen qhat.
            return self.qhat
        r = np.asarray(self.resid_abs, dtype=float)
        n = r.size
        q_level = min(1.0, np.ceil((n + 1) * (1.0 - alpha)) / n)
        idx = min(n - 1, max(0, int(np.ceil(q_level * n) - 1)))
        return float(r[idx])


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
    """ACI: alpha_{t+1} = clip(alpha_t + lr * (alpha_target - err_t), 0.01, 0.5).

    `target` is the *coverage* target (e.g. 0.90) for call-site compatibility; the
    update uses the miss-rate target alpha_target = 1 - target (e.g. 0.10).

    Gibbs & Candes (2021) drive the realised miss rate to alpha_target. Feeding the
    coverage target in where the miss-rate target belongs makes the only stationary
    point a 90% *miss* rate: on a hit alpha moves +lr*0.9, on a miss only -lr*0.1,
    so alpha ratchets up, intervals shrink, and coverage decays toward 1-target.
    That is a defect on any stream, shifted or not — see
    artifacts/uncertainty/diagnosis.md.
    """
    alpha_target = 1.0 - target
    err = 1.0 if missed else 0.0
    nxt = alpha + lr * (alpha_target - err)
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
                    pool = np.sort(np.abs(resid[np.isfinite(resid)]))
                    self.erc[(str(cell), h)] = CellState(
                        qhat=q,
                        alpha=1.0 - self.coverage,
                        n_cal=int(np.isfinite(resid).sum()),
                        resid_abs=[float(v) for v in pool],
                    )
            y_col, hat_col = f"usdm_h{h}", f"usdm_h{h}_hat"
            if y_col in frame.columns and hat_col in frame.columns:
                for cell, chunk in frame.groupby("cell_id"):
                    resid = (chunk[y_col] - chunk[hat_col]).to_numpy(dtype=float)
                    q = split_conformal_qhat(resid, 1.0 - self.coverage)
                    pool = np.sort(np.abs(resid[np.isfinite(resid)]))
                    self.usdm_q[(str(cell), h)] = CellState(
                        qhat=q,
                        alpha=1.0 - self.coverage,
                        n_cal=int(np.isfinite(resid).sum()),
                        resid_abs=[float(v) for v in pool],
                    )

    def interval(self, cell_id: str, horizon: int, point: float, kind: str = "erc") -> tuple[float, float, float, float]:
        store = self.erc if kind == "erc" else self.usdm_q
        state = store.get((cell_id, horizon), CellState(qhat=10.0, alpha=1.0 - self.coverage))
        # Re-quantile the frozen calibrate-split residual pool at the current alpha.
        # The previous code rescaled a frozen 0.90 qhat by (0.10/alpha), which is
        # not the quantile ratio: at alpha=0.5 the linear proxy is ~51% too narrow
        # under Gaussian residuals. The pool itself is never refit on a holdout.
        half = state.qhat_at(state.alpha)
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
    out = frame.copy().reset_index(drop=True)
    order = np.argsort(pd.to_datetime(out["time"]).to_numpy(), kind="mergesort")
    for h in HORIZONS_WEEKS:
        lo_col, hi_col = f"erc_pct_h{h}_lo", f"erc_pct_h{h}_hi"
        a_col, conf_col = f"erc_pct_h{h}_alpha", f"erc_pct_h{h}_conf"
        out[lo_col] = np.nan
        out[hi_col] = np.nan
        out[a_col] = np.nan
        out[conf_col] = np.nan
        out[f"usdm_h{h}_set"] = [[] for _ in range(len(out))]
        hat = pd.to_numeric(out.get(f"erc_pct_h{h}_hat", pd.Series(np.nan, index=out.index)), errors="coerce").to_numpy(
            dtype=float
        )
        y = pd.to_numeric(out.get(f"erc_pct_h{h}", pd.Series(np.nan, index=out.index)), errors="coerce").to_numpy(
            dtype=float
        )
        ge2s = pd.to_numeric(out.get(f"usdm_ge2_h{h}_hat", pd.Series(0.3, index=out.index)), errors="coerce").to_numpy(
            dtype=float
        )
        ge3s = pd.to_numeric(out.get(f"usdm_ge3_h{h}_hat", pd.Series(0.1, index=out.index)), errors="coerce").to_numpy(
            dtype=float
        )
        usdm_hat = pd.to_numeric(out.get(f"usdm_h{h}_hat", pd.Series(0.0, index=out.index)), errors="coerce").to_numpy(
            dtype=float
        )
        cells = out["cell_id"].astype(str).to_numpy()
        for i in order:
            ii = int(i)
            point = float(hat[ii])
            if not np.isfinite(point):
                continue
            cell = str(cells[ii])
            lo, hi, alpha, conf = cal.interval(cell, h, point, "erc")
            out.at[ii, lo_col] = lo
            out.at[ii, hi_col] = hi
            out.at[ii, a_col] = alpha
            out.at[ii, conf_col] = conf
            out.at[ii, f"usdm_h{h}_set"] = cal.ordinal_prediction_set(
                cell, h, float(usdm_hat[ii]), float(ge2s[ii]), float(ge3s[ii])
            )
            if update_aci and np.isfinite(y[ii]):
                cal.observe(cell, h, float(y[ii]), lo, hi, "erc")
    return out


if __name__ == "__main__":
    from cofire.model.calibrate import run_calibrate

    run_calibrate()
