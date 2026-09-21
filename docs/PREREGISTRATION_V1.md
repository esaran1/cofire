# Pre-registration: conformal PID against ACI (Phase 4)

Written before the first PID run. The sha256 of this file is recorded in
STATUS.md. If any decision below changes, the change is recorded as an
amendment with its own hash rather than by editing the original text, so that
what was predicted stays separable from what was found.

## The question

Does a conformal PID controller hold nominal coverage better than adaptive
conformal inference (ACI) on this data, and does it do so without paying for it
in interval width?

## Why this is worth asking

ACI is a pure integral controller on the miss rate: it moves `alpha` up when it
misses and down when it hits, and it has no term that responds to *how fast*
coverage is drifting. On a stream with slow regime change, which is what eight
years of Colorado drought is, an integrator alone tends to lag the drift and
then overshoot correcting it. A PID controller adds a proportional term, which
responds to the current error directly, and a scorecaster, which anticipates
where the score is heading. Angelopoulos, Candes and Tibshirani (2023) set out
the construction.

The honest prior is that PID does **not** help much here. The earlier
calibration work established that the held-out years carry a roughly uniform
2.4x residual inflation, and a controller cannot manufacture information about
a shift it has not yet observed. The expected result is that PID tracks
coverage slightly better during transitions and is otherwise indistinguishable.
That prediction is recorded here so that a null result is reported as a null
result rather than reframed after the fact.

## Arms

All six are run. None is dropped after seeing results.

1. `split` - split conformal, `qhat` frozen on the calibration split.
2. `aci` - adaptive conformal inference, learning rate 0.01, the existing
   implementation with its miss-rate target fix.
3. `pid_p` - proportional term only.
4. `pid_pi` - proportional plus integral.
5. `pid_full` - proportional, integral and scorecaster.
6. `cqr` - conformalised quantile regression, as a different family rather than
   a different controller.

## Fixed before running

- Target coverage: **0.90**. Not varied, not tuned.
- Domains: Larimer and Pueblo, reported separately, never pooled.
- Horizons: 2, 4 and 8 weeks.
- Evaluation window: the validation split only. The 2026 holdout is not touched
  in this session and the look counter stays at 2.
- Learning rates: ACI 0.01, as already committed. PID gains are set from the
  reference construction (`K_p = 0.1`, `K_i = 0.01`, integrator window 100
  steps) and are **not** searched. A gain search against the evaluation data
  would be tuning against the test.
- Seed: 2026.

## Primary endpoint

Absolute deviation of realised coverage from 0.90, computed per week and
averaged. Lower is better.

## Secondary endpoints

- Mean interval width, so that coverage bought by inflation is visible.
- Worst 8-week rolling coverage deviation, which is where a lagging controller
  shows up.
- Coverage during the transition weeks specifically, defined as weeks where the
  domain-mean USDM category changed, identified from the target series without
  reference to any model output.

## Decision rule, fixed in advance

PID is adopted over ACI only if **both** hold, on **both** domains:

1. Mean absolute coverage deviation improves by at least 0.01 in absolute
   terms, and
2. Mean interval width does not increase by more than 5%.

If PID improves coverage only by widening intervals, that is recorded as "no
improvement", because widening is available to any method for free.

If the two domains disagree, the result is reported as "domain dependent, not
adopted". Disagreement across domains is evidence of overfitting to one
geography, which is the specific failure this two-domain design exists to
catch.

## What would falsify the approach

If every controller, including plain split conformal, holds coverage within
0.01 of nominal, then the controllers are not doing anything and the honest
report is that adaptivity is unnecessary on this data. That outcome is
reportable and will be reported.

## Stopping rule

One run per arm per domain per horizon. No re-runs with adjusted gains. If a
run fails for a technical reason, the failure and its cause are recorded and
the run is repeated only after the technical fault is fixed, with that noted.
