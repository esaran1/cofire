# STATUS: merged to main, v1.1 adds Denver (CO-01) and its source watersheds

## Correction, 2026-09-27: a missing drought map read as "no drought"

**The app's latest issue, 2026-09-22, showed no drought anywhere.** That
week's USDM map was not in the archive, and the frozen rasterizer fills a
missing week with category 0 without an error. The export therefore issued
22 September forecasts from USDM 0 in every cell of every domain (Larimer and
Pueblo since the export was built, Denver and its watersheds from v1.1 Stage
6), where the 15 September map had Larimer at a mean category of 2.4, Pueblo
2.0, Denver 2.6 and Dillon 3.7. The drought odds shown for that issue started
from a false "none". Larimer and
Pueblo's ERC for the same week was also a three-day mean, because their daily
record ended on the 18th. The export now emits an issue only when its USDM
map is in the archive and all seven ERC days are present, stamps every issue
with the time its inputs were published, and tests for the fault
(`tests/test_rendering.py`). The latest issue is 2026-09-15 until Larimer and
Pueblo's 2026 ERC is resolved (below).

**The same fault reached look 3.** Look 3 ran on 21 September, before the 22
September map existed (released 24 September). Its frame ran through
2026-09-22, so the drought labels for target week 2026-09-22 were coded "no
drought", and the ERC labels for that week were three-day means. That is one
target week per horizon: issues of 8 September at 2 weeks, 25 August at 4 and
28 July at 8. The size and direction of the effect on the look-3 reliability
and interval results cannot be measured without scoring 2026 again, which the
seal forbids, so they are not recomputed. The interval results are already
void; the probability results carry this caveat. The look count stays 3.

**Open, 2026-09-27: one USDM week missing from the 2007 to 2025 record.** An
audit of all 992 weeks (`artifacts/audit/usdm_missing_weeks.json`) found one
map missing and none unreadable: 2022-12-27, in validation. The server has it
(HTTP 200, 1,800,699 bytes); the local 2022 archive holds 51 weeks without it,
so the frozen rasterizer coded that week "none" in every domain's store. It is
false for Pueblo (mean category 1.23 before, 1.19 after) and cannot be ruled
out for Larimer (0.59 before, 0 after) or Denver (0.23 before, 0 after); the
Upper South Platte and Dillon read 0 on both sides. Training, calibration, the
fold choices and look 3 do not touch it. The validation survivor tests and the
new domains' validation reliability do: drought targets only, at most one
issue week and one label week per horizon out of 104. Nothing is refit until
that is decided. The export now refuses any published week without its map,
not only the newest.

**gridMET revised its 2026 file after the stores were built.** Re-reading
Larimer and Pueblo's 2026 ERC through the reconciled path disagrees with the
stored copy on 203 and 184 of 261 days since late February, by up to 20 ERC
units. The same path reproduces June 2025 exactly (14,880 cell-days,
max|diff| 0), so the difference is the server's revision, not the fetch. The
refresh gate refused the revised record, and both counties stay on their
stored, reconciled 2026 data until adopting the revision is decided
(`COFIRE_REGATE=1`). Record in `docs/DECISIONS.md`, v1.1 Stage 7.

## Correction, 2026-09-26: interval results void, no forecast band shown

The look-3 interval tests (30 of 30 passed) used same-week updates a real-time
forecaster cannot make (`ahead=1` over a week-then-cell stream). With the honest
lag the PID controller is unstable on 2022 to 2025, worst 13-week coverage down
to 0.27, and the radius the export had applied covers 43 to 72%. Per the
pre-registered consequence of a failed interval test, all six continuous
horizons now render `uncalibrated`. Full record: [`docs/CORRECTION_LOOK3.md`](docs/CORRECTION_LOOK3.md), beside the unedited pre-registration; follow-up sweep: [`docs/LEAK_SWEEP.md`](docs/LEAK_SWEEP.md);
reproducible audit: `cofire/ship/pid_audit.py`. Probability results and the 12
skill survivors are unaffected.

Also fixed in the same audit: base-rate targets showed the average of a year of
model predictions (64% for Larimer D2-or-worse on 22 September) instead of the
training-record rate for the season (11%); the typical range used median plus
or minus half the width instead of real percentiles; `/forecast` without an
issue returned the oldest issue.

Branch `v1-research`. Holdout 2026 **looked at 3 times**, the third under the preregistration below.
The counter is keyed on the holdout year in `cofire/model/freeze.py`. No
further look is authorised.

**Holdout information reached a shipped artifact.** The forecast ranges the app
displayed for 2026 were a single radius per horizon, taken from the final state
of a PID run whose last labels were January and February 2026 outcomes, the
sealed year. No evaluation, test result or reported number was derived from
that radius; the look-3 figures come from `cofire/model/look3.py`, which was
run once and is unaffected. The artifact is withdrawn: the export no longer
computes it and the app draws no band. The values are retained only as a
historical record in `artifacts/audit/shown_radius.json`. The look count is
unchanged at 3: displaying a radius is not a look, because no one read 2026
outcomes to learn anything from it. Details: [`docs/LEAK_SWEEP.md`](docs/LEAK_SWEEP.md).

**Survivors after a leak-free refit: 11, not 12.** Refit outside the frozen
path with an h-week label embargo and per-fold `erc_pct`, the stage 1 test
keeps 11 of the 12 survivors. Pueblo `d_ge2_h4` falls (lower bound +0.011 to
-0.002) and is no longer claimed. The fire conclusion is unchanged, and the
fire family choice is unchanged in all 9 targets. Record in
`docs/LEAK_SWEEP.md`; diagnostic in `cofire/ship/sensitivity.py`.

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
all 15 failures at h4 or h8 (5 and 10). Every h2 target passes on both domains; the worst h2 reliability is 0.0377.

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
