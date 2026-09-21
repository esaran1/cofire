"""Run the pre-registered PID comparison. HAND-REWRITE.

Follows `docs/PREREGISTRATION_V1.md`, hash recorded in STATUS.md before any of
this ran. Six arms, two domains, three horizons, target coverage 0.90.

The 2026 holdout is never opened. Scores come from the calibration and
validation splits only, and the runner asserts that no evaluated row falls in
2026 before it computes anything.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from cofire.model.config import COVERAGE_TARGET
from cofire.model.uncertainty.pid import ARMS, run_arm

LOGGER = logging.getLogger("cofire.uncertainty.run_pid")

HOLDOUT_YEAR = 2026
HORIZONS = (2, 4, 8)
PRED_DIR = Path("artifacts/predictions")
OUT_DIR = Path("artifacts/uncertainty")


def _assert_no_holdout(frame: pd.DataFrame, where: str) -> None:
    """The look counter stays at 2. Nothing here may touch 2026."""
    years = pd.to_datetime(frame["time"]).dt.year.unique()
    bad = [int(y) for y in years if int(y) >= HOLDOUT_YEAR]
    if bad:
        raise SystemExit(
            f"{where}: rows from {bad} would open the sealed holdout. "
            "This session takes no look."
        )


def scores_for(frame: pd.DataFrame, horizon: int, target: str = "erc_pct") -> pd.DataFrame:
    """Absolute residuals as conformity scores, ordered by week.

    Ordering matters: these controllers are sequential, so feeding them rows in
    storage order rather than time order would measure nothing real.
    """
    col_hat, col_true = f"{target}_h{horizon}_hat", f"{target}_h{horizon}"
    if col_hat not in frame.columns or col_true not in frame.columns:
        return pd.DataFrame()
    out = frame[["time", "cell_id", col_hat, col_true]].copy()
    out["time"] = pd.to_datetime(out["time"])
    out["score"] = (
        pd.to_numeric(out[col_true], errors="coerce")
        - pd.to_numeric(out[col_hat], errors="coerce")
    ).abs()
    out = out[np.isfinite(out["score"])]
    return out.sort_values(["time", "cell_id"]).reset_index(drop=True)


def weekly_coverage(frame: pd.DataFrame, covered: np.ndarray) -> pd.Series:
    """Coverage per week, which is the unit the endpoints are defined on."""
    g = frame.assign(_c=covered).groupby(frame["time"])
    return g["_c"].mean()


def transition_weeks(frame: pd.DataFrame, source: pd.DataFrame) -> set[pd.Timestamp]:
    """Weeks where the domain-mean USDM category changed.

    Identified from the observed target series alone, never from a model
    output, so the definition cannot be tuned to flatter a controller.
    """
    if "usdm" not in source.columns:
        return set()
    s = source.copy()
    s["time"] = pd.to_datetime(s["time"])
    m = s.groupby("time")["usdm"].mean().sort_index()
    changed = m.diff().abs() > 1e-9
    return set(pd.DatetimeIndex(m.index[changed]))


def evaluate_arm(
    arm: str, scored: pd.DataFrame, trans: set[pd.Timestamp]
) -> dict[str, object]:
    """One arm on one score stream, against the pre-registered endpoints."""
    radii, covered = run_arm(arm, scored["score"].to_numpy())
    wk = weekly_coverage(scored, covered)
    dev = (wk - COVERAGE_TARGET).abs()
    roll = wk.rolling(8, min_periods=4).mean()
    roll_dev = (roll - COVERAGE_TARGET).abs()

    in_trans = [w for w in wk.index if w in trans]
    return {
        "arm": arm,
        "n": int(len(scored)),
        "n_weeks": int(len(wk)),
        "coverage": float(np.mean(covered)),
        # Primary endpoint, fixed in the pre-registration.
        "mean_abs_cov_dev": float(dev.mean()),
        # Secondary endpoints.
        "mean_width": float(2.0 * np.mean(radii)),
        "worst_roll8_dev": float(roll_dev.max()) if roll_dev.notna().any() else float("nan"),
        "coverage_in_transitions": float(wk.loc[in_trans].mean()) if in_trans else float("nan"),
        "n_transition_weeks": len(in_trans),
    }


# Rough bounding boxes, used only to verify that a prediction file actually
# holds the domain it is being reported as. They are not used to subset.
DOMAIN_BBOX = {
    "larimer": (-106.20, 40.25, -104.94, 41.00),
    "pueblo": (-105.051, 37.735, -104.054, 38.522),
}


def _assert_is_domain(frame: pd.DataFrame, domain: str) -> None:
    """Refuse to label one domain's predictions as another's.

    The first run of this comparison reported byte-identical results for both
    domains, because `run_domain` took a domain argument and then read the same
    files regardless. Two-domain agreement is the brief's main guard against
    overfitting to one geography, so silently counting one domain twice would
    have turned that guard into a rubber stamp.
    """
    box = DOMAIN_BBOX.get(domain)
    if box is None or frame.empty:
        return
    w, s_, e, n = box
    lat, lon = frame["lat"].to_numpy(float), frame["lon"].to_numpy(float)
    inside = float(np.mean((lat >= s_) & (lat <= n) & (lon >= w) & (lon <= e)))
    if inside < 0.5:
        raise SystemExit(
            f"predictions labelled {domain!r} have only {inside:.1%} of rows inside "
            f"its bbox; this file is a different domain. Re-run the pipeline for "
            f"{domain} before reporting it."
        )


def _domain_pred_dir(domain: str) -> Path:
    """Where this domain's prediction parquets live.

    Pueblo is the active subset and writes to artifacts/predictions. Any other
    domain must have its own directory, so a stale shared file cannot be served
    for it.
    """
    if domain == "pueblo":
        return PRED_DIR
    cand = Path(f"artifacts/predictions_{domain}")
    return cand if cand.exists() else PRED_DIR


def run_domain(domain: str) -> list[dict[str, object]]:
    """Every arm and horizon for one domain."""
    pred = _domain_pred_dir(domain)
    cal = pd.read_parquet(pred / "ensemble_calibrate.parquet")
    val = pd.read_parquet(pred / "ensemble_valid.parquet")
    _assert_no_holdout(cal, "calibrate split")
    _assert_no_holdout(val, "validation split")
    _assert_is_domain(val, domain)
    _assert_is_domain(cal, domain)

    # Calibration first, then validation: the controller warms up on the
    # calibration split and is scored as it runs forward into validation, which
    # is the sequential setting these methods are designed for.
    both = pd.concat([cal, val], ignore_index=True)
    _assert_no_holdout(both, "combined stream")

    rows: list[dict[str, object]] = []
    for h in HORIZONS:
        scored = scores_for(both, h)
        if scored.empty:
            LOGGER.warning("%s h=%d: no scores, skipping", domain, h)
            continue
        trans = transition_weeks(scored, both)
        for arm in ARMS:
            rec = evaluate_arm(arm, scored, trans)
            rec.update({"domain": domain, "horizon": h})
            rows.append(rec)
            LOGGER.info(
                "%s h=%d %-8s cov=%.3f dev=%.4f width=%.2f worst8=%.4f",
                domain, h, arm, rec["coverage"], rec["mean_abs_cov_dev"],
                rec["mean_width"], rec["worst_roll8_dev"],
            )
    return rows


def adoption_verdict(df: pd.DataFrame) -> dict[str, object]:
    """Apply the pre-registered decision rule. No post-hoc criteria.

    PID is adopted over ACI only if, on *both* domains, mean absolute coverage
    deviation improves by at least 0.01 and mean interval width grows by no
    more than 5%.
    """
    verdicts: dict[str, object] = {}
    per_domain: list[bool] = []
    for dom, g in df.groupby("domain"):
        aci = g[g["arm"] == "aci"]
        pid = g[g["arm"] == "pid_full"]
        if aci.empty or pid.empty:
            verdicts[str(dom)] = "not computable"
            per_domain.append(False)
            continue
        d_dev = float(aci["mean_abs_cov_dev"].mean() - pid["mean_abs_cov_dev"].mean())
        w_ratio = float(pid["mean_width"].mean() / max(aci["mean_width"].mean(), 1e-9))
        ok = (d_dev >= 0.01) and (w_ratio <= 1.05)
        per_domain.append(ok)
        verdicts[str(dom)] = {
            "dev_improvement": round(d_dev, 4),
            "width_ratio": round(w_ratio, 4),
            "meets_rule": ok,
        }
    # The pre-registered rule requires BOTH domains. One domain passing is not
    # the rule being met; it is the rule being untested. Adopting on partial
    # evidence would quietly discard the guard against fitting one geography.
    required = set(DOMAIN_BBOX)
    present = set(df["domain"].astype(str).unique())
    missing = sorted(required - present)
    verdicts["domains_evaluated"] = sorted(present)
    if missing:
        verdicts["adopted"] = False
        verdicts["note"] = (
            f"not adopted: {', '.join(missing)} not evaluated, and the rule "
            "requires both domains. See STATUS.md."
        )
        return verdicts
    verdicts["adopted"] = bool(per_domain) and all(per_domain)
    if not verdicts["adopted"] and any(per_domain):
        verdicts["note"] = "domain dependent, not adopted"
    return verdicts


def run(domains: tuple[str, ...] = ("larimer", "pueblo")) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for dom in domains:
        try:
            rows.extend(run_domain(dom))
        except FileNotFoundError as exc:
            LOGGER.warning("%s: %s", dom, exc)
    if not rows:
        raise SystemExit("no PID rows produced")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "pid_results.csv", index=False)
    verdict = adoption_verdict(df)
    (OUT_DIR / "pid_verdict.json").write_text(json.dumps(verdict, indent=2))
    LOGGER.info("verdict: %s", verdict)
    return OUT_DIR / "pid_results.csv"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
