# Conformal collapse: diagnosis

**Verdict: bug, not distribution shift.** Two independent defects in `cofire/model/conformal.py`,
both pushing intervals narrower. Neither requires a shifted stream to fire. Diagnosed entirely on
stored artifacts and synthetic streams — **no new evaluation on 2026**; the hindcast stays sealed at
2 looks.

## The symptom

2026 hindcast, ERC h=4: coverage 0.485, mean width 67.10, against calibrate-split coverage 0.914 at
width 112.28. Under adaptive conformal, a miss should *widen* the interval. Width fell by 40%, which
is the opposite of what ACI does under shift. That inconsistency is what made this a bug hunt rather
than a shift story.

## Defect 1 — ACI update targets coverage where it needs the miss rate

`aci_update` computed `alpha + lr * (target - err)` with `target = COVERAGE_TARGET = 0.90` and
`err = 1` on a miss. Gibbs & Candès (2021) drive the realised *miss* rate to `alpha_target`, so the
update must use `alpha_target = 1 - coverage = 0.10`.

Consequence, from the stored run log:

- on a **hit**:  `alpha += 0.01 * (0.90 - 0) = +0.009`
- on a **miss**: `alpha += 0.01 * (0.90 - 1) = -0.001`

Hits move alpha 9x faster than misses. Setting `E[delta] = 0` gives `p_miss = 0.90`: the only
stationary point is a **90% miss rate**, i.e. 10% coverage. Alpha ratchets up, and since width was
tied to `1/alpha`, intervals shrink monotonically until almost everything misses.

Observed in `artifacts/predictions/ensemble_hindcast_intervals.parquet` — this is the smoking gun,
and it is a *time trend*, not a drought response:

| issue | mean alpha | mean width | weekly coverage |
| --- | --- | --- | --- |
| 2026-01-06 | 0.100 | 112.28 | 1.000 |
| 2026-02-24 | 0.154 | 73.20 | — |
| 2026-08-25 | 0.232 | 48.53 | — |
| final 6 weeks | 0.231 | 48.71 | 0.452, 0.015, 0.0, 0.0, 0.0, 0.0 |

Coverage decays to exactly zero. A drought regime does not drive coverage to 0.000; a runaway alpha
does.

**Proof it is not shift.** On a *stationary* synthetic stream with no shift whatsoever and a
correctly-specified qhat, the old code converges to **0.260** coverage; with the miss-rate target it
holds **0.890**. The bug fires on any stream.

This also explains why the calibrate split looked healthy at 0.914: `calibrate.py` calls
`attach_intervals(..., update_aci=False)`, so the broken update never ran there. Only the hindcast
path passes `update_aci=True`. The two splits were not running the same code.

## Defect 2 — frozen qhat rescaled linearly instead of re-quantiled

`interval()` took the qhat frozen at the 0.90 level and multiplied by `(0.10 / alpha)`. That linear
proxy is not the quantile ratio. Under Gaussian residuals:

| alpha | true q(1-a)/q(0.90) | linear proxy | error |
| --- | --- | --- | --- |
| 0.05 | 1.192 | 2.000 | +68% |
| 0.20 | 0.779 | 0.500 | −36% |
| 0.30 | 0.630 | 0.333 | −47% |
| 0.50 | 0.410 | 0.200 | −51% |

Once defect 1 drove alpha up, defect 2 shrank the interval roughly twice as fast as the quantile
math warrants. The two compound.

## Fixes

1. `aci_update` uses `alpha_target = 1 - target`. Call sites unchanged (they still pass the coverage
   target), so no caller had to change.
2. `CellState` stores the sorted `|residual|` pool from the calibrate split; `interval()` calls
   `qhat_at(alpha)` to re-quantile at the current alpha. The pool is fit on calibrate only and is
   never refit on a holdout, so the split-conformal guarantee is preserved.

Post-fix on synthetic streams: stationary coverage **0.885** (target 0.90), and under an injected
step change width **grows** (3.30 → 5.02) instead of shrinking.

## The learning rate is *not* the problem

The pre-registered follow-up hypothesis — "ACI lr=0.01 may be too slow for weekly steps" — is
**refuted**. Sweeping {0.01, 0.05, 0.1, 0.25} against an injected step change:

| lr | severe shift x4 post-coverage | steps to recover | mild shift x1.5 post-coverage | steps to recover |
| --- | --- | --- | --- | --- |
| 0.01 | 0.453 | never | 0.867 | 19 |
| 0.05 | 0.427 | never | 0.833 | 12 |
| 0.10 | 0.427 | never | 0.827 | 39 |
| 0.25 | 0.407 | never | 0.760 | never |

Under a severe shift *no* learning rate recovers: alpha saturates at the 0.01 floor in every case.
The binding constraint is that re-quantiling a frozen calibration pool cannot produce an interval
wider than the largest residual that pool ever saw. Faster adaptation does not help, and lr=0.25 is
actively worse (it overshoots and oscillates). **Recommendation: keep lr=0.01.** If severe-shift
coverage matters, the fix is a wider//reweighted calibration pool or a scale-adaptive score, not a
larger learning rate.

## Bearing on the No-go

This repairs the *uncertainty* half of the v0.3 result. It does **not** change any point forecast:
`aci_update` and `interval()` touch interval width only, never `*_hat`. The persistence gap on
point MAE is untouched and is addressed separately by the delta parameterisation.

## LODO reproduction: the bug fires on in-sample years too

Section 1's premise holds. Running the same conformal path on held-out **2020** (an in-sample year,
no holdout budget spent) reproduces the collapse:

| h | coverage BEFORE fix | width | coverage AFTER fix | width |
| --- | --- | --- | --- | --- |
| 2 | 0.263 | 32.2 | 0.586 | 65.5 |
| 4 | 0.266 | 34.0 | 0.526 | 65.2 |
| 8 | 0.261 | 33.8 | 0.519 | 66.6 |

Coverage ~0.26 on a year that is *not* 2026 settles the question: the collapse was never a property
of the 2026 drought. The fix roughly doubles both coverage and width.

## But the fix does not get to 0.90 on real data — and that part is not a bug

After the fix, LODO 2020 coverage is 0.526 at h=4, still far from target. The synthetic streams
reach 0.885, so the remaining gap is data, not code. Residual magnitudes on the calibration year
versus the test year, h=4:

| | mean | p50 | p90 | max |
| --- | --- | --- | --- | --- |
| calibrate (2025) | 10.96 | 9.06 | 22.49 | 67.47 |
| test (2020) | 31.03 | 31.45 | 56.74 | 90.16 |

Test-year residuals are **2.52x** larger at p90. The decisive check: **static split conformal with
no ACI at all** gives test coverage **0.348**. A frozen calibration pool from an easier year cannot
cover a harder year, whatever the online update does afterwards.

So there are two distinct effects, and only the first is a defect:

1. **Bug (fixed).** Target inversion + linear rescale drove coverage to ~0.26 on *any* stream.
2. **Real limit (not fixed, not fixable by tuning).** Cross-year residual shift of ~2.5x means a
   single-year calibration pool is too narrow. This is why lr sweeps do not help: alpha saturates at
   its floor and the pool's own maximum becomes the binding constraint.

The honest remedy for (2) is a calibration pool that spans multiple regimes (pool residuals across
several years, or condition the score on drought category), not a faster learning rate. That is a
design change, pre-registered for a future session rather than applied here.
