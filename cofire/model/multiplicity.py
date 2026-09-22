"""Stage 1: multiplicity control over every target, under the paired test.

Three filters, applied in this order:

1. **Estimability.** A target with fewer than 12 positive weeks in the
   evaluation set is reported not estimable and carries no p-value. Order
   statistics and rates from a handful of values are not evidence, and this
   floor is the same one the bootstrap applies.
2. **The paired real-minus-shuffled test.** The statistic is the BSS against
   the target's headline reference, on real targets minus the same statistic on
   targets shuffled within the same circular blocks. A raw BSS interval is not
   enough: two models that are both functions of the same input differ in Brier
   on shuffled labels through probability spread alone, which is how seven fire
   targets passed an interval that was measuring spread.
3. **Multiplicity.** Benjamini-Hochberg at q=0.10 across every estimable
   target and both domains, and Holm within each event family, where a family
   is the horizon variants of one event. Holm is the stricter of the two inside
   a family because the horizons of one event are the same question asked
   three times, and a survivor must clear both.

A survivor is a target-and-domain pair that is estimable, has a paired
difference CI above zero, and is retained by both BH and Holm.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cofire.model.rerun_a import OUT, load_domain  # noqa: E402
from cofire.model.shipping import (  # noqa: E402
    _drought_prediction,
    _fire_prediction,
)
from cofire.model.stats_lib import (  # noqa: E402
    bootstrap_pvalue,
    multipletests_bh,
    multipletests_holm,
    paired_bss_shuffled,
)
from cofire.model.targets import (  # noqa: E402
    fire_transition_baseline,
    seasonal_climatology_baseline,
)

LOGGER = logging.getLogger("cofire.multiplicity")

Q = 0.10
ALPHA_HOLM = 0.10


def family_of(target: str) -> str:
    """The event a target belongs to, with its horizon stripped.

    `f_gt90_h2`, `f_gt90_h4` and `f_gt90_h8` are one family: the same event
    asked at three ranges. Holm runs inside the family.
    """
    return re.sub(r"_h\d+$", "", target)


def run(n_boot: int = 400, n_shuffles: int = 20) -> Path:
    """Every shipped target, both domains, one code path."""
    from cofire.model.shipping import load as load_choices

    choices = load_choices(out_dir=OUT)
    if not choices:
        raise SystemExit("run stage_step1 first")

    rows: list[dict[str, object]] = []
    for dom in ("larimer", "pueblo"):
        train, valid, _st = load_domain(dom)
        weeks = pd.to_datetime(valid["time"]).to_numpy()
        for (target, h), c in sorted(choices.items()):
            if target not in valid.columns:
                continue
            y = pd.to_numeric(valid[target], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(y).any() or len(np.unique(y[np.isfinite(y)])) < 2:
                continue
            pred = (
                _drought_prediction(h, train, target, valid)
                if c.family == "markov"
                else _fire_prediction(c.family, train, target, valid)
            )
            is_fire = target.startswith("f_gt")
            ref_name = "transition" if is_fire else "seasonal"
            ref = (
                fire_transition_baseline(train, target, valid)
                if is_fire
                else seasonal_climatology_baseline(train, target, valid)
            )

            # One code path for both arms: the real target and each shuffled
            # target are scored by the same function on the same rows. The
            # per-week precomputation makes a full pass fit inside a stage and
            # preserves the multiplicity of repeated weeks in a replicate,
            # which a membership test on week labels does not.
            res = paired_bss_shuffled(
                pred, ref, y, weeks, n_boot=n_boot, n_shuffles=n_shuffles
            )
            p = bootstrap_pvalue(res)
            rows.append(
                {
                    "domain": dom,
                    "target": target,
                    "horizon": h,
                    "family": family_of(target),
                    "arm": c.family,
                    "ref": ref_name,
                    "n_positive_weeks": res.n_positive_weeks,
                    "estimable": res.estimable,
                    "paired_diff": round(res.point, 5) if np.isfinite(res.point) else np.nan,
                    "paired_lo": round(res.lo, 5) if np.isfinite(res.lo) else np.nan,
                    "paired_hi": round(res.hi, 5) if np.isfinite(res.hi) else np.nan,
                    "ci_above_zero": bool(np.isfinite(res.lo) and res.lo > 0),
                    "pvalue": round(p, 6) if np.isfinite(p) else np.nan,
                    "reason": res.reason,
                }
            )
            LOGGER.info(
                "%s %-16s h=%d paired=%s posWk=%d",
                dom, target, h,
                "not estimable" if not res.estimable
                else f"{res.point:+.4f} [{res.lo:+.4f},{res.hi:+.4f}]",
                res.n_positive_weeks,
            )

    df = pd.DataFrame(rows)

    # BH across every estimable target and both domains, together.
    df["bh_reject"] = False
    est = df["estimable"] & df["pvalue"].notna()
    if est.any():
        df.loc[est, "bh_reject"] = multipletests_bh(
            df.loc[est, "pvalue"].tolist(), q=Q
        )

    # Holm inside each event family, per domain: the horizons of one event.
    df["holm_reject"] = False
    for (_dom, _fam), g in df[est].groupby(["domain", "family"]):
        df.loc[g.index, "holm_reject"] = multipletests_holm(
            g["pvalue"].tolist(), alpha=ALPHA_HOLM
        )

    df["survivor"] = df["estimable"] & df["ci_above_zero"] & df["bh_reject"] & df["holm_reject"]

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "multiplicity.csv"
    df.to_csv(path, index=False)
    LOGGER.info(
        "%d rows, %d estimable, %d CI above zero, %d BH, %d Holm, %d survivors",
        len(df), int(df["estimable"].sum()), int(df["ci_above_zero"].sum()),
        int(df["bh_reject"].sum()), int(df["holm_reject"].sum()),
        int(df["survivor"].sum()),
    )
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run())
