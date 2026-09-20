# Pre-registration: multi-regime calibration pool

**Frozen before any variant was run.** Written in the v0.6 session, after the subset move and before
the first calibration experiment. Nothing in this experiment evaluates on 2026; the hindcast stays
sealed at 2 looks.

The v0.5 finding this responds to: after fixing the two ACI defects, LODO coverage reached only
0.51–0.67 against a 0.90 target, because test-year |residuals| run ~2.5x calibration-year at p90 and
a **single-year** calibration pool cannot cover a harder year. Static split conformal with no ACI at
all gave 0.348 on LODO 2020. This experiment asks whether a pool built from multiple regimes closes
that gap.

## Variants to be tested

Exactly these four, plus the v0.5 baseline. The list is closed: **no variant may be added after
results are seen.** A new idea gets logged in DECISIONS.md as a future experiment.

| id | name | construction |
| --- | --- | --- |
| **base** | single-year (v0.5 baseline) | residual pool from the most recent non-fold year only |
| **a** | all-years pooled | residuals from every non-fold, non-2026 year, pooled with equal weight |
| **b** | severity-stratified | all non-fold years, each year's residuals weighted by that year's mean USDM category, normalised to mean weight 1 |
| **c** | nearest-regime (k most similar years) | the k non-fold years closest to the target year by the similarity metric below; **k = 2 and k = 3**, both reported |
| **d** | residual rescaling by regime covariate | all-years pool, with each residual multiplied by `ratio = sigma_hat(target regime) / sigma_hat(pool regime)`, where `sigma_hat` is a linear fit of |residual| on the regime covariate estimated **on the pool only** |

### Covariates, named up front

The **regime covariate** for variants (b), (c) and (d) is the pair:

- `usdm` — domain-mean USDM category over the year (drought severity)
- `spi_90` — domain-mean 90-day standardised precipitation index (antecedent precipitation)

The **similarity metric** for variant (c) is Euclidean distance in the 2-dimensional space of
(domain-mean `usdm`, domain-mean `spi_90`), each standardised to zero mean and unit variance across
the available non-fold years. k values: **2 and 3**.

For variant (d), `sigma_hat` is fit as `|residual| ~ b0 + b1 * usdm_mean` by ordinary least squares
over the pool years, and the ratio is clipped to `[0.5, 3.0]` to keep a degenerate fit from producing
absurd intervals. The clip bound is fixed here, in advance.

## Evaluation

- **Folds**: LODO only (2020, 2021, 2024, 2025). No 2026, no validation-split tuning.
- **Domains**: Pueblo (the new dev subset) and Larimer, reported separately, so the domain change is
  not confounded with the method change.
- **Target coverage**: 0.90 nominal.
- **Strata**: overall, by USDM category (0–4), and by month.
- **Also reported**: mean interval width at every stratum.
- **Horizons**: 2, 4, 8 weeks. The headline horizon is h=4 on the ERC-percentile target.

## Width constraint

Coverage bought with useless intervals is a failure. The ERC percentile is bounded on [0, 100], so an
interval of width 100 carries no information at all.

**Maximum acceptable mean width: 1.5x the v0.5 baseline** at the same fold and horizon. The v0.5
LODO baseline mean width is ~65 ERC-percentile points at h=4, so the cap is **~98 points**. Any
variant whose mean width exceeds the cap is recorded as **failed on width**, whatever its coverage.

## Acceptance criterion and decision rule

Stated numerically, before results:

- **Adopt** a variant if, on the Pueblo domain at h=4, it achieves mean LODO coverage **>= 0.85**
  *and* worst-fold coverage **>= 0.80**, *and* mean width **<= 1.5x baseline**.
- **Provisionally adopt** if mean coverage is **>= 0.80** and improves on the baseline by **>= 0.15**
  absolute, with width within the cap. Ships with the `extrapolating` status wired (section 4) rather
  than as a clean calibration claim.
- **Reject** otherwise, including any variant that meets coverage only by breaching the width cap.

If several variants qualify, the tie-break is **smallest mean width**, then simplest construction in
the order base < a < b < c < d.

**Expected outcome, recorded in advance:** no pool built from 2018–2025 contains a 2026 analog (the
driest available year is mean USDM 0.916 against 2026's 2.231). The most likely true result is that
pooling improves coverage materially but does **not** reach 0.90 on the hardest fold. If that is what
happens, it is reported as the finding and the residual gap is quantified. **No tuning toward 0.90.**

## Reporting commitment

**Every variant on the list will be reported, including those that fail**, with coverage and width at
every stratum, in `artifacts/uncertainty/multiregime.md`. A variant that is rejected is shown with
its numbers, not omitted. Failure modes (over-wide intervals, under-coverage, degenerate fits) are
named explicitly.

## Relationship to the point-forecast pre-registration

`docs/PREREGISTRATION.md` governs the next 2026 look for the **point forecast** and its trigger
remains unmet. This document governs the **uncertainty layer** only. Nothing here authorises a 2026
look, and no result from this experiment may be used to justify one.
