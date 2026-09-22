# STATUS: merged to main, v1 complete

Branch `v1-research`. Holdout 2026 **looked at 3 times**, the third under the preregistration below.
The counter is keyed on the holdout year in `cofire/model/freeze.py`. No
further look is authorised.

## Where the work stands

| stage | result |
|---|---|
| A, PID coverage | all five preregistered criteria pass, both domains, three horizons |
| B, width ratio | 4 of 6 informative: Larimer h2, Pueblo h2, h4, h8 |
| 1, multiplicity | 51 comparisons, 39 estimable, **12 survivors** |
| 2, SubX | run once, **0 targets switch**; everything ships on configuration A |
| 3, freeze | preregistration recorded, config hash fixed |
| 4, look 3 | 69 of 84 criteria pass: **30 of 30 interval**, 39 of 54 reliability |
| 5, artifacts | 34656 rows, 38 issues to 2026-09-22, rendering stored per target |
| 6, product | every figure from artifacts, contamination-era content removed |
| 7, verification | all checks green, clone to running 201s, 20 screenshots |
| 8, merge | `daee4a8`, pushed to origin/main |

## The rule that governs every skill claim

A skill claim is the **paired difference between the statistic on real targets
and on targets shuffled within the same circular blocks**, bootstrapped jointly,
CI above zero. A raw skill-score interval does not establish skill, because two
models that are both functions of the same input differ in Brier on shuffled
labels through probability spread alone.

Applied to the fire results, this removes five of the seven targets that passed
an unpaired interval, which are exactly the five whose ad-hoc shuffled control
had already reproduced the effect.

## Configuration

Train 2007-01-01 to 2021-12-31, validate 2022 to 2023, calibrate 2024 to 2025,
holdout 2026. Drought targets Markov 18 of 18, fire exceedance targets
damped-persistence logistic 9 of 9, continuous `erc_pct` damped regression,
intervals from the reference conformal PID. No forecast weather: SubX did not
qualify.

## Pre-registration

`docs/PREREGISTRATION_LOOK3.md`. Supersedes
`f9b3212c2454bb1afec2c67b084f60bf0ac1d471c29bde13f30385277807b584` and every
earlier one; no look was taken under any of them.

The config hash now covers every file under `cofire/model/` plus every fitted
artifact the shipped path loads and its fit-window sidecar. The previous hash
covered a handful of hyperparameters and would not have moved if every line of
model code had changed.

## Two seal defects found and closed

1. **The look counter was keyed on the config hash.** Changing the
   configuration reset it to zero, which would have handed back a fresh set of
   looks at data already seen twice. It is now keyed on the holdout year, and
   the two looks already taken are carried forward.
2. **Stages A and B ran from scratch scripts**, so the numbers in the
   preregistration came from code the hash did not cover. Both are now in
   `cofire/model/calibration_stages.py`. Promoting Stage A corrected a stream
   that ran backwards in time; every conclusion held and the worst miss run
   improved from 31 to 14.

## Look 3 results

All thirty interval criteria pass on the sealed year. PID long-run coverage
0.8975 to 0.8996, minimum rolling 13-week coverage 0.8944 to 0.8986 against a
floor of 0.70, all twelve conditional strata within 0.0164 of 0.90, longest miss
run 6 to 12 against a bound of 60. ACI reaches a rolling minimum of 0.6140 with
a 264-week miss run on the same rows.

Reliability passes 39 of 54 at the 0.05 threshold, and 9 of the 12 stage-1
survivors. The failures concentrate at long horizons exactly as the recorded
expectation said: mean reliability 0.0126 at h2, 0.0386 at h4, 0.0775 at h8, and
13 of 15 failures at h4 or h8. Every h2 target passes on both domains.

Width ratios on 2026 are 0.568 to 0.757, better than validation's 0.922 to
1.006. By the rule fixed before the look this changes no rendering.

## Rendering, per target and horizon

Fixed in the preregistration before look 3, applied mechanically from artifacts.

| county | h2 | h4 | h8 |
|---|---|---|---|
| larimer | interval | historical range | historical range |
| pueblo | interval | interval | interval |

Probabilistic targets: 30 render as per-cell probabilities, 24 as a regional
base rate identical across cells, being the 15 that failed the look-3
reliability criterion plus 9 with no resolution to offer. No horizon failed a
PID test, so nothing renders `uncalibrated`; the path exists and is exercised by
the rule.

## What ships

`cofire/model/` is frozen at `46c17ae` and `tests/test_frozen_model.py` holds it
there. `cofire/ship/` reads the frozen model and fits nothing. Any further work
on the model requires a new preregistration; the current one is spent.
