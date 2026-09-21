"""Stage 2: configuration A plus SubX, evaluated once.

Configuration B is configuration A's prediction with two SubX anomaly features
appended: precipitation and temperature departure from the model's own
lead-dependent climatology, refit per fold with the held-out year removed.

What constrains this run:

- **2018 onward only.** The cached SubX is the forecast series, 2018-01 to
  2025-12. The hindcast series was not ingested, so B cannot see a row before
  2018 and A must be rescored on exactly the rows B sees. Comparing A on
  fifteen years against B on eight would be a row-set difference reported as
  skill.
- **Equal row sets, enforced rather than assumed.** The two arms are aligned on
  a shared finite mask before either is scored.
- **Fold-wise climatology with the leakage guard active.** Each fold's
  climatology excludes its own year and `assert_no_self_contribution` verifies
  it on the rows actually used.
- **The paired real-minus-shuffled rule.** A target switches to B only if the
  paired difference of B against A has a CI above zero in both domains. The raw
  BSS interval is not sufficient and is not used as the criterion: B has more
  probability spread than A by construction, which moves a Brier ratio on
  shuffled labels alone.

One run. The rule is applied mechanically to whatever comes out.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.config import Settings  # noqa: E402
from cofire.model.data.subx import (  # noqa: E402
    VARIABLES,
    assert_no_self_contribution,
    coverage_note,
    fold_climatology,
    load_chunks,
)
from cofire.model.prob_metrics import brier  # noqa: E402
from cofire.model.rerun_a import OUT, load_domain  # noqa: E402
from cofire.model.shipping import _drought_prediction, _fire_prediction  # noqa: E402
from cofire.model.stats_lib import paired_bss_shuffled  # noqa: E402

LOGGER = logging.getLogger("cofire.subx_arm")

SUBX_START = pd.Timestamp("2018-01-01")


def weekly_anomalies(settings: Settings | None = None) -> pd.DataFrame:
    """One row per issue week with the two anomaly features, fold-wise.

    Leads are averaged to a single weekly value per issue: the SubX grid is one
    degree against gridMET's four kilometres, and a per-lead join would assert
    more resolution than the source has.
    """
    out: pd.DataFrame | None = None
    for var in VARIABLES:
        frame = load_chunks(settings, var=var)
        if frame.empty:
            LOGGER.warning("no SubX chunks for %s", var)
            continue
        frame["issue"] = pd.to_datetime(frame["issue"])
        years = sorted(frame["issue"].dt.year.unique())
        parts: list[pd.DataFrame] = []
        for year in years:
            clim, used = fold_climatology(frame, var, exclude_year=int(year))
            assert_no_self_contribution(used, int(year))
            if clim.empty:
                continue
            fold = frame[frame["issue"].dt.year == year].copy()
            fold["woy"] = fold["issue"].dt.isocalendar().week.astype(int).clip(1, 52)
            fold = fold.merge(clim, on=["lead", "woy"], how="left")
            fold[f"{var}_anom"] = fold[var] - fold[f"{var}_clim"]
            parts.append(fold[["issue", f"{var}_anom"]])
        if not parts:
            continue
        per_issue = (
            pd.concat(parts, ignore_index=True)
            .groupby("issue")[f"{var}_anom"]
            .mean()
            .reset_index()
        )
        out = per_issue if out is None else out.merge(per_issue, on="issue", how="outer")
    return out if out is not None else pd.DataFrame(columns=["issue"])


def _attach(valid: pd.DataFrame, anom: pd.DataFrame) -> pd.DataFrame:
    """Join anomalies onto validation rows by nearest prior issue, within 7 days."""
    v = valid.copy()
    v["time"] = pd.to_datetime(v["time"])
    if anom.empty:
        for var in VARIABLES:
            v[f"{var}_anom"] = np.nan
        return v
    a = anom.sort_values("issue")
    merged = pd.merge_asof(
        v.sort_values("time"),
        a.rename(columns={"issue": "time"}),
        on="time",
        direction="backward",
        tolerance=pd.Timedelta("7D"),
    )
    return merged


def _arm_b(pred_a: np.ndarray, frame: pd.DataFrame, y: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    """A's prediction adjusted by a logistic on the SubX anomalies.

    B is deliberately A plus a small correction rather than a separate model:
    the question is whether SubX adds anything to A, and a model refit from
    scratch would confound that with everything else that changed.
    """
    from sklearn.linear_model import LogisticRegression

    feats = [f"{v}_anom" for v in VARIABLES]
    x = np.column_stack(
        [pd.to_numeric(frame.get(f), errors="coerce").to_numpy(dtype=float) for f in feats]
        + [np.log(np.clip(pred_a, 1e-6, 1 - 1e-6) / (1 - np.clip(pred_a, 1e-6, 1 - 1e-6)))]
    )
    ok = np.isfinite(x).all(axis=1) & np.isfinite(y)
    fit = ok & train_mask
    if fit.sum() < 100 or len(np.unique(y[fit])) < 2:
        return np.full(len(frame), np.nan)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(x[fit], y[fit])
    out = np.full(len(frame), np.nan)
    out[ok] = lr.predict_proba(x[ok])[:, 1]
    return out


def run(n_boot: int = 400, n_shuffles: int = 20) -> Path:
    from cofire.model.shipping import load as load_choices

    choices = load_choices(out_dir=OUT)
    if not choices:
        raise SystemExit("run stage_step1 first")

    anom = weekly_anomalies()
    LOGGER.info("SubX anomalies: %d issue weeks", len(anom))

    rows: list[dict[str, object]] = []
    for dom in ("larimer", "pueblo"):
        train, valid, _st = load_domain(dom)
        # Both arms see 2018 onward only, because that is all B can see.
        valid = valid[pd.to_datetime(valid["time"]) >= SUBX_START]
        train_sub = train[pd.to_datetime(train["time"]) >= SUBX_START]
        if valid.empty:
            LOGGER.warning("%s: no rows from %s", dom, SUBX_START.date())
            continue
        both = pd.concat([train_sub, valid], ignore_index=True)
        both = _attach(both, anom)
        is_train = np.arange(len(both)) < len(train_sub)

        for (target, h), c in sorted(choices.items()):
            if target not in both.columns:
                continue
            y_all = pd.to_numeric(both[target], errors="coerce").to_numpy(dtype=float)
            ev = both[~is_train]
            y = pd.to_numeric(ev[target], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
                continue
            pred_a_all = (
                _drought_prediction(h, train, target, both)
                if c.family == "markov"
                else _fire_prediction(c.family, train, target, both)
            )
            pred_b_all = _arm_b(pred_a_all, both, y_all, is_train)
            a = pred_a_all[~is_train]
            b = pred_b_all[~is_train]

            # Equal row sets, enforced: both arms scored on the same finite mask.
            keep = np.isfinite(a) & np.isfinite(b) & np.isfinite(y)
            if keep.sum() < 100:
                rows.append(
                    {"domain": dom, "target": target, "horizon": h, "n": int(keep.sum()),
                     "estimable": False, "reason": "fewer than 100 shared rows"}
                )
                continue
            a, b, y = a[keep], b[keep], y[keep]
            weeks = pd.to_datetime(ev["time"]).to_numpy()[keep]

            # A is the reference and B the model, so the statistic is the BSS
            # of B against A, real minus the same thing on shuffled targets.
            # B has more probability spread than A by construction, which moves
            # a Brier ratio on shuffled labels alone; the paired difference is
            # what removes that.
            res = paired_bss_shuffled(
                b, a, y, weeks, n_boot=n_boot, n_shuffles=n_shuffles
            )
            rows.append(
                {
                    "domain": dom, "target": target, "horizon": h,
                    "n": int(len(y)),
                    "brier_a": round(brier(a, y), 5),
                    "brier_b": round(brier(b, y), 5),
                    "bss_b_vs_a": round(1.0 - brier(b, y) / brier(a, y), 5)
                    if brier(a, y) > 1e-12 else np.nan,
                    "n_positive_weeks": res.n_positive_weeks,
                    "estimable": res.estimable,
                    "paired_diff": round(res.point, 5) if np.isfinite(res.point) else np.nan,
                    "paired_lo": round(res.lo, 5) if np.isfinite(res.lo) else np.nan,
                    "paired_hi": round(res.hi, 5) if np.isfinite(res.hi) else np.nan,
                    "ci_above_zero": bool(np.isfinite(res.lo) and res.lo > 0),
                    "reason": res.reason,
                }
            )
            LOGGER.info(
                "%s %-16s h=%d B-vs-A paired=%s", dom, target, h,
                "not estimable" if not res.estimable
                else f"{res.point:+.4f} [{res.lo:+.4f},{res.hi:+.4f}]",
            )

    df = pd.DataFrame(rows)
    # The rule: both domains must have a CI above zero.
    if not df.empty and "ci_above_zero" in df.columns:
        passed = (
            df[df["ci_above_zero"].fillna(False)]
            .groupby(["target", "horizon"])["domain"]
            .nunique()
        )
        both_dom = set(passed[passed >= 2].index)
        df["switches_to_b"] = [
            (t, h) in both_dom for t, h in zip(df["target"], df["horizon"], strict=True)
        ]
    else:
        df["switches_to_b"] = False

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "subx_verdict.csv"
    df.to_csv(path, index=False)
    (OUT / "subx_coverage_note.txt").write_text(
        coverage_note()
        + "\n\nThis run: cached SubX is the forecast series 2018-01 to 2025-12 only; "
        "the hindcast series was not ingested, so both arms were scored on 2018 "
        "onward rows and configuration A was rescored on exactly the rows B sees.\n"
    )
    LOGGER.info(
        "%d comparisons, %d estimable, %d with CI above zero, %d switching to B",
        len(df), int(df.get("estimable", pd.Series(dtype=bool)).sum()),
        int(df.get("ci_above_zero", pd.Series(dtype=bool)).fillna(False).sum()),
        int(df["switches_to_b"].sum()),
    )
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
