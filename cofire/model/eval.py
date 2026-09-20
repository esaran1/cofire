"""Shared scoring. Validation metrics freeze here; hindcast scoring lives in hindcast.py."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error, r2_score

from cofire.model.config import HORIZONS_WEEKS, SEED


def _as_float(value: object, default: float = float("nan")) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def merge_pred(truth: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    """Align truth with a prediction frame.

    Saved prediction parquets already contain ``*_hat`` columns. Those must be
    dropped from *truth* so the incoming ``pred`` (model or baseline) wins.
    Dropping from ``pred`` instead would score the stored hats as every arm.
    """
    t = truth.reset_index(drop=True)
    p = pred.reset_index(drop=True)
    overlap = [c for c in p.columns if c in t.columns]
    if overlap:
        t = t.drop(columns=overlap)
    return t.join(p)


def reliability_ece(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error for a binary probability."""
    ok = np.isfinite(y) & np.isfinite(p)
    if ok.sum() < n_bins:
        return float("nan")
    y, p = y[ok], np.clip(p[ok], 0, 1)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y)
    for i in range(n_bins):
        m = (p >= bins[i]) & (p < bins[i + 1] if i < n_bins - 1 else p <= bins[i + 1])
        if not m.any():
            continue
        ece += float(m.mean() * abs(float(y[m].mean()) - float(p[m].mean())))
    return ece if n else float("nan")


def evaluate_arm(name: str, pred: pd.DataFrame, truth: pd.DataFrame) -> dict[str, object]:
    merged = merge_pred(truth, pred)
    out: dict[str, object] = {"arm": name, "n": int(len(merged))}
    for h in HORIZONS_WEEKS:
        if f"usdm_h{h}" in merged.columns and f"usdm_h{h}_hat" in merged.columns:
            y = merged[f"usdm_h{h}"].to_numpy(dtype=float)
            yhat = merged[f"usdm_h{h}_hat"].to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(yhat)
            out[f"usdm_h{h}_mae"] = float(mean_absolute_error(y[ok], yhat[ok])) if ok.any() else float("nan")
            out[f"usdm_h{h}_acc"] = float(np.mean(np.round(yhat[ok]) == y[ok])) if ok.any() else float("nan")
            out[f"usdm_h{h}_n"] = int(ok.sum())
        if f"erc_pct_h{h}" in merged.columns and f"erc_pct_h{h}_hat" in merged.columns:
            y = merged[f"erc_pct_h{h}"].to_numpy(dtype=float)
            yhat = merged[f"erc_pct_h{h}_hat"].to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(yhat)
            out[f"erc_h{h}_mae"] = float(mean_absolute_error(y[ok], yhat[ok])) if ok.any() else float("nan")
            out[f"erc_h{h}_r2"] = float(r2_score(y[ok], yhat[ok])) if ok.sum() > 2 else float("nan")
            out[f"erc_h{h}_n"] = int(ok.sum())
        for thresh, tag in ((2, "ge2"), (3, "ge3")):
            ge_col = f"usdm_{tag}_h{h}_hat"
            if ge_col in merged.columns and f"usdm_h{h}" in merged.columns:
                y = (merged[f"usdm_h{h}"] >= thresh).to_numpy(dtype=float)
                p = merged[ge_col].to_numpy(dtype=float)
                ok = np.isfinite(y) & np.isfinite(p)
                out[f"usdm_h{h}_brier_{tag}"] = (
                    float(brier_score_loss(y[ok], np.clip(p[ok], 0, 1))) if ok.any() else float("nan")
                )
                out[f"usdm_h{h}_ece_{tag}"] = reliability_ece(y, p)
    return out


def persistence_pred(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for h in HORIZONS_WEEKS:
        out[f"usdm_h{h}_hat"] = frame["usdm"] if "usdm" in frame.columns else np.nan
        out[f"erc_pct_h{h}_hat"] = frame["erc_pct"] if "erc_pct" in frame.columns else np.nan
    return out


def climatology_pred(train: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for h in HORIZONS_WEEKS:
        if "usdm" in train.columns and "woy" in train.columns:
            means = train.groupby(["cell_id", "woy"])["usdm"].mean()
            keys = list(zip(frame["cell_id"], frame["woy"], strict=False))
            out[f"usdm_h{h}_hat"] = [means.get(k, np.nan) for k in keys]
        if "erc_pct" in train.columns and "woy" in train.columns:
            means = train.groupby(["cell_id", "woy"])["erc_pct"].mean()
            keys = list(zip(frame["cell_id"], frame["woy"], strict=False))
            out[f"erc_pct_h{h}_hat"] = [means.get(k, np.nan) for k in keys]
    return out


def random_pred(train: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    usdm_mode = float(train["usdm"].mode().iloc[0]) if "usdm" in train.columns and len(train) else 0.0
    erc_mean = float(train["erc_pct"].mean()) if "erc_pct" in train.columns else 50.0
    for h in HORIZONS_WEEKS:
        out[f"usdm_h{h}_hat"] = usdm_mode
        out[f"erc_pct_h{h}_hat"] = erc_mean
    return out


def skill(mae_model: float, mae_base: float) -> float:
    if not np.isfinite(mae_model) or not np.isfinite(mae_base) or mae_base == 0:
        return float("nan")
    return float(1.0 - mae_model / mae_base)


def week_block_skill_ci(
    truth: pd.DataFrame,
    pred: pd.DataFrame,
    base: pd.DataFrame,
    col_true: str,
    col_hat: str,
    n_boot: int = 150,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """Skill vs a baseline, resampling whole issue weeks. Returns (point, lo, hi)."""
    merged = merge_pred(truth, pred)
    base_m = merge_pred(truth, base)
    merged["_base"] = base_m[col_hat]
    merged["_week"] = pd.to_datetime(merged["time"]).astype(str)
    weeks = merged["_week"].unique()
    rng = np.random.default_rng(seed)

    y = merged[col_true].to_numpy(dtype=float)
    yhat = merged[col_hat].to_numpy(dtype=float)
    yb = merged["_base"].to_numpy(dtype=float)
    week_ids = merged["_week"].to_numpy()
    uniq = np.asarray(weeks)
    blocks = [np.flatnonzero(week_ids == w) for w in uniq]

    def _skill_idx(idx: np.ndarray) -> float:
        yy, yh, ybb = y[idx], yhat[idx], yb[idx]
        ok = np.isfinite(yy) & np.isfinite(yh) & np.isfinite(ybb)
        if not ok.any():
            return float("nan")
        return skill(float(mean_absolute_error(yy[ok], yh[ok])), float(mean_absolute_error(yy[ok], ybb[ok])))

    all_idx = np.arange(len(merged))
    point = _skill_idx(all_idx)
    n_w = len(blocks)
    if n_w == 0:
        return point, float("nan"), float("nan")
    draws: list[float] = []
    for _ in range(n_boot):
        pick = rng.integers(0, n_w, size=n_w)
        idx = np.concatenate([blocks[int(i)] for i in pick])
        draws.append(_skill_idx(idx))
    arr = np.asarray(draws, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 20:
        return point, float("nan"), float("nan")
    return point, float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def ar1_neff(values: np.ndarray) -> tuple[float, float, int]:
    """Lag-1 autocorrelation and n_eff = n (1-rho)/(1+rho)."""
    x = values[np.isfinite(values)]
    n = int(x.size)
    if n < 8:
        return float("nan"), float("nan"), n
    rho = float(np.corrcoef(x[:-1], x[1:])[0, 1])
    if not np.isfinite(rho) or rho >= 0.999:
        return rho, 1.0, n
    neff = n * (1.0 - rho) / (1.0 + max(rho, -0.999))
    return rho, float(max(neff, 1.0)), n


def attach_skills(
    row: dict[str, Any],
    truth: pd.DataFrame,
    pred: pd.DataFrame,
    pers: pd.DataFrame,
    clim: pd.DataFrame,
) -> dict[str, Any]:
    for h in HORIZONS_WEEKS:
        for target, tcol, hcol in (
            ("usdm", f"usdm_h{h}", f"usdm_h{h}_hat"),
            ("erc", f"erc_pct_h{h}", f"erc_pct_h{h}_hat"),
        ):
            if tcol not in truth.columns:
                continue
            sp, slo, shi = week_block_skill_ci(truth, pred, pers, tcol, hcol)
            sc, clo, chi = week_block_skill_ci(truth, pred, clim, tcol, hcol)
            row[f"{target}_h{h}_skill_pers"] = sp
            row[f"{target}_h{h}_skill_pers_lo"] = slo
            row[f"{target}_h{h}_skill_pers_hi"] = shi
            row[f"{target}_h{h}_skill_clim"] = sc
            row[f"{target}_h{h}_skill_clim_lo"] = clo
            row[f"{target}_h{h}_skill_clim_hi"] = chi
    return row


def format_skill_sentence(arm: str, horizon: int, kind: str, row: dict[str, Any], pers: dict[str, Any]) -> str:
    """One plain sentence. Negative skill is stated as worse than persistence, not an 'improvement'."""
    if kind == "usdm":
        mae_key, label, unit = f"usdm_h{horizon}_mae", "drought", " categories"
        sk_key = f"usdm_h{horizon}_skill_pers"
    else:
        mae_key, label, unit = f"erc_h{horizon}_mae", "ERC-percentile", ""
        sk_key = f"erc_h{horizon}_skill_pers"
    mae = _as_float(row.get(mae_key))
    pmae = _as_float(pers.get(mae_key))
    sk = _as_float(row.get(sk_key))
    lo = _as_float(row.get(f"{sk_key}_lo"))
    hi = _as_float(row.get(f"{sk_key}_hi"))
    if not np.isfinite(mae) or not np.isfinite(pmae):
        return f"The {horizon}-week {label} MAE for {arm} could not be computed."
    if not np.isfinite(sk):
        return (
            f"The {horizon}-week {label} MAE for {arm} is {mae:.2f}{unit} versus {pmae:.2f} for persistence; "
            "skill vs persistence could not be computed."
        )
    if sk > 0:
        clause = f"a {100.0 * sk:.0f}% skill improvement"
    elif sk < 0:
        clause = f"a {100.0 * sk:.0f}% skill (worse than persistence)"
    else:
        clause = "no skill vs persistence"
    ci = ""
    if np.isfinite(lo) and np.isfinite(hi):
        ci = f", CI [{100.0 * lo:.0f}%, {100.0 * hi:.0f}%]"
    return (
        f"The {horizon}-week {label} MAE for {arm} is {mae:.2f}{unit} versus {pmae:.2f} for persistence, "
        f"{clause}{ci}."
    )
