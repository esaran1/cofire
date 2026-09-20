# Leakage diagnostic

One-hour audit, prompted by a sharp observation: under the original splits, 2024–2025 is **already
held out of training**, so "the model saw the year" cannot explain why calibration-year residuals
run ~2.5x training-year residuals. Either something leaks into the training window, or the v0.6
framing was imprecise.

**Verdict: no leak found on any of the three checks. The v0.6 framing was imprecise and is corrected
below.** The affected numbers do not change; their interpretation does.

## Check 1 — early stopping uses the validation split only

`LightGBMConditionModel._fit_one` passes `valid_sets=[dtrain, dvalid]` with
`lgb.early_stopping(20)`. The `valid` frame comes from `split_frames`, which is bounded by
`settings.valid_start .. valid_end`.

| split | window |
| --- | --- |
| train | <= 2022-12-31 |
| valid (early stopping) | 2023-01-01 .. 2023-12-31 |
| calibrate (conformal pool) | 2024-01-01 .. 2025-12-31 |
| hindcast | >= 2026-01-06 |

Programmatic check: `valid/calibrate overlap = False`. LODO and the multiregime runner both call
`model.fit(train, None)`, i.e. **no early-stopping set at all**, so no calibration year can influence
tree count there either. **Clean.**

## Check 2 — feature statistics are fit on the training window only

`fit_training_stats(frame, train_end)` filters `frame.loc[time <= train_end]` **before** any fitting,
and `build_feature_store` calls it with `train_end = settings.train_end` (2022-12-31). This covers
SPI/SPEI gamma parameters (per cell, per month), ERC/BI percentiles (per cell, per week-of-year) and
the fm100/fm1000/tmmx normalisation means and standard deviations.

Two empirical confirmations:

- No feature shows a missingness shift > 30 percentage points from train to calibrate (0 of 95).
- `erc_pct` spans **[20.0, 100.0] on train but [0.0, 100.0] on calibrate**. A percentile fit on the
  calibration data could not produce values below its own observed floor; values escaping the
  training range are exactly the signature of a *train-fitted* transform applied to later data.

**Clean.**

## Check 3 — no ConvLSTM sequence window straddles a split boundary

`frame_to_samples` builds `SEQ_LEN = 8` step windows over whatever frame it receives, and `train.py`
calls it on the already-split frames. Measured, per split:

| split | rows | time range | within bounds | tiles |
| --- | --- | --- | --- | --- |
| train | 112,752 | 2018-01-02 .. 2022-12-27 | yes | 253 |
| valid | 22,464 | 2023-01-03 .. 2023-12-26 | yes | 44 |
| calibrate | 45,360 | 2024-01-02 .. 2025-12-30 | yes | 97 |
| hindcast | 16,416 | 2026-01-06 .. 2026-09-22 | yes | 30 |

Because windows are constructed per split, the earliest input step of any sample is that split's own
first timestep. No calibration-year sample can contain a training-year step, or vice versa.
**Clean.**

Side effect worth recording (not a leak): the first 7 weeks of each split yield no labelled sample,
so the first usable label is ~7 weeks after each split boundary. That is a small, symmetric data
loss, not contamination.

## The finding, restated correctly

All three checks are clean, so the result stands as a **generalization** result. But the v0.6
sentence "residual magnitude tracks whether the model saw the year in training" was drawn from a
**LODO** model, where 2021/2024/2025 *are* in the fold's training set — so the 56.74 vs 22.71
comparison there really was held-out versus in-training. That is valid for LODO and invalid as a
general statement, because it does not describe the original splits.

Measured under the **original** splits (train <= 2022, early stopping on 2023, calibration unseen),
ERC h=4 absolute residuals:

| split | year | mean | p90 |
| --- | --- | --- | --- |
| train | 2018 | 11.60 | 20.59 |
| train | 2019 | 14.24 | 24.94 |
| train | 2020 | 13.57 | 25.06 |
| train | 2021 | 13.59 | 23.77 |
| train | 2022 | 13.42 | 26.38 |
| **valid** | **2023** | **32.71** | **59.16** |
| **calibrate** | **2024** | **32.06** | **60.59** |
| **calibrate** | **2025** | **33.01** | **62.66** |

The gap is **in-sample versus out-of-sample**, not seen-year versus unseen-year. It is ~2.4x at p90
and is strikingly uniform across three independent held-out years (59.16 / 60.59 / 62.66), which is
what a stable generalization gap looks like and is not what leakage looks like — a leak would make
the *calibration* residuals small, not large.

This also explains the v0.6 calibration null result more cleanly than the original wording did. The
conformal pool is built from calibration-year residuals (p90 ≈ 61), and those already reflect the
out-of-sample penalty; the problem is not that the pool is drawn from the wrong regime, it is that
**every** held-out year carries the same ~2.4x inflation, so no reweighting across pool years can
recover it. Pool construction cannot fix a gap that is constant across the pool.

## Corrections to make

- v0.5/v0.6 **numbers are unaffected** — nothing was computed with leaked data, so no re-report is
  required.
- The **wording** in DECISIONS.md, STATUS.md, `multiregime.md` and `docs/DESIGN.md` is corrected from
  "whether the model saw the year" to "in-sample versus out-of-sample", with the LODO-specific claim
  labelled as LODO-specific.

## Future work, logged not run

The difficulty-conditioned conformal score remains **future work** and was not started. The result
above sharpens its motivation: the conditioning variable should capture out-of-sample difficulty,
which is uniform across held-out years here, so a within-pool covariate is unlikely to help and an
explicit out-of-sample penalty term is the more promising direction.
