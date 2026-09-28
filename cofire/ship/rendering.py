"""The preregistered rendering rules, applied mechanically.

Fixed in `docs/PREREGISTRATION_LOOK3.md` before look 3, so no result could be
read into a rendering decision after the fact. This module is the single place
those rules become code, and it decides from artifacts alone.

The four states a target-horizon-domain can render in:

- `interval`: point forecast plus the PID interval. Only where Stage B
  classified the continuous horizon informative on the extended record. Look 3's
  own width ratios are better than Stage B's on every horizon, and by rule they
  change nothing.
- `historical_range`: point forecast plus the labelled historical week-of-year
  range of raw ERC. Where Stage B classified the horizon climatological.
- `base_rate`: the per-cell probability is not shown. Fire targets show the
  area's seasonal rate instead; drought targets show no number, because a
  historical rate beside the model's other drought odds could contradict them. For a
  probabilistic target that failed the look-3 reliability criterion, or that has
  no resolution to offer.
- `uncalibrated`: no interval at all, with the reason shown. For a horizon that
  failed any of the look-3 PID tests. No horizon failed, and the path is kept
  because a later run could.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger("cofire.ship.rendering")

ART = Path("artifacts")
RERUN = ART / "rerun_a"
LOOK3 = ART / "look3"

INTERVAL = "interval"
HISTORICAL_RANGE = "historical_range"
BASE_RATE = "base_rate"
UNCALIBRATED = "uncalibrated"

# The look-3 reliability threshold, preregistered. Repeated from
# `cofire.model.look3` rather than imported so that reading this file tells the
# reader what the rule is; `test_rendering.py` asserts the two agree.
RELIABILITY_MAX = 0.05
# A target whose forecasts barely separate events from non-events has nothing
# to say per cell, whatever its Brier score.
MIN_RESOLUTION = 1e-4


def shown_instead(target: str) -> str:
    """What a base-rate target shows in place of a per-cell probability."""
    if target.startswith("d_"):
        return ("no number is shown: a historical rate beside the model's other drought odds "
                "could contradict them on the same card")
    return "the historical rate for this area at this time of year is shown instead"


@dataclass(frozen=True)
class Decision:
    domain: str
    target: str
    horizon: int
    state: str
    reason: str


def _interval_failures() -> dict[tuple[str, int], str]:
    """Horizons that failed any look-3 PID test, with the first reason."""
    path = LOOK3 / "criteria.csv"
    if not path.exists():
        return {}
    crit = pd.read_csv(path)
    out: dict[tuple[str, int], str] = {}
    for _, row in crit[~crit["passed"].astype(bool)].iterrows():
        name = str(row["name"])
        if name.startswith("5"):  # reliability, not an interval test
            continue
        scope = str(row["scope"]).split()
        if len(scope) != 2 or not scope[1].startswith("h"):
            continue
        key = (scope[0], int(scope[1][1:]))
        out.setdefault(
            key,
            f"{name} on the 2026 holdout: {row['observed']}, needed {row['threshold']}",
        )
    return out


def _reliability_failures() -> dict[tuple[str, str], float]:
    """Probabilistic targets that failed the look-3 reliability criterion."""
    path = LOOK3 / "reliability.csv"
    if not path.exists():
        return {}
    rel = pd.read_csv(path)
    bad = rel[rel["reliability"] > RELIABILITY_MAX]
    return {
        (str(r["domain"]), str(r["target"])): float(r["reliability"])
        for _, r in bad.iterrows()
    }


def _zero_resolution() -> dict[tuple[str, str], float]:
    """Targets whose forecasts separate events from non-events barely or not at all."""
    path = LOOK3 / "reliability.csv"
    if not path.exists():
        return {}
    rel = pd.read_csv(path)
    low = rel[rel["resolution"] <= MIN_RESOLUTION]
    return {
        (str(r["domain"]), str(r["target"])): float(r["resolution"])
        for _, r in low.iterrows()
    }


def _realtime_verdict() -> dict[str, object] | None:
    """The real-time interval audit, if it has been run.

    The look-3 interval tests passed, but they were computed with same-week
    updates a real-time forecaster cannot make (see cofire/ship/pid_audit.py).
    A test that was invalid cannot count as a pass, and the valid version
    fails, so the pre-registered consequence of a failed interval test applies:
    `uncalibrated`, no band, reason stated.
    """
    import json

    path = ART / "audit" / "pid_realtime.json"
    if not path.exists():
        return None
    verdict: dict[str, object] = json.loads(path.read_text())["verdict"]
    return verdict


def continuous_decisions() -> list[Decision]:
    """One decision per domain and horizon for the continuous ERC forecast.

    Stage B decides interval against historical range; look 3's PID tests can
    override to `uncalibrated`.
    """
    cls = pd.read_csv(RERUN / "classification.csv")
    failures = _interval_failures()
    realtime = _realtime_verdict()
    out: list[Decision] = []
    for _, row in cls.iterrows():
        dom, h = str(row["domain"]), int(row["horizon"])
        informative = str(row["classification"]) == "informative"
        if (dom, h) in failures:
            out.append(Decision(dom, "erc_pct", h, UNCALIBRATED, failures[(dom, h)]))
            continue
        if realtime is not None and not realtime["realtime_valid"]:
            out.append(Decision(dom, "erc_pct", h, UNCALIBRATED, str(realtime["reason"])))
            continue
        if informative:
            reason = (
                f"PID interval is narrower than the historical range on the "
                f"training record: width ratio {row['ratio']:.3f} "
                f"[{row['ratio_lo']:.3f}, {row['ratio_hi']:.3f}]"
            )
            out.append(Decision(dom, "erc_pct", h, INTERVAL, reason))
        else:
            reason = (
                f"the forecast interval is no narrower than the historical "
                f"range: width ratio {row['ratio']:.3f} "
                f"[{row['ratio_lo']:.3f}, {row['ratio_hi']:.3f}], so the "
                f"historical week-of-year range is shown instead"
            )
            out.append(Decision(dom, "erc_pct", h, HISTORICAL_RANGE, reason))
    return out


def probabilistic_decisions() -> list[Decision]:
    """One decision per domain and probabilistic target.

    A target renders per cell only if it passed the look-3 reliability
    criterion and has resolution to offer. Otherwise a historical rate,
    identical across cells, with the reason stated.
    """
    path = LOOK3 / "reliability.csv"
    if not path.exists():
        return []
    rel = pd.read_csv(path)
    bad_rel = _reliability_failures()
    flat = _zero_resolution()
    survivors = _survivor_set()

    out: list[Decision] = []
    for _, row in rel.iterrows():
        dom, target, h = str(row["domain"]), str(row["target"]), int(row["horizon"])
        key = (dom, target)
        if key in bad_rel:
            out.append(
                Decision(
                    dom, target, h, BASE_RATE,
                    f"stated probabilities did not match observed frequencies on "
                    f"the 2026 holdout: reliability {bad_rel[key]:.4f}, needed "
                    f"{RELIABILITY_MAX} or less, so {shown_instead(target)}",
                )
            )
            continue
        if key in flat:
            out.append(
                Decision(
                    dom, target, h, BASE_RATE,
                    f"the forecast does not separate events from non-events: "
                    f"resolution {flat[key]:.6f}, so every cell would show the "
                    f"same number, so {shown_instead(target)}",
                )
            )
            continue
        beats = key in survivors or (dom, target) in survivors
        reason = (
            "calibrated on the 2026 holdout and beats its baseline on 2022 to "
            "2023 validation"
            if beats
            else "calibrated on the 2026 holdout; it does not beat its baseline, "
            "so it is shown as a probability with its historical basis and no "
            "claim of skill"
        )
        out.append(Decision(dom, target, h, "probability", reason))
    return out


V11 = ART / "v11" / "survivors_v11.csv"


def _survivor_set() -> set[tuple[str, str]]:
    """Current survivors, as (domain, target) pairs.

    Read from the leak-free five-domain test. This previously read the
    original stage 1 table, which still lists Pueblo d_ge2_h4, withdrawn by
    the leak-free refit, so the app told users that pair beat its baseline.
    """
    if not V11.exists():
        return set()
    m = pd.read_csv(V11)
    s = m[m["survivor"].astype(bool)]
    return {(str(r["domain"]), str(r["target"])) for _, r in s.iterrows()}


def new_domain_decisions() -> list[Decision]:
    """Rendering for the v1.1 domains, decided on 2022 to 2023 validation.

    These domains have no 2026 evaluation and never will under the seal, so
    the look-3 reliability threshold is applied to validation instead
    (docs/DECISIONS.md, v1.1 Stage 5). The continuous forecast draws no band,
    as everywhere.
    """
    from cofire.model.targets import HORIZONS, target_names
    from cofire.ship import domains

    if not V11.exists():
        return []
    tab = pd.read_csv(V11)
    out: list[Decision] = []
    for dom in domains.NEW:
        for h in HORIZONS:
            out.append(Decision(
                dom, "erc_pct", h, UNCALIBRATED,
                "No interval method passes the delayed-feedback check, so no band is drawn. "
                "The point forecast is shown with the historical range for the week.",
            ))
        t = tab[tab["domain"] == dom].set_index("target")
        for target in target_names(HORIZONS):
            h = int(target.rsplit("_h", 1)[1])
            if target not in t.index:
                out.append(Decision(
                    dom, target, h, BASE_RATE,
                    "the event did not happen in this area in 2022 or 2023, so a per-cell "
                    f"probability cannot be checked; {shown_instead(target)}",
                ))
                continue
            r = t.loc[target]
            if str(r["render"]) == "probability":
                reason = (
                    f"calibrated on 2022 to 2023 validation (reliability "
                    f"{float(r['reliability_cell']):.4f}) and beats its baseline there"
                    if bool(r["survivor"])
                    else f"calibrated on 2022 to 2023 validation (reliability "
                    f"{float(r['reliability_cell']):.4f}); it does not beat its baseline, so it "
                    f"is shown as a probability with no claim of skill"
                )
                out.append(Decision(dom, target, h, "probability", reason))
            elif not bool(r["estimable"]):
                out.append(Decision(
                    dom, target, h, BASE_RATE,
                    f"only {int(r['n_positive_weeks'])} weeks with the event in 2022 to 2023 "
                    f"validation, fewer than the 12 needed to check a per-cell probability; "
                    f"{shown_instead(target)}",
                ))
            else:
                out.append(Decision(
                    dom, target, h, BASE_RATE,
                    f"stated probabilities did not match observed frequencies in 2022 to 2023 "
                    f"validation: reliability {float(r['reliability_cell']):.4f}, needed "
                    f"{RELIABILITY_MAX} or less, so {shown_instead(target)}",
                ))
    return out


def all_decisions() -> pd.DataFrame:
    rows = [
        {
            "domain": d.domain, "target": d.target, "horizon": d.horizon,
            "state": d.state, "reason": d.reason,
        }
        for d in continuous_decisions() + probabilistic_decisions() + new_domain_decisions()
    ]
    return pd.DataFrame(rows).sort_values(["domain", "target", "horizon"])


def write(out_dir: Path = ART / "ship") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "rendering.csv"
    frame = all_decisions()
    frame.to_csv(path, index=False)
    LOGGER.info(
        "%d rendering decisions: %s",
        len(frame), frame["state"].value_counts().to_dict(),
    )
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write())
