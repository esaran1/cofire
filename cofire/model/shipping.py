"""The shipping forecast layer: empirical conditional models. HAND-REWRITE.

What ships is the baseline, because the baseline is what survived. The ML arms
stay in the repo and in the ablation results, and they are not in this path.

Drought targets ship the fixed Markov model: support gated on independent
weeks, rates estimated from rows, a 0.75 blend toward staying put where a cell
lacks support. Fire targets ship whichever of the ERC-decile transition table
and the damped-persistence logistic wins on pooled leave-one-drought-year-out,
chosen once per target and then frozen.

The choice is made here, recorded to disk, and read back by everything
downstream. Nothing reselects at serve time.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.config import Settings  # noqa: E402
from cofire.model.prob_metrics import brier, brier_decomposition  # noqa: E402
from cofire.model.targets import (  # noqa: E402
    HORIZONS,
    SEASONS,
    MarkovBaseline,
    all_event_targets,
    damped_persistence_baseline,
    fire_transition_baseline,
    target_names,
)

LOGGER = logging.getLogger("cofire.shipping")

OUT_DIR = Path("artifacts/shipping")
FOLD_YEARS = (2020, 2021, 2024, 2025)
DOMAINS = ("larimer", "pueblo")
FIRE_ARMS = ("transition", "damped")


@dataclass(frozen=True)
class ShippingChoice:
    """One frozen decision: which family serves this target."""

    target: str
    horizon: int
    family: str          # "markov" | "transition" | "damped"
    pooled: bool         # whether the pooled-domain fit won on LODO
    lodo_brier: float
    reliability: float
    resolution: float


def _fire_prediction(arm: str, train: pd.DataFrame, target: str, index: pd.DataFrame) -> np.ndarray:
    if arm == "transition":
        return fire_transition_baseline(train, target, index)
    return damped_persistence_baseline(train, target, index)


def _drought_prediction(
    horizon: int, train: pd.DataFrame, target: str, index: pd.DataFrame
) -> np.ndarray:
    mk = MarkovBaseline(horizon=horizon).fit(train)
    return mk.predict_events(index).get(target, np.full(len(index), np.nan))


def lodo_score(
    frame: pd.DataFrame,
    target: str,
    horizon: int,
    family: str,
    fold_years: tuple[int, ...] = FOLD_YEARS,
    eval_domain: str | None = None,
) -> tuple[float, float, float]:
    """Pooled LODO Brier, reliability and resolution for one family.

    Scoring is always restricted to `eval_domain` when given, so a pooled fit is
    judged on the domain it has to serve rather than on the average of both.
    """
    t = pd.to_datetime(frame["time"])
    ps: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for year in fold_years:
        train = frame[t.dt.year != year]
        held = frame[t.dt.year == year]
        if eval_domain is not None and "domain" in held.columns:
            held = held[held["domain"] == eval_domain]
        if train.empty or held.empty:
            continue
        y = pd.to_numeric(held[target], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
            continue
        if family == "markov":
            p = _drought_prediction(horizon, train, target, held)
        else:
            p = _fire_prediction(family, train, target, held)
        ps.append(np.asarray(p, dtype=float))
        ys.append(y)
    if not ps:
        return float("nan"), float("nan"), float("nan")
    p_all, y_all = np.concatenate(ps), np.concatenate(ys)
    dec = brier_decomposition(p_all, y_all)
    return brier(p_all, y_all), dec["reliability"], dec["resolution"]


def choose(frame_by_domain: dict[str, pd.DataFrame]) -> list[ShippingChoice]:
    """Freeze one family per target, and decide pooling, on LODO only."""
    pooled = pd.concat(
        [f.assign(domain=d, domain_id=float(DOMAINS.index(d))) for d, f in frame_by_domain.items()],
        ignore_index=True,
    )
    choices: list[ShippingChoice] = []
    for h in HORIZONS:
        for target in target_names((h,)):
            if any(target not in f.columns for f in frame_by_domain.values()):
                continue
            is_fire = target.startswith("f_gt")
            arms = FIRE_ARMS if is_fire else ("markov",)

            best: ShippingChoice | None = None
            for arm in arms:
                # Per-domain fits, then the pooled fit, each scored on every
                # domain it must serve. Pooling wins only if it is at least as
                # good on the mean across domains.
                per_dom = [
                    lodo_score(f, target, h, arm)[0] for f in frame_by_domain.values()
                ]
                per_dom_mean = float(np.nanmean(per_dom)) if per_dom else float("nan")
                pooled_scores = [
                    lodo_score(pooled, target, h, arm, eval_domain=d)[0] for d in frame_by_domain
                ]
                pooled_mean = float(np.nanmean(pooled_scores)) if pooled_scores else float("nan")

                use_pooled = np.isfinite(pooled_mean) and (
                    not np.isfinite(per_dom_mean) or pooled_mean <= per_dom_mean
                )
                score = pooled_mean if use_pooled else per_dom_mean
                if not np.isfinite(score):
                    continue
                src = pooled if use_pooled else next(iter(frame_by_domain.values()))
                _b, rel, res = lodo_score(src, target, h, arm)
                cand = ShippingChoice(target, h, arm, bool(use_pooled), score, rel, res)
                if best is None or cand.lodo_brier < best.lodo_brier:
                    best = cand
            if best is not None:
                choices.append(best)
                LOGGER.info(
                    "%-14s h=%d -> %-11s pooled=%-5s lodo_brier=%.5f rel=%.6f res=%.6f",
                    best.target, best.horizon, best.family, best.pooled,
                    best.lodo_brier, best.reliability, best.resolution,
                )
    return choices


def save(choices: list[ShippingChoice], out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "target": c.target,
            "horizon": c.horizon,
            "family": c.family,
            "pooled": c.pooled,
            "lodo_brier": round(c.lodo_brier, 6),
            "reliability": round(c.reliability, 6),
            "resolution": round(c.resolution, 6),
        }
        for c in choices
    ]
    p = out_dir / "choices.json"
    p.write_text(json.dumps(payload, indent=2))
    pd.DataFrame(payload).to_csv(out_dir / "choices.csv", index=False)
    return p


def load(out_dir: Path = OUT_DIR) -> dict[tuple[str, int], ShippingChoice]:
    """The frozen choices. Nothing reselects at serve time."""
    p = out_dir / "choices.json"
    if not p.exists():
        return {}
    out: dict[tuple[str, int], ShippingChoice] = {}
    for r in json.loads(p.read_text()):
        c = ShippingChoice(
            r["target"], int(r["horizon"]), r["family"], bool(r["pooled"]),
            float(r["lodo_brier"]), float(r["reliability"]), float(r["resolution"]),
        )
        out[(c.target, c.horizon)] = c
    return out


def predict(
    target: str, horizon: int, train: pd.DataFrame, index: pd.DataFrame
) -> np.ndarray:
    """Serve one target from its frozen family."""
    choice = load().get((target, horizon))
    family = choice.family if choice else ("transition" if target.startswith("f_gt") else "markov")
    if family == "markov":
        return _drought_prediction(horizon, train, target, index)
    return _fire_prediction(family, train, target, index)


def run() -> Path:
    from cofire.model.ablation import _splits
    from cofire.model.features import load_features

    frames: dict[str, pd.DataFrame] = {}
    for dom in DOMAINS:
        os.environ["COFIRE_SUBSET_NAME"] = dom
        st = Settings()
        f = load_features(st.processed_dir / "features_v1")
        if f.empty:
            continue
        f = all_event_targets(f, HORIZONS)
        train, _cal, _valid = _splits(f, st, 0.25)
        frames[dom] = train
    if not frames:
        raise SystemExit("no domains available")
    choices = choose(frames)
    out = save(choices)
    LOGGER.info("froze %d shipping choices -> %s", len(choices), out)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())


# ------------------------------------------------------ continuous forecast


CONTINUOUS_ARMS = ("damped_regression", "decile_mean")


def damped_regression(
    train: pd.DataFrame, horizon: int, index: pd.DataFrame, target: str = "erc_pct"
) -> np.ndarray:
    """Least-squares regression of the future percentile on today's.

    The continuous analogue of the damped-persistence logistic: one predictor,
    two parameters. The fitted slope is normally below one, which is the damping
    and is why plain persistence is the wrong continuous baseline.
    """
    col = f"{target}_h{horizon}"
    x = pd.to_numeric(train.get(target), errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(train.get(col), errors="coerce").to_numpy(dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    xi = pd.to_numeric(index.get(target), errors="coerce").to_numpy(dtype=float)
    if m.sum() < 50:
        fill = float(np.nanmean(y)) if np.isfinite(y).any() else 50.0
        return np.full(len(index), fill, dtype=float)
    slope, intercept = np.polyfit(x[m], y[m], 1)
    med = float(np.nanmedian(x[m]))
    xi = np.where(np.isfinite(xi), xi, med)
    return np.asarray(np.clip(intercept + slope * xi, 0.0, 100.0), dtype=float)


def decile_mean(
    train: pd.DataFrame, horizon: int, index: pd.DataFrame, target: str = "erc_pct"
) -> np.ndarray:
    """Conditional mean of the future percentile by current decile and season.

    The continuous analogue of the transition table, with the same week-gated
    support rule the probabilistic version uses.
    """
    col = f"{target}_h{horizon}"
    tr = train[["time", target, col]].copy()
    tr["time"] = pd.to_datetime(tr["time"])
    tr["season"] = tr["time"].dt.month.map(SEASONS)
    x = pd.to_numeric(tr[target], errors="coerce")
    tr["dec"] = np.clip((x // 10).astype(float), 0, 9)
    tr["_y"] = pd.to_numeric(tr[col], errors="coerce")
    tr = tr.dropna(subset=["_y", "dec"])
    overall = float(tr["_y"].mean()) if len(tr) else 50.0

    by_ds: dict[tuple[float, str], float] = {}
    for (dec, sea), g in tr.groupby(["dec", "season"]):
        if g["time"].nunique() >= 32:
            by_ds[(float(dec), str(sea))] = float(g["_y"].mean())
    by_d = {
        float(dec): float(g["_y"].mean())
        for dec, g in tr.groupby("dec")
        if g["time"].nunique() >= 32
    }

    idx = index[["time", target]].copy()
    idx["time"] = pd.to_datetime(idx["time"])
    idx["season"] = idx["time"].dt.month.map(SEASONS)
    xi = pd.to_numeric(idx[target], errors="coerce")
    idx["dec"] = np.clip((xi // 10).astype(float), 0, 9)

    out = np.full(len(idx), overall, dtype=float)
    for i, (dec, sea) in enumerate(zip(idx["dec"].to_numpy(), idx["season"].to_numpy(), strict=True)):
        if not np.isfinite(dec):
            continue
        out[i] = by_ds.get((float(dec), str(sea)), by_d.get(float(dec), overall))
    return out


def continuous_predict(
    arm: str, train: pd.DataFrame, horizon: int, index: pd.DataFrame
) -> np.ndarray:
    return (
        damped_regression(train, horizon, index)
        if arm == "damped_regression"
        else decile_mean(train, horizon, index)
    )


def choose_continuous(
    frame_by_domain: dict[str, pd.DataFrame], fold_years: tuple[int, ...] = FOLD_YEARS
) -> dict[int, str]:
    """One continuous arm per horizon, chosen once on pooled LODO MAE."""
    pooled = pd.concat(frame_by_domain.values(), ignore_index=True)
    t = pd.to_datetime(pooled["time"])
    chosen: dict[int, str] = {}
    for h in HORIZONS:
        scores: dict[str, float] = {}
        for arm in CONTINUOUS_ARMS:
            errs: list[float] = []
            for year in fold_years:
                tr, te = pooled[t.dt.year != year], pooled[t.dt.year == year]
                if tr.empty or te.empty:
                    continue
                y = pd.to_numeric(te.get(f"erc_pct_h{h}"), errors="coerce").to_numpy(dtype=float)
                p = continuous_predict(arm, tr, h, te)
                m = np.isfinite(y) & np.isfinite(p)
                if m.any():
                    errs.append(float(np.mean(np.abs(p[m] - y[m]))))
            scores[arm] = float(np.mean(errs)) if errs else float("inf")
        best = min(scores, key=lambda k: scores[k])
        chosen[h] = best
        LOGGER.info("h=%d continuous arm -> %s (LODO MAE %s)",
                    h, best, {k: round(v, 3) for k, v in scores.items()})
    return chosen
