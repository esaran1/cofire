"""Three-state uncertainty status, computed from calibration diagnostics.

Not a hand-set flag: the state follows from where the current issue's regime sits
relative to the calibration pool's regime range, and from whether the pool's
measured coverage supports an interval at all.

  calibrated     current conditions fall inside the pool's regime range
  extrapolating  conditions exceed the pool's range; interval shown with a caveat
                 and widened by the pre-registered rescaling
  uncalibrated   diagnostics say coverage cannot be supported; the interval is
                 suppressed and only the point forecast + Why drivers are shown

See docs/PREREGISTRATION_CALIBRATION.md and artifacts/uncertainty/multiregime.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np

Status = Literal["calibrated", "extrapolating", "uncalibrated"]

# Coverage below this on the pool's own diagnostics means an interval would be
# misleading, so it is suppressed rather than shown. Set from the v0.5/v0.6
# evidence: LODO coverage of ~0.5 is not an interval anyone should act on.
UNCALIBRATED_COVERAGE = 0.60
# How far past the pool's regime range still counts as "extrapolating" rather
# than hopeless. Expressed in pool standard deviations of the regime covariate.
EXTRAPOLATION_LIMIT_SD = 2.0


@dataclass
class PoolRegime:
    """Regime range of the calibration pool, in USDM-category units."""

    usdm_min: float
    usdm_max: float
    usdm_mean: float
    usdm_sd: float
    pool_years: list[int]
    measured_coverage: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class RegimePosition:
    status: Status
    current_usdm: float
    pool_usdm_max: float
    exceedance_sd: float
    widen_factor: float
    measured_coverage: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify(current_usdm: float, pool: PoolRegime, *, rescale_clip: tuple[float, float] = (0.5, 3.0)) -> RegimePosition:
    """Place the current issue against the pool and pick a status.

    The order matters: a pool whose own measured coverage is too low cannot
    support an interval even for conditions inside its range, so that check comes
    first.
    """
    sd = pool.usdm_sd if pool.usdm_sd > 1e-6 else 1.0
    exceed = max(0.0, float(current_usdm) - pool.usdm_max)
    exceed_sd = exceed / sd

    if pool.measured_coverage < UNCALIBRATED_COVERAGE:
        return RegimePosition(
            status="uncalibrated",
            current_usdm=float(current_usdm),
            pool_usdm_max=pool.usdm_max,
            exceedance_sd=exceed_sd,
            widen_factor=1.0,
            measured_coverage=pool.measured_coverage,
            reason=(
                f"calibration pool coverage is {pool.measured_coverage:.2f} against a 0.90 target, "
                f"below the {UNCALIBRATED_COVERAGE:.2f} floor; an interval here would overstate "
                "what the record supports"
            ),
        )

    if exceed <= 0:
        return RegimePosition(
            status="calibrated",
            current_usdm=float(current_usdm),
            pool_usdm_max=pool.usdm_max,
            exceedance_sd=0.0,
            widen_factor=1.0,
            measured_coverage=pool.measured_coverage,
            reason=(
                f"current drought severity {current_usdm:.2f} is inside the calibration pool range "
                f"[{pool.usdm_min:.2f}, {pool.usdm_max:.2f}]"
            ),
        )

    if exceed_sd > EXTRAPOLATION_LIMIT_SD:
        return RegimePosition(
            status="uncalibrated",
            current_usdm=float(current_usdm),
            pool_usdm_max=pool.usdm_max,
            exceedance_sd=exceed_sd,
            widen_factor=1.0,
            measured_coverage=pool.measured_coverage,
            reason=(
                f"current drought severity {current_usdm:.2f} exceeds the pool maximum "
                f"{pool.usdm_max:.2f} by {exceed_sd:.1f} pool SD, past the "
                f"{EXTRAPOLATION_LIMIT_SD:.0f} SD limit; no year in the record resembles it"
            ),
        )

    # Pre-registered variant (d) rescaling, reused as the widening factor.
    widen = float(np.clip(1.0 + exceed_sd, *rescale_clip))
    return RegimePosition(
        status="extrapolating",
        current_usdm=float(current_usdm),
        pool_usdm_max=pool.usdm_max,
        exceedance_sd=exceed_sd,
        widen_factor=widen,
        measured_coverage=pool.measured_coverage,
        reason=(
            f"current drought severity {current_usdm:.2f} exceeds the calibration pool maximum "
            f"{pool.usdm_max:.2f} by {exceed_sd:.1f} pool SD; interval widened {widen:.2f}x and "
            "shown with a caveat"
        ),
    )


def pool_from_artifacts(artifacts_dir: Path) -> PoolRegime | None:
    """Read the adopted pool's regime range from the multiregime artifacts."""
    path = artifacts_dir / "uncertainty" / "regime_pool.json"
    if not path.exists():
        return None
    blob = json.loads(path.read_text())
    return PoolRegime(
        usdm_min=float(blob["usdm_min"]),
        usdm_max=float(blob["usdm_max"]),
        usdm_mean=float(blob["usdm_mean"]),
        usdm_sd=float(blob["usdm_sd"]),
        pool_years=[int(y) for y in blob.get("pool_years", [])],
        measured_coverage=float(blob["measured_coverage"]),
    )


def write_pool(pool: PoolRegime, artifacts_dir: Path) -> Path:
    out = artifacts_dir / "uncertainty" / "regime_pool.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pool.to_dict(), indent=2))
    return out
