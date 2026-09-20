# Pre-registration for hindcast look 3

Written **before** the next look at the sealed 2026 holdout, as required by the v0.5 operating rules.
The 2026 hindcast currently stands at **2 looks** on config `0957e415fa7f3fad`. Nothing in the v0.5
session evaluated on 2026; every number that informed this document came from the 2018-2025 feature
store, the 2022-2023 validation split, LODO folds, or synthetic streams.

This document is the contract. If the run below happens, it is **look 3**, it is reported as look 3,
and no iteration follows it.

## Status: NOT YET AUTHORISED TO RUN

Look 3 is **not** taken in this session. The pre-conditions in "Trigger" below are not all met. This
document exists so that whoever takes look 3 is bound by choices made before seeing the answer.

## Why a re-specification needs a new look

The delta parameterisation changes the target, so the existing 2026 numbers do not describe it. The
level-parameterised results from looks 1-2 remain valid for the level model and are unaffected by
anything registered here.

## Frozen configuration

| item | value |
| --- | --- |
| config hash (level, looks 1-2) | `0957e415fa7f3fad` |
| parameterisation | **delta** (`y = target(t+h) - target(t)`), reconstructed to level by adding back `target(t)` |
| reconstruction clipping | USDM to [0, 4], ERC percentile to [0, 100]; clip-binding rate reported |
| model arm | **LightGBM** (least-bad arm on both validation and LODO; the PI-ConvLSTM was worse on both targets and its three penalty configs were within 0.01 ERC MAE of each other) |
| ACI learning rate | **0.01**, unchanged |
| conformal | target 0.90; `qhat` fit on the calibrate split only; ACI online with the corrected miss-rate target |
| sample weighting | **uniform** (`power = 0.0`) |
| seed | `SEED` from `cofire.model.config`, unchanged |
| horizons | 2, 4, 8 weeks |
| domain | Larimer (`COFIRE_DEV_SUBSET=1`) unless the subset move lands first, in which case the new subset is recorded here before the run |

Rationale for the choices that were genuinely open:

- **ACI lr stays at 0.01.** The sweep {0.01, 0.05, 0.1, 0.25} on synthetic step changes showed no
  learning rate recovers coverage under severe shift (alpha saturates at its floor in every case),
  and 0.25 is actively worse. There is no evidence for changing it, so it does not change.
- **Weighting stays uniform.** Inverse-frequency weighting is implemented
  (`lodo.severe_week_weights`) but was not shown to help on LODO, so shipping it would be an
  unjustified degree of freedom.
- **LightGBM, not the ensemble.** The ensemble was the v0.3 shipping arm on validation ERC MAE, but
  LightGBM was the least-bad arm on the 2026 level hindcast and is the arm the delta work was
  developed on.

## Metrics to be reported

Exactly these, for both targets at h = 2, 4, 8:

1. Level MAE of the reconstructed forecast, and persistence MAE on the same rows.
2. Skill versus persistence, `1 - MAE_model / MAE_persistence`, with week-block bootstrap CIs.
3. Delta MAE against the zero predictor (persistence in delta space).
4. Clip-binding rate for the reconstruction.
5. Conformal and bootstrap coverage and mean width at the 0.90 target, overall and by USDM stratum.
6. `look_index` from `run_log.json`, stated in every table caption.

No other metric may be introduced after the run to make the result look better.

## Decision rule, fixed in advance

Applied to the **ERC-percentile** target, which is the product's headline, at **h = 4**:

- **Go** — skill versus persistence is positive at h=4 **and** h=8, with the lower CI bound above 0
  at h=4, **and** conformal coverage is within 5 points of 0.90.
- **Partial** — skill is positive at h=4 with a CI that includes 0, **or** skill is positive at only
  one of the two horizons, **and** coverage is within 10 points of 0.90.
- **No-go** — anything else, including any case where persistence wins at both h=4 and h=8.

Drought (USDM) is reported but does not gate the verdict, because the 2023 validation split is
99.4% D0 and cannot discriminate.

## What is forbidden after look 3

- Retuning any hyperparameter, the ACI learning rate, the weighting scheme, or the conformal target.
- Switching the reported arm or parameterisation.
- Adding, dropping, or redefining a metric.
- Taking look 4 on this config.

A scoring-only bugfix is permitted, but it increments `look_index`, and every affected number is
re-reported as **contaminated**, exactly as the `merge_pred` fix was in v0.3.

## Trigger

Look 3 runs only when **all** of the following hold, and not before:

1. The delta parameterisation closes the persistence gap on validation **and** on LODO — that is,
   positive mean skill on the ERC target at h=4 across folds. As of this writing it does **not**:
   delta improves on level at every fold and horizon tested, but both remain negative.
2. The user explicitly authorises the look.
3. This document is updated with the final config hash for the delta specification and committed
   before the run.

Condition 1 is currently unmet, which is why this session stops at the pre-registration rather than
taking the look.
