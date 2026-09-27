"""v1.1 Stage 5: the leak-free survivor test across five domains.

Exactly the test in `sensitivity.stage1`, run per domain with that domain's
families (frozen for Larimer and Pueblo, v1.1 for the new domains), then
combined: BH at q = 0.10 across every estimable pair in all five domains, Holm
within domain and event family, and the agreement rule stated in
docs/DECISIONS.md before this ran. Validation reliability is reported for the
per-cell forecast and for the regional base rate, and decides rendering for
the new domains. Nothing is computed on 2026.

    python -m cofire.ship.survivors_v11 domain <domain>
    python -m cofire.ship.survivors_v11 combine
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.ship import build_v11, domains, fit_v11  # noqa: E402

LOGGER = logging.getLogger("cofire.ship.survivors_v11")
OUT = Path("artifacts/v11")
TRAIN_END = pd.Timestamp("2021-12-31")
VALID_START, VALID_END = pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")
RELIABILITY_MAX = 0.05  # the preregistered look-3 threshold


def run_domain(domain: str, n_boot: int = 400, n_shuffles: int = 20) -> Path:
    from cofire.model.erc_pct import erc_percentile_reference
    from cofire.model.multiplicity import family_of
    from cofire.model.prob_metrics import brier, brier_decomposition
    from cofire.model.stats_lib import bootstrap_pvalue, paired_bss_shuffled
    from cofire.model.targets import fire_transition_baseline, seasonal_climatology_baseline
    from cofire.ship.export import regional_base_rate

    out = OUT / "survivors" / f"{domain}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    choices = fit_v11.load_choices(domain)
    f = build_v11.load(domain)
    upto = f[f["time"] <= VALID_END].reset_index(drop=True)
    assert upto["time"].max() < pd.Timestamp("2026-01-01")
    pct = erc_percentile_reference(upto, (upto["time"] <= TRAIN_END).to_numpy())
    stored = pd.to_numeric(upto["erc_pct"], errors="coerce").to_numpy(float)
    assert np.allclose(pct, stored, equal_nan=True), f"{domain}: stored erc_pct is not training-only"
    g = fit_v11.with_targets(upto, pct)
    gt = g["time"]
    train = g[gt <= TRAIN_END]
    valid = g[(gt >= VALID_START) & (gt <= VALID_END)]
    weeks = pd.to_datetime(valid["time"]).to_numpy()

    rows: list[dict[str, Any]] = []
    for (target, h), c in sorted(choices.items()):
        if target not in valid.columns:
            continue
        y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
            continue
        clean = fit_v11.embargo(train, TRAIN_END + pd.Timedelta(days=1), h)
        assert (pd.to_datetime(clean["time"]) + pd.Timedelta(weeks=h) <= TRAIN_END).all()
        pred = fit_v11.predict_event(c.family, h, clean, target, valid)
        fire = target.startswith("f_gt")
        ref = (fire_transition_baseline(clean, target, valid) if fire
               else seasonal_climatology_baseline(clean, target, valid))
        res = paired_bss_shuffled(pred, ref, y, weeks, n_boot=n_boot, n_shuffles=n_shuffles)
        m = np.isfinite(pred) & np.isfinite(ref) & np.isfinite(y)
        real = 1.0 - brier(pred[m], y[m]) / brier(ref[m], y[m]) if m.any() else np.nan

        base = regional_base_rate(clean, target, valid)
        mp = np.isfinite(pred) & np.isfinite(y)
        mb = np.isfinite(base) & np.isfinite(y)
        rel_cell = float(brier_decomposition(pred[mp], y[mp])["reliability"]) if mp.sum() >= 100 else np.nan
        rel_base = float(brier_decomposition(base[mb], y[mb])["reliability"]) if mb.sum() >= 100 else np.nan
        rows.append({
            "domain": domain, "target": target, "horizon": h, "family": family_of(target),
            "arm": c.family, "n_positive_weeks": res.n_positive_weeks, "estimable": res.estimable,
            "paired_diff": res.point, "paired_lo": res.lo, "paired_hi": res.hi,
            "ci_above_zero": bool(np.isfinite(res.lo) and res.lo > 0),
            "pvalue": bootstrap_pvalue(res),
            "bss_real": real,
            "bss_shuffled": real - res.point if np.isfinite(res.point) else np.nan,
            "rows_dropped_by_embargo": int(len(train) - len(clean)),
            "n_valid": int(mp.sum()), "base_rate_valid": float(y[mp].mean()) if mp.any() else np.nan,
            "reliability_cell": rel_cell, "reliability_base_rate": rel_base,
            "brier_cell": brier(pred[mp], y[mp]) if mp.any() else np.nan,
            "brier_base_rate": brier(base[mb], y[mb]) if mb.any() else np.nan,
        })
        LOGGER.info("%s %-16s paired=%+.4f [%+.4f, %+.4f] rel=%.4f", domain, target,
                    res.point, res.lo, res.hi, rel_cell)
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def combine() -> pd.DataFrame:
    from cofire.model.multiplicity import ALPHA_HOLM, Q
    from cofire.model.stats_lib import multipletests_bh, multipletests_holm

    df = pd.concat([pd.read_csv(OUT / "survivors" / f"{d}.csv") for d in domains.ORDER], ignore_index=True)
    est = df["estimable"].astype(bool) & df["pvalue"].notna()
    df["bh_reject"] = False
    df.loc[est, "bh_reject"] = multipletests_bh(df.loc[est, "pvalue"].tolist(), q=Q)
    df["holm_reject"] = False
    for _k, grp in df[est].groupby(["domain", "family"]):
        df.loc[grp.index, "holm_reject"] = multipletests_holm(grp["pvalue"].tolist(), alpha=ALPHA_HOLM)
    df["survivor"] = df["estimable"].astype(bool) & df["ci_above_zero"] & df["bh_reject"] & df["holm_reject"]

    # Agreement: passes wherever estimable, and in at least two domains.
    agree: dict[str, bool] = {}
    for tg, grp in df.groupby("target"):
        e = grp[grp["estimable"].astype(bool)]
        agree[str(tg)] = bool(len(e) > 0 and e["survivor"].all() and int(e["survivor"].sum()) >= 2)
    df["target_agrees_across_domains"] = df["target"].map(agree)

    # Rendering for the new domains, decided on validation.
    def state(r: pd.Series) -> tuple[str, str]:
        if r["domain"] not in domains.NEW:
            return "look3", "Larimer and Pueblo keep their look-3 rendering"
        if not bool(r["estimable"]):
            return "base_rate", f"{int(r['n_positive_weeks'])} positive validation weeks, fewer than 12"
        if not (np.isfinite(r["reliability_cell"]) and r["reliability_cell"] <= RELIABILITY_MAX):
            return "base_rate", f"validation reliability {r['reliability_cell']:.4f} above {RELIABILITY_MAX}"
        return "probability", f"validation reliability {r['reliability_cell']:.4f}"

    st = df.apply(state, axis=1, result_type="expand")
    df["render"], df["render_reason"] = st[0], st[1]

    frozen = pd.read_csv("artifacts/audit/survivors_embargoed.csv")
    cur = frozen[frozen["survivor"].astype(bool)][["domain", "target"]]
    df["current_survivor"] = df.set_index(["domain", "target"]).index.isin(
        cur.set_index(["domain", "target"]).index)
    strongest = float(df.loc[df["current_survivor"], "bss_real"].max())
    df["flag_surprisingly_strong"] = df["domain"].isin(domains.NEW) & (df["bss_real"] > strongest)
    df.to_csv(OUT / "survivors_v11.csv", index=False)
    summary = {
        "n_pairs": int(len(df)), "n_estimable": int(est.sum()), "n_survivors": int(df["survivor"].sum()),
        "current_survivors_hold": int(df.loc[df["current_survivor"], "survivor"].sum()),
        "current_survivors_total": int(df["current_survivor"].sum()),
        "strongest_current_bss": strongest,
        "agreeing_targets": sorted(k for k, v in agree.items() if v),
        "fire_survivors": int(df.loc[df["target"].str.startswith("f_gt"), "survivor"].sum()),
    }
    (OUT / "survivors_v11_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if sys.argv[1] == "domain":
        print(run_domain(sys.argv[2]))
    elif sys.argv[1] == "combine":
        combine()
        print((OUT / "survivors_v11_summary.json").read_text())
    else:
        raise SystemExit(__doc__)
