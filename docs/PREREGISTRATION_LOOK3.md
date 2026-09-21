# Pre-registration: look 3 on the 2026 holdout

Recorded before the look. Everything below is fixed at the commit that carries
this file; the commit hash is `FREEZE_COMMIT`, and nothing under `cofire/model/`
changes after it.

**Supersedes** sha256 `f9b3212c2454bb1afec2c67b084f60bf0ac1d471c29bde13f30385277807b584`,
and through it `88d8fdf7...`, `341b68e7...`, `cabf75e1...`, `fdccb0f6...`,
`c06fbca2...`. No look was taken under any of them.

The holdout stands at **2 looks**. The counter now lives in
`cofire/model/freeze.py` and is keyed on the holdout **year**, not the
configuration. The previous counter was keyed on the config hash, which meant
any change to the configuration reset it to zero and silently handed back a
fresh set of looks at data that had already been seen twice. The seal belongs to
the year, whatever code does the looking.

## Configuration

**Config hash** sha256 `ed0c2079a5bc0eee1d0aa11869d3bc5eb0af671b9f30ee0c5114c3b9ca7be157`,
over every file under `cofire/model/` (path and contents, so a rename moves it)
plus every fitted artifact the shipped path loads and each one's fit-window
sidecar. The previous hash covered a handful of hyperparameters and would not
have moved if every line of model code had changed.

| layer | configuration |
|---|---|
| record | gridMET ERC 2007 to 2025, Larimer and Pueblo, 4000 m |
| split | train 2007-01-01 to 2021-12-31, validate 2022 to 2023, calibrate 2024 to 2025, holdout 2026 |
| drought targets | Markov transition baseline, 18 of 18 |
| fire exceedance targets | damped-persistence logistic, 9 of 9 |
| continuous `erc_pct` | damped regression at h2, h4, h8 |
| intervals | reference conformal PID, gains `LR=0.1, C_SAT=2.0, K_I=1.0, T_BURNIN=100` |
| forecast weather | none: SubX did not qualify |

`erc_pct` is the empirical percentile of a cell-week's ERC within that cell's
training pool over weeks of year within ±3 on a circular calendar, ties by
`kind="mean"`, computed by `cofire/model/erc_pct.py` and nowhere else.

## Preconditions, verified in code before the look

1. Working tree clean, and no file under `cofire/model/` differing from
   `FREEZE_COMMIT`. HEAD itself need not equal `FREEZE_COMMIT`: recording that
   commit's own hash creates a commit after it, as does any later work outside
   the model. What matters is that the model tree being run is the frozen one.
2. Recomputed config hash equals the hash above.
3. The fit-window loader runs in strict mode with no violations. Every fitted
   artifact declares `[fit_start, fit_end]` and a scope, and the loader raises
   rather than warns.
4. The look counter reads 2.

`cofire/model/freeze.py:freeze_conditions` reports each with its observed value.
If any fails, the look is not taken.

## The rule for any skill claim

A skill claim is the **paired difference between the statistic on real targets
and on targets shuffled within the same circular blocks**, bootstrapped jointly,
requiring the difference's CI above zero. A raw skill-score interval does not
establish skill: two models that are both functions of the same input differ in
Brier on shuffled labels through probability spread alone. This rule produced
the survivor set below and applies to anything claimed from the look.

## Reference values from the extended record

These are the values the 2026 results will be read against. They are validation
and calibration figures, not holdout figures.

**Stage A, reference PID coverage** (`artifacts/rerun_a/pid_coverage.csv`):

| domain | h | coverage | width | longest miss run | min rolling 13wk | D0-D1 | D2+ |
|---|---|---|---|---|---|---|---|
| larimer | 2 | 0.8985 | 63.90 | 11 | 0.8954 | 0.8988 | 0.8964 |
| larimer | 4 | 0.8987 | 66.58 | 11 | 0.8963 | 0.8974 | 0.9093 |
| larimer | 8 | 0.8991 | 68.76 | 11 | 0.8963 | 0.9008 | 0.8853 |
| pueblo | 2 | 0.8982 | 52.80 | 14 | 0.8944 | 0.8969 | 0.9074 |
| pueblo | 4 | 0.8978 | 55.77 | 12 | 0.8910 | 0.8969 | 0.9038 |
| pueblo | 8 | 0.8980 | 58.81 | 12 | 0.8917 | 0.8978 | 0.8992 |

Produced by `cofire/model/calibration_stages.py`, which is inside the config
hash. Stages A and B were first run from scratch scripts, so their numbers came
from code the hash did not cover; promoting them corrected one thing. The
original streamed the calibration split ahead of the validation split, warming
the controller on 2024 and 2025 before scoring it on 2022 and 2023. That is not
leakage, because the warm-up state is not fitted on the outcomes it is scored
against, but it runs backwards in time and a conformal controller is an online
method. Streaming in time order leaves every conclusion unchanged and improves
the worst miss run from 31 to 14.

ACI on the same rows reaches a rolling 13-week minimum of 0.4220 at Pueblo h8
with a 993-week miss run.

**Stage B, width-ratio classification** (`artifacts/rerun_a/classification.csv`),
ratio of mean PID width to the climatological ±3-week 5th-to-95th width:

| domain | h | ratio [CI] | classification |
|---|---|---|---|
| larimer | 2 | 0.970 [0.958, 0.982] | informative |
| larimer | 4 | 0.994 [0.978, 1.010] | climatological |
| larimer | 8 | 1.006 [0.987, 1.021] | climatological |
| pueblo | 2 | 0.922 [0.902, 0.941] | informative |
| pueblo | 4 | 0.943 [0.927, 0.959] | informative |
| pueblo | 8 | 0.977 [0.960, 0.993] | informative |

The shuffled control invalidates none: destroying the target moves every ratio
to 1.076 or worse, against 0.922 to 0.977 on real targets.

**Stage 1, survivors** (`artifacts/rerun_a/multiplicity.csv`). 51 comparisons,
39 estimable at the 12-positive-week floor, **12 survivors** under the paired
test, BH at q=0.10 across all targets and both domains, and Holm within each
event family:

| domain | target | h | paired difference [CI] |
|---|---|---|---|
| larimer | d_ge2 | 2 | +0.792 [+0.191, +1.141] |
| larimer | d_ge2 | 4 | +0.430 [+0.026, +0.806] |
| larimer | d_improve1 | 2 | +0.211 [+0.109, +0.338] |
| larimer | d_improve1 | 4 | +0.339 [+0.195, +0.528] |
| larimer | d_improve1 | 8 | +0.402 [+0.273, +0.607] |
| larimer | d_nochange | 2 | +0.158 [+0.057, +0.266] |
| larimer | d_nochange | 4 | +0.239 [+0.077, +0.397] |
| larimer | d_nochange | 8 | +0.324 [+0.174, +0.481] |
| pueblo | d_ge2 | 2 | +0.305 [+0.077, +0.515] |
| pueblo | d_ge2 | 4 | +0.219 [+0.011, +0.369] |
| pueblo | f_gt80 | 8 | +0.041 [+0.014, +0.062] |
| pueblo | f_gt90 | 8 | +0.025 [+0.004, +0.042] |

`f_gt97` is not estimable on either domain at h8, nor on Pueblo at any horizon:
6 to 9 positive weeks against a floor of 12.

**Stage 2, SubX** (`artifacts/rerun_a/subx_verdict.csv`). Run once. 51
comparisons, 39 estimable, **1** with a paired CI above zero in a single domain,
**0** switching to configuration B. Every target ships on configuration A.

## Confirmatory tests on 2026

Both domains, each horizon, on 2026 issues. Stated before the look.

### Interval calibration, per domain and horizon

| # | test | criterion |
|---|---|---|
| 1 | long-run PID coverage | reported for sanity only, no pass or fail |
| 2 | minimum rolling 13-week coverage | **≥ 0.70** |
| 3 | coverage conditional on D0-D1 and on D2+ | each **within 0.05 of 0.90**, i.e. in [0.85, 0.95] |
| 4 | longest miss run | **≤ 60 consecutive cell-weeks** |

Test 1 is sanity only because long-run coverage is close to guaranteed by the
controller's construction; it is the local tests that can fail. The miss-run
bound of 60 is set above the worst PID value observed on the extended record
(14, Pueblo h2) and far below ACI's (993).

### Reliability, per shipped probabilistic target

| # | test | criterion |
|---|---|---|
| 5 | Murphy reliability term | **≤ 0.05** |
| 6 | reliability diagram, 10 quantile bins | reported with the curve |

0.05 is above the worst reliability among the 12 survivors on validation
(0.0394, Pueblo `d_ge2_h4`) and below the range where a forecast's stated
probabilities stop matching observed frequencies. It is a test that can fail.

### Width ratio, per continuous horizon

| # | test | criterion |
|---|---|---|
| 7 | ratio of mean PID width to climatological width, with CI | reported with its CI |

## Product consequence of every outcome, decided now

Fixed before the look so that no result can be read into a rendering decision
after the fact.

| outcome | rendering |
|---|---|
| a horizon fails any of tests 2, 3 or 4 | that horizon renders with status `uncalibrated` and **no interval**; the reason string is stored in the export |
| a probabilistic target fails test 5 | it renders its **regional base rate**, visibly identical across cells, with the stated reason |
| the width ratio on 2026 | **reported, and changes nothing**: rendering stays as Stage B determined on the extended record |
| a target not among the 12 survivors | renders with no claim of skill; the probability and its historical basis only |
| a target not estimable | renders the regional base rate with the count of positive weeks as the reason |

Rendering per target and horizon, fixed by Stage B and unchanged by the look:

| domain | h | continuous `erc_pct` renders |
|---|---|---|
| larimer | 2 | point forecast plus PID interval |
| larimer | 4 | point forecast plus labelled historical week-of-year range |
| larimer | 8 | point forecast plus labelled historical week-of-year range |
| pueblo | 2 | point forecast plus PID interval |
| pueblo | 4 | point forecast plus PID interval |
| pueblo | 8 | point forecast plus PID interval |

## How the look is taken

One script, `cofire/model/look3.py`, invoked once with `COFIRE_ALLOW_LOOK=3`. It
verifies the four preconditions, computes exactly the tests above on 2026
issues, writes `artifacts/look3/`, and records the look. The counter must read 3
afterward.

It is not rerun for any reason, including a crash after results are written. If
it crashes before writing results, the traceback is reported and the work stops.

After the look, `tests/test_frozen_model.py` asserts that no file under
`cofire/model/` differs from `FREEZE_COMMIT`, and every later stage keeps that
test passing.

## Recorded expectation

Stated so the look can disconfirm something. The interval tests are expected to
pass: PID held 0.8978 to 0.8991 long-run and 0.8910 to 0.8963 on the worst
rolling window across six domain-horizon pairs, and its worst miss run was 14.
The reliability tests are less certain, because 2026 is a single year and the
drought targets' reliability rose with horizon on validation (0.0035 at h2 to
0.0354 at h8 on Larimer `d_improve1`); an h8 target failing at 0.05 would not be
surprising. The width ratio on 2026 is expected near the validation values, and
by rule it changes nothing either way.
