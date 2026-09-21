# STATUS: frozen, awaiting look 3

Branch `v1-research`. Holdout 2026 sealed at **2 looks**, counter keyed on the
holdout year in `cofire/model/freeze.py`.

## Where the work stands

| stage | result |
|---|---|
| A, PID coverage | all five preregistered criteria pass, both domains, three horizons |
| B, width ratio | 4 of 6 informative: Larimer h2, Pueblo h2, h4, h8 |
| 1, multiplicity | 51 comparisons, 39 estimable, **12 survivors** |
| 2, SubX | run once, **0 targets switch**; everything ships on configuration A |
| 3, freeze | preregistration recorded, config hash fixed |

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

## Resume point

Stage 3 complete. `FREEZE_COMMIT` is `425bdedbf13c3e7ea8e5910b84749c75b7bfad18`, recorded in
`artifacts/FREEZE_COMMIT`. Preregistration sha256 `33e0ee105eebd0517e08f73a4c7a5df4cfc5db444438cd7876da4fb01731cecc`. Next is
stage 4, look 3, which runs only if the four preconditions in the
preregistration verify in code.
