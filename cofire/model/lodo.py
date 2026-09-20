"""Leave-one-drought-year-out (LODO). INTENDED FOR HAND-REWRITE.

Free shift test: for each held-out year, retrain with that year removed and
evaluate on it. These are in-sample analogs for a severe-drought regime and cost
no holdout budget, so model development and conformal debugging can iterate here
instead of on the sealed 2026 hindcast.

Also runs the delta ("predict change, not level") parameterisation side by side
with the level parameterisation, so the two are comparable on identical folds.

Nothing in this module reads 2026.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import HORIZONS_WEEKS, SEED, get_settings
from cofire.model.conformal import ConformalCalibrator, attach_intervals
from cofire.model.features import load_features
from cofire.model.log import setup_logging
from cofire.model.models.lightgbm_arm import LightGBMConditionModel

# Driest years available in the 2018-2026 feature store, excluding the sealed
# 2026 holdout. 2002 and 2012 are not on disk (fetch warmup starts 2018), so the
# four driest in-window years stand in. They are weaker analogs than 2026: the
# driest here is 2021 at mean USDM 0.916 against 2026's 2.231.
LODO_YEARS = (2020, 2021, 2024, 2025)

HOLDOUT_YEAR = 2026


@dataclass
class FoldResult:
    year: int
    horizon: int
    target: str
    parameterisation: str
    model_mae: float
    persistence_mae: float
    skill: float
    n: int
    coverage: float | None = None
    width: float | None = None


def _levels_to_delta(frame: pd.DataFrame, horizon: int, target: str) -> pd.Series:
    """y_delta = y(t+h) - y(t). Persistence becomes the zero predictor."""
    base = frame[target]
    fut = frame[f"{target}_h{horizon}"]
    return fut - base


def add_delta_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach delta targets for both variables at every horizon."""
    out = frame.copy()
    for h in HORIZONS_WEEKS:
        for target in ("usdm", "erc_pct"):
            col = f"{target}_h{h}"
            if col in out.columns and target in out.columns:
                out[f"{target}_d{h}"] = _levels_to_delta(out, h, target)
    return out


def severe_week_weights(frame: pd.DataFrame, power: float = 1.0) -> np.ndarray:
    """Weight rows so severe-drought weeks are not drowned out by normal ones.

    Inverse-frequency on the USDM category of the *issue* week, normalised to
    mean 1. Reported explicitly rather than tuned: `power=1.0` is plain inverse
    frequency, `power=0.0` is uniform.
    """
    cat = pd.to_numeric(frame.get("usdm"), errors="coerce").fillna(0).round().clip(0, 4).astype(int)
    counts = cat.value_counts().to_dict()
    n = len(cat)
    w = cat.map(lambda c: (n / (len(counts) * max(counts.get(c, 1), 1))) ** power).to_numpy(dtype=float)
    out: np.ndarray = w / max(float(w.mean()), 1e-9)
    return out


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.mean(np.abs(a[m] - b[m]))) if m.any() else float("nan")


def run_fold(
    frame: pd.DataFrame,
    year: int,
    *,
    parameterisation: str = "level",
    weighting: float = 0.0,
    seed: int = SEED,
) -> list[FoldResult]:
    """Retrain with `year` removed, evaluate on `year`."""
    t = pd.to_datetime(frame["time"])
    is_year = t.dt.year == year
    # Never train on the sealed holdout, whatever the fold.
    train = frame[(~is_year) & (t.dt.year != HOLDOUT_YEAR)].copy()
    test = frame[is_year].copy()
    if train.empty or test.empty:
        return []

    results: list[FoldResult] = []
    model = LightGBMConditionModel(seed=seed)

    if parameterisation == "delta":
        # Fit on the change, then reconstruct the level by adding back y(t).
        train = add_delta_targets(train)
        test = add_delta_targets(test)
        renames_tr, renames_te = {}, {}
        for h in HORIZONS_WEEKS:
            for target in ("usdm", "erc_pct"):
                if f"{target}_d{h}" in train.columns:
                    renames_tr[f"{target}_h{h}"] = f"{target}_lvl{h}"
                    renames_te[f"{target}_h{h}"] = f"{target}_lvl{h}"
        train = train.rename(columns=renames_tr)
        test = test.rename(columns=renames_te)
        for h in HORIZONS_WEEKS:
            for target in ("usdm", "erc_pct"):
                if f"{target}_d{h}" in train.columns:
                    train[f"{target}_h{h}"] = train[f"{target}_d{h}"]
                    test[f"{target}_h{h}"] = test[f"{target}_d{h}"]

    if weighting > 0:
        train = train.assign(_w=severe_week_weights(train, weighting))

    model.fit(train, None)
    pred = model.predict(test)
    merged = test.reset_index(drop=True).join(pred.reset_index(drop=True), rsuffix="_p")

    for h in HORIZONS_WEEKS:
        for target, clip in (("usdm", (0.0, 4.0)), ("erc_pct", (0.0, 100.0))):
            hat_col = f"{target}_h{h}_hat"
            if hat_col not in merged.columns:
                continue
            yhat = pd.to_numeric(merged[hat_col], errors="coerce").to_numpy(dtype=float)
            base = pd.to_numeric(merged[target], errors="coerce").to_numpy(dtype=float)
            if parameterisation == "delta":
                y_true = pd.to_numeric(merged[f"{target}_lvl{h}"], errors="coerce").to_numpy(dtype=float)
                level_hat = np.clip(base + yhat, *clip)
            else:
                y_true = pd.to_numeric(merged[f"{target}_h{h}"], errors="coerce").to_numpy(dtype=float)
                level_hat = np.clip(yhat, *clip)
            # Persistence on the level is y(t) in both parameterisations.
            results.append(
                FoldResult(
                    year=year,
                    horizon=h,
                    target=target,
                    parameterisation=parameterisation,
                    model_mae=_mae(level_hat, y_true),
                    persistence_mae=_mae(base, y_true),
                    skill=float("nan"),
                    n=int(np.isfinite(y_true).sum()),
                )
            )
    for r in results:
        if np.isfinite(r.persistence_mae) and r.persistence_mae > 0:
            r.skill = 1.0 - r.model_mae / r.persistence_mae
    return results


def clip_binding_rate(frame: pd.DataFrame, horizon: int, target: str = "usdm") -> float:
    """How often the reconstructed level needs clipping to the valid range."""
    hat = pd.to_numeric(frame.get(f"{target}_h{horizon}_hat"), errors="coerce").to_numpy(dtype=float)
    base = pd.to_numeric(frame.get(target), errors="coerce").to_numpy(dtype=float)
    raw = base + hat
    hi = 4.0 if target == "usdm" else 100.0
    m = np.isfinite(raw)
    return float(((raw[m] < 0) | (raw[m] > hi)).mean()) if m.any() else float("nan")


def lodo_conformal_coverage(frame: pd.DataFrame, year: int, seed: int = SEED) -> dict[str, float]:
    """Fit conformal on non-fold years, run ACI across the held-out year.

    This is the free reproduction of the 2026 coverage question: if coverage
    collapses here too, the defect is in the code, not in the 2026 regime.
    """
    t = pd.to_datetime(frame["time"])
    is_year = t.dt.year == year
    train = frame[(~is_year) & (t.dt.year != HOLDOUT_YEAR)].copy()
    test = frame[is_year].copy()
    if train.empty or test.empty:
        return {}
    model = LightGBMConditionModel(seed=seed)
    model.fit(train, None)
    cal_src = train[pd.to_datetime(train["time"]).dt.year == sorted({int(y) for y in pd.to_datetime(train["time"]).dt.year})[-1]]
    cal = cal_src.reset_index(drop=True).join(model.predict(cal_src).reset_index(drop=True))
    te = test.reset_index(drop=True).join(model.predict(test).reset_index(drop=True))
    conf = ConformalCalibrator()
    conf.fit(cal)
    out = attach_intervals(te, conf, update_aci=True)
    res: dict[str, float] = {}
    for h in HORIZONS_WEEKS:
        y = pd.to_numeric(out.get(f"erc_pct_h{h}"), errors="coerce")
        lo, hi = out.get(f"erc_pct_h{h}_lo"), out.get(f"erc_pct_h{h}_hi")
        if y is None or lo is None:
            continue
        m = np.isfinite(y) & np.isfinite(lo)
        if not m.any():
            continue
        res[f"h{h}_coverage"] = float(((y >= lo) & (y <= hi))[m].mean())
        res[f"h{h}_width"] = float((hi - lo)[m].mean())
        res[f"h{h}_alpha_min"] = float(out[f"erc_pct_h{h}_alpha"].min())
        res[f"h{h}_alpha_max"] = float(out[f"erc_pct_h{h}_alpha"].max())
    return res


def run_lodo(
    years: tuple[int, ...] = LODO_YEARS,
    with_coverage: bool = True,
    resume: bool = True,
) -> Path:
    """Run every fold, checkpointing after each so an interrupted run resumes.

    Each (year, parameterisation) fold and each coverage fold writes its own JSON
    under artifacts/lodo/checkpoints/ as soon as it finishes. A rerun skips any
    checkpoint already on disk. This exists because an early run deadlocked mid-way
    and lost every completed fold.
    """
    settings = get_settings()
    log = setup_logging(settings.log_dir)
    out_dir = settings.artifacts_dir / "lodo"
    ckpt_dir = out_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    frame = load_features(settings.processed_dir / "features")
    rows: list[dict[str, object]] = []
    coverage: dict[str, dict[str, float]] = {}

    for year in years:
        for param in ("level", "delta"):
            ck = ckpt_dir / f"fold_{year}_{param}.json"
            if resume and ck.exists():
                log.info("LODO resume: %s", ck.name)
                rows.extend(json.loads(ck.read_text()))
                continue
            log.info("LODO fold year=%s parameterisation=%s", year, param)
            got = [
                {
                    "year": r.year,
                    "horizon": r.horizon,
                    "target": r.target,
                    "parameterisation": r.parameterisation,
                    "model_mae": r.model_mae,
                    "persistence_mae": r.persistence_mae,
                    "skill": r.skill,
                    "n": r.n,
                }
                for r in run_fold(frame, year, parameterisation=param)
            ]
            ck.write_text(json.dumps(got, indent=2))
            rows.extend(got)
        if with_coverage:
            ck = ckpt_dir / f"coverage_{year}.json"
            if resume and ck.exists():
                log.info("LODO resume: %s", ck.name)
                coverage[str(year)] = json.loads(ck.read_text())
                continue
            log.info("LODO conformal coverage year=%s", year)
            cov = lodo_conformal_coverage(frame, year)
            ck.write_text(json.dumps(cov, indent=2))
            coverage[str(year)] = cov

    df = pd.DataFrame(rows)
    df.to_json(out_dir / "folds.json", orient="records", indent=2)
    (out_dir / "coverage.json").write_text(json.dumps(coverage, indent=2))
    md = _write_md(df, coverage, out_dir)
    log.info("LODO written to %s", md)
    return md


def _write_md(df: pd.DataFrame, coverage: dict[str, dict[str, float]], out_dir: Path) -> Path:
    lines = ["# Leave-one-drought-year-out (LODO)", ""]
    lines.append(
        "In-sample shift test. For each year, the model is retrained with that year removed and "
        "evaluated on it. No fold ever trains or evaluates on 2026. Skill is versus persistence "
        "on the **level**, so the two parameterisations are directly comparable."
    )
    lines.append("")
    lines.append(
        f"Years: {', '.join(str(y) for y in sorted(df['year'].unique()))}. 2002 and 2012 are not in "
        "the feature store (fetch warmup starts 2018), so these are the driest available years. "
        "They are weaker analogs for 2026 than the spec assumed: the driest here is 2021 at mean "
        "USDM 0.916, against 2026's 2.231."
    )
    lines.append("")
    if not df.empty:
        for target in ("erc_pct", "usdm"):
            sub = df[df.target == target]
            if sub.empty:
                continue
            lines.append(f"## {target}")
            lines.append("")
            lines.append("| year | h | param | model MAE | persistence MAE | skill |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for _, r in sub.sort_values(["year", "horizon", "parameterisation"]).iterrows():
                lines.append(
                    f"| {r.year} | {r.horizon} | {r.parameterisation} | {r.model_mae:.3f} | "
                    f"{r.persistence_mae:.3f} | {r.skill:+.1%} |"
                )
            lines.append("")
            piv = sub.pivot_table(index="parameterisation", values="skill", aggfunc="mean")
            lines.append("Mean skill across folds and horizons:")
            lines.append("")
            for param, row in piv.iterrows():
                lines.append(f"- **{param}**: {row['skill']:+.1%}")
            lines.append("")
    if coverage:
        lines.append("## Conformal coverage on held-out years (target 0.90)")
        lines.append("")
        lines.append("| year | h=2 | h=4 | h=8 |")
        lines.append("| --- | --- | --- | --- |")
        for year, cov in sorted(coverage.items()):
            cells = [f"{cov.get(f'h{h}_coverage', float('nan')):.3f}" for h in HORIZONS_WEEKS]
            lines.append(f"| {year} | {' | '.join(cells)} |")
        lines.append("")
    path = out_dir / "lodo.md"
    path.write_text("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    run_lodo()
