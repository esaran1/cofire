"""Multi-regime calibration pools. INTENDED FOR HAND-REWRITE.

Implements exactly the variants frozen in docs/PREREGISTRATION_CALIBRATION.md:

  base  single-year pool (the v0.5 baseline)
  a     all non-fold years pooled, equal weight
  b     severity-stratified, years weighted by mean USDM category
  c     nearest-regime, k most similar years by (usdm_mean, spi_90_mean); k = 2, 3
  d     residual rescaling by a regime covariate, ratio clipped to [0.5, 3.0]

The variant list is closed. Nothing here evaluates on 2026.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import COVERAGE_TARGET

HOLDOUT_YEAR = 2026
# Frozen in the pre-registration.
RESCALE_CLIP = (0.5, 3.0)
K_VALUES = (2, 3)
WIDTH_CAP_MULTIPLE = 1.5


@dataclass
class RegimeProfile:
    """Per-year regime summary used for weighting and similarity."""

    year: int
    usdm_mean: float
    spi90_mean: float


def regime_profiles(frame: pd.DataFrame) -> dict[int, RegimeProfile]:
    t = pd.to_datetime(frame["time"])
    out: dict[int, RegimeProfile] = {}
    for year, chunk in frame.groupby(t.dt.year):
        y = int(year)
        if y == HOLDOUT_YEAR:
            continue
        spi = pd.to_numeric(chunk.get("spi_90"), errors="coerce")
        out[y] = RegimeProfile(
            year=y,
            usdm_mean=float(pd.to_numeric(chunk["usdm"], errors="coerce").mean()),
            spi90_mean=float(spi.mean()) if spi is not None else float("nan"),
        )
    return out


def nearest_years(profiles: dict[int, RegimeProfile], target: int, k: int) -> list[int]:
    """k non-target years closest in standardised (usdm_mean, spi90_mean) space."""
    pool = {y: p for y, p in profiles.items() if y != target}
    if target not in profiles or not pool:
        return sorted(pool)[:k]
    years = sorted(pool)
    u = np.array([profiles[y].usdm_mean for y in years], dtype=float)
    s = np.array([profiles[y].spi90_mean for y in years], dtype=float)
    tu, ts = profiles[target].usdm_mean, profiles[target].spi90_mean
    # Standardise on the pool so both covariates contribute comparably.
    def z(v: np.ndarray, x: float) -> tuple[np.ndarray, float]:
        mu, sd = float(np.nanmean(v)), float(np.nanstd(v))
        sd = sd if sd > 1e-9 else 1.0
        return (v - mu) / sd, (x - mu) / sd

    uz, tuz = z(u, tu)
    sz, tsz = z(s, ts)
    d = np.sqrt(np.nan_to_num(uz - tuz) ** 2 + np.nan_to_num(sz - tsz) ** 2)
    order = [years[i] for i in np.argsort(d)]
    return order[:k]


def _residual_frame(preds: dict[int, pd.DataFrame], horizon: int, target: str = "erc_pct") -> dict[int, np.ndarray]:
    """|residual| arrays per year for one horizon."""
    out: dict[int, np.ndarray] = {}
    for year, df in preds.items():
        y = pd.to_numeric(df.get(f"{target}_h{horizon}"), errors="coerce").to_numpy(dtype=float)
        hat = pd.to_numeric(df.get(f"{target}_h{horizon}_hat"), errors="coerce").to_numpy(dtype=float)
        r = np.abs(y - hat)
        out[year] = r[np.isfinite(r)]
    return out


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Weighted quantile of |residual|, with the (n+1)/n style correction."""
    if values.size == 0:
        return float("nan")
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w)
    total = cum[-1]
    if total <= 0:
        return float(np.quantile(v, q))
    # Match split conformal's conservative direction.
    target = q * (total + w.mean())
    idx = int(np.searchsorted(cum, min(target, total)))
    return float(v[min(idx, v.size - 1)])


def build_pool(
    variant: str,
    fold_year: int,
    residuals: dict[int, np.ndarray],
    profiles: dict[int, RegimeProfile],
    *,
    k: int = 2,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Return (values, weights, meta) for one variant, excluding the fold year."""
    avail = {y: r for y, r in residuals.items() if y != fold_year and y != HOLDOUT_YEAR and r.size}
    meta: dict[str, object] = {"variant": variant, "fold_year": fold_year}
    if not avail:
        return np.array([]), np.array([]), meta

    if variant == "base":
        year = max(avail)
        meta["pool_years"] = [year]
        v = avail[year]
        return v, np.ones_like(v), meta

    if variant == "a":
        meta["pool_years"] = sorted(avail)
        v = np.concatenate([avail[y] for y in sorted(avail)])
        return v, np.ones_like(v), meta

    if variant == "b":
        years = sorted(avail)
        meta["pool_years"] = years
        # Weight each year by its mean USDM category, normalised to mean 1.
        raw = np.array([max(profiles[y].usdm_mean, 1e-3) if y in profiles else 1e-3 for y in years], dtype=float)
        norm = raw / raw.mean()
        meta["year_weights"] = {str(y): float(w) for y, w in zip(years, norm, strict=True)}
        v = np.concatenate([avail[y] for y in years])
        w = np.concatenate([np.full(avail[y].size, norm[i]) for i, y in enumerate(years)])
        return v, w, meta

    if variant == "c":
        sel = [y for y in nearest_years(profiles, fold_year, k) if y in avail]
        if not sel:
            sel = sorted(avail)[:k]
        meta["pool_years"] = sel
        meta["k"] = k
        v = np.concatenate([avail[y] for y in sel])
        return v, np.ones_like(v), meta

    if variant == "d":
        years = sorted(avail)
        meta["pool_years"] = years
        # sigma_hat ~ b0 + b1 * usdm_mean, fit on the POOL only.
        xs = np.array([profiles[y].usdm_mean for y in years if y in profiles], dtype=float)
        ys = np.array([float(np.mean(avail[y])) for y in years if y in profiles], dtype=float)
        v = np.concatenate([avail[y] for y in years])
        if xs.size >= 2 and np.std(xs) > 1e-9:
            b1, b0 = np.polyfit(xs, ys, 1)
            pool_sigma = float(b0 + b1 * float(np.mean(xs)))
            tgt_usdm = profiles[fold_year].usdm_mean if fold_year in profiles else float(np.mean(xs))
            tgt_sigma = float(b0 + b1 * tgt_usdm)
            ratio = tgt_sigma / pool_sigma if abs(pool_sigma) > 1e-9 else 1.0
            ratio = float(np.clip(ratio, *RESCALE_CLIP))
        else:
            ratio, b0, b1 = 1.0, float("nan"), float("nan")
            meta["degenerate_fit"] = True
        meta["rescale_ratio"] = ratio
        meta["fit"] = {"b0": float(b0), "b1": float(b1)}
        return v * ratio, np.ones_like(v), meta

    raise ValueError(f"unknown variant {variant!r}")


def evaluate_variant(
    variant: str,
    fold_year: int,
    residuals: dict[int, np.ndarray],
    profiles: dict[int, RegimeProfile],
    test_frame: pd.DataFrame,
    horizon: int,
    *,
    k: int = 2,
    target: str = "erc_pct",
    coverage_target: float = COVERAGE_TARGET,
) -> dict[str, object]:
    """Static split-conformal coverage/width on the held-out year for one variant.

    Static (no ACI) isolates the pool's contribution from the online update.
    """
    values, weights, meta = build_pool(variant, fold_year, residuals, profiles, k=k)
    if values.size == 0:
        return {**meta, "horizon": horizon, "coverage": float("nan"), "width": float("nan"), "n": 0}
    qhat = _weighted_quantile(values, weights, coverage_target)
    y = pd.to_numeric(test_frame.get(f"{target}_h{horizon}"), errors="coerce").to_numpy(dtype=float)
    hat = pd.to_numeric(test_frame.get(f"{target}_h{horizon}_hat"), errors="coerce").to_numpy(dtype=float)
    m = np.isfinite(y) & np.isfinite(hat)
    if not m.any():
        return {**meta, "horizon": horizon, "coverage": float("nan"), "width": float("nan"), "n": 0}
    covered = np.abs(y[m] - hat[m]) <= qhat
    out: dict[str, object] = {
        **meta,
        "horizon": horizon,
        "qhat": float(qhat),
        "coverage": float(covered.mean()),
        "width": float(2 * qhat),
        "n": int(m.sum()),
    }
    # Stratified coverage: by USDM category and by month.
    usdm = pd.to_numeric(test_frame.get("usdm"), errors="coerce").to_numpy(dtype=float)[m]
    month = pd.to_datetime(test_frame["time"]).dt.month.to_numpy()[m]
    strata: dict[str, float] = {}
    for cat in range(5):
        s = np.isclose(np.round(usdm), cat)
        if s.sum() >= 30:
            strata[f"usdm={cat}"] = float(covered[s].mean())
    for mo in range(1, 13):
        s = month == mo
        if s.sum() >= 30:
            strata[f"month={mo}"] = float(covered[s].mean())
    out["strata"] = strata
    return out


def variant_specs() -> list[tuple[str, int]]:
    """The closed variant list: (variant id, k). k is ignored except for 'c'."""
    return [("base", 0), ("a", 0), ("b", 0), ("c", 2), ("c", 3), ("d", 0)]


def label(variant: str, k: int) -> str:
    return f"c(k={k})" if variant == "c" else variant


def write_report(rows: list[dict[str, object]], out_dir: Path, domain_notes: str = "") -> Path:
    """artifacts/uncertainty/multiregime.md — every variant, including failures."""
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    (out_dir / "multiregime.json").write_text(json.dumps(rows, indent=2, default=str))

    L = ["# Multi-regime calibration pools", ""]
    L.append(
        "Pre-registered in `docs/PREREGISTRATION_CALIBRATION.md` (sha256 recorded in DECISIONS.md) "
        "**before** any variant was run. The variant list is closed. Every variant is reported, "
        "including the ones that fail. Nothing here evaluates on 2026."
    )
    L.append("")
    if domain_notes:
        L += [domain_notes, ""]
    L.append(
        "Coverage is **static split conformal** (no ACI) so the pool's contribution is isolated from "
        "the online update. Target 0.90."
    )
    L.append("")
    for dom in sorted(df["domain"].unique()) if "domain" in df.columns else [None]:
        sub = df[df.domain == dom] if dom else df
        L += [f"## Domain: {dom}", ""] if dom else []
        for h in sorted(sub.horizon.unique()):
            hs = sub[sub.horizon == h]
            L += [f"### h = {h} weeks", "", "| variant | mean coverage | worst fold | mean width | pool years (last fold) |",
                  "| --- | --- | --- | --- | --- |"]
            for lab in hs.label.unique():
                v = hs[hs.label == lab]
                py = v.iloc[-1].get("pool_years", [])
                L.append(
                    f"| {lab} | {v.coverage.mean():.3f} | {v.coverage.min():.3f} | "
                    f"{v.width.mean():.1f} | {py} |"
                )
            L.append("")
    path = out_dir / "multiregime.md"
    path.write_text("\n".join(L) + "\n")
    return path
