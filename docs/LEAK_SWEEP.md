# Leak sweep, 2026-09-26

After the look-3 interval results were voided for same-week feedback
(`docs/CORRECTION_LOOK3.md`), every place a statistic is updated sequentially,
warm-started, or pooled was checked for the same class of fault: use of
information not available at issue time. The standard applied is strict: an
observation may be used for a forecast issued in week w at horizon h only if its
outcome week is w - h or earlier.

Nothing under `cofire/model/` was edited. Faults there are reported here and
left as they are, because that tree is frozen at `FREEZE_COMMIT`.

## The delayed-feedback gate

`cofire/ship/leak_gate.py`, run in CI by `tests/test_delayed_feedback_gate.py`.
For each probe row it perturbs every score not observable at issue time,
including other cells in the same week, and fails if the method's output at the
probe moves. A toy method with a known answer demonstrates it: seeing the
previous row fails, an h-week delay passes, and a delay one row short fails.

Every sequential method in the repo, at h = 2 on a synthetic stream:

| method | result | mechanism |
|---|---|---|
| reference PID, `ahead=1` (as run for look 3) | leaks | updates on the previous row, another cell in the same week |
| reference PID, `ahead` = 2 weeks of rows | leaks | step size scaled by the range of the last 100 scores, ignoring `ahead` |
| reference PID, lagged, fixed step (diagnostic) | passes | the only change is turning the proportional step size off |
| in-house PID, P / PI / full | leaks | updates after every row; no lag option |
| ACI stream | leaks | updates after every row |
| split conformal stream | leaks | calibrates on the first 100 rows, then scores those same rows |
| per-cell ACI (`ConformalCalibrator`) | leaks | per-cell update each week, h - 1 weeks before the outcome is known |

None of these ships. The app draws no forecast band, and the CI test fails if a
band is rendered while no shipped method passes.

The reference implementation's step-size term is an upstream defect for
multi-step forecasting. It means the "real-time" run in `pid_audit.py` applied
the lag to the updates but not to the step size, so it was not fully causal
either. The look-3 conclusion does not depend on it: those results are void
because of `ahead=1`.

## The sweep

### SubX fold-wise climatology and `assert_no_self_contribution`: leaks

`fold_climatology` removes only the held-out year, so each fold's climatology
is built from every other year, including later ones. Validation issues in 2022
and 2023 get anomalies against a climatology that includes 2024 and 2025, and
configuration B's training anomalies (2018 to 2021) are centred on a climatology
that includes 2022 to 2025, the validation years. `assert_no_self_contribution`
checks only for the held-out year itself, so it passes.

Where: `cofire/model/data/subx.py`, `cofire/model/subx_arm.py`. Frozen; not
edited. Consequence: the leak favours configuration B, and the verdict was that
no target switches to B, so removing it could only strengthen that verdict.
Separately, B was calibrated on A's in-sample predictions, which biases against
B; the SubX comparison is therefore not clean in either direction, and it was
run once by rule.

### Platt calibrators and pooled out-of-fold construction: clean

Used only by the ablation, which does not ship. The calibrator is fit on pooled
out-of-fold predictions from training years and applied to validation, so no
validation information enters it, apart from the boundary label overlap below.

### Markov and damped-persistence fits, and their pooling across cells: leaks at boundaries

Pooling rows across cells and weeks at fit time is clean: the fit is done once
on the training split, before anything it is scored on. The leak is in the
labels. Targets are `shift(-h)` with no embargo, so the last h weeks of training
rows carry outcomes from after 2021-12-31, the start of the validation period:

| h | training rows with a label from after the split |
|---|---|
| 2 | 0.26% (960 Larimer, 864 Pueblo) |
| 4 | 0.51% (1,920 Larimer, 1,728 Pueblo) |
| 8 | 1.02% (3,840 Larimer, 3,456 Pueblo) |

The same happens at every leave-one-year-out boundary: for the 2020 fold at h8,
3,840 Larimer training rows from late 2019 carry labels from inside 2020.

Where: `cofire/model/features_a.py` (`add_horizons`), `cofire/model/rerun_a.py`
(`load_domain`), `cofire/model/shipping.py` (`lodo_score`). Frozen; not edited.
Consequence: the validation-based results (the stage 1 survivors, the family
choice) were computed with the first 2 to 8 weeks of 2022 outcomes seen in
training. Look 3 is unaffected, since the latest leaked label is February 2022,
and so are the 2026 forecasts.

### The `erc_pct` reference pool: clean across the split, leaks within folds

Pools are built from training rows only and hold same-week ERC values, not
future labels, so a validation or 2026 row's percentile uses nothing it should
not. Within leave-one-year-out, though, the pools are fit once on the whole
training split and reused, so the held-out year's own ERC values, and every
later training year's, help define the percentile that is its own target.

Where: `cofire/model/erc_pct.py`, `cofire/model/features_a.py`. Frozen; not
edited. Consequence: fold-based results, the family choice and the Stage B
width-ratio classification, carry this self-inclusion. Stage B no longer drives
the rendering, since no band is drawn.

### Warm-start and carried state in the export path: leaked, fixed

The export applied one radius to every 2026 forecast: the final state of the
`ahead=1` PID run over 2022 to 2025. Beyond the same-week leak, that run's
stream was built from the frame that extends through 2026, so its last 2 to 8
weeks of labels were outcomes from January and February 2026, the sealed year.
The radius is no longer computed or carried by the export
(`cofire/ship/export.py`). The values that were shown are kept for the record in
`artifacts/audit/shown_radius.json`, restored from the export at commit
`1e31eba`, and the audit reads them from there.

Everything else the export carries is fit on the training split only: point
forecasts, probabilities, the seasonal base rates, and the typical-range
percentiles. Clean.

### Also found: multi-regime calibration pools

The rejected multi-regime variants (`cofire/model/uncertainty/multiregime.py`)
pool residuals from the most similar years, which can be later years. They do
not ship. Recorded for completeness.


## Sensitivity: the stage 1 survivors under a leak-free refit

Added 2026-09-26. `cofire/ship/sensitivity.py`, a diagnostic outside the frozen
path; nothing ships from it.

Every fit, the models and the reference baselines alike, dropped training rows
whose h-week label lands after 2021-12-31, and the stage 1 test was rerun
exactly as before: paired real-minus-shuffled BSS, circular block bootstrap,
BH at q=0.10, Holm within families, 12 positive weeks minimum. For stage 1's
single split the stored `erc_pct` was asserted equal to a training-years-only
recomputation, and it is: the self-inclusion fault is inside the folds only.

| county | target | before [95% CI] | after [95% CI] | survives |
|---|---|---|---|---|
| larimer | d_ge2_h2 | +0.792 [+0.191, +1.141] | +0.833 [+0.167, +1.196] | yes |
| larimer | d_ge2_h4 | +0.430 [+0.026, +0.806] | +0.486 [+0.017, +0.870] | yes |
| larimer | d_improve1_h2 | +0.211 [+0.109, +0.338] | +0.205 [+0.100, +0.326] | yes |
| larimer | d_improve1_h4 | +0.339 [+0.195, +0.528] | +0.327 [+0.182, +0.511] | yes |
| larimer | d_improve1_h8 | +0.402 [+0.273, +0.607] | +0.371 [+0.240, +0.562] | yes |
| larimer | d_nochange_h2 | +0.158 [+0.057, +0.266] | +0.165 [+0.064, +0.278] | yes |
| larimer | d_nochange_h4 | +0.239 [+0.077, +0.397] | +0.255 [+0.095, +0.424] | yes |
| larimer | d_nochange_h8 | +0.324 [+0.174, +0.481] | +0.348 [+0.174, +0.501] | yes |
| pueblo | d_ge2_h2 | +0.305 [+0.077, +0.515] | +0.305 [+0.091, +0.513] | yes |
| pueblo | d_ge2_h4 | +0.219 [+0.011, +0.369] | +0.216 [-0.002, +0.373] | **no** |
| pueblo | f_gt80_h8 | +0.041 [+0.014, +0.062] | +0.040 [+0.012, +0.068] | yes |
| pueblo | f_gt90_h8 | +0.025 [+0.004, +0.042] | +0.024 [+0.003, +0.045] | yes |

11 of 12 survive. Pueblo `d_ge2_h4` falls, its lower bound moving from +0.011 to
-0.002 while the point estimate barely moves; it was marginal. Across all
estimable comparisons the median shift in the paired difference is
0.0033 and the largest 0.0560. Estimable comparisons fall from
39 to 38: Larimer `f_gt97_h4` drops from 12 positive weeks to 11, because the
embargoed fit leaves one ERC state unseen and one positive week's rows get no
prediction; it was not a survivor before.

The fire conclusion is unchanged: no fire target beats the ERC-decile
transition baseline in both counties. The two fire survivors are both Pueblo
at 8 weeks, as before.

The fire family choice, the one fold-based decision that feeds stage 1, was
redone with `erc_pct` recomputed per fold from that fold's training years and
an h-week embargo before each held-out year. The damped logistic beats the
transition table in all 9 fire targets, matching the shipped choice.

The app now claims only the 11 that survive both tests.

## Addendum, 2026-09-27: Pueblo d_ge2_h4 restored

The validation record used above was missing the USDM map for 2022-12-27; the
server's 2022 yearly archive predates that map, and the frozen rasterizer
coded the week "none" (Pueblo's mean category was 1.23 the week before and
1.19 the week after). With the map fetched and the stores rebuilt, the
five-domain leak-free test (`cofire/ship/survivors_v11.py`, same protocol)
gives Pueblo `d_ge2_h4` a paired difference of +0.2427 [+0.0067, +0.4227],
against +0.2158 [-0.0018, +0.3728] before the fix. It passed the original
stage 1 test, so under the claim rule it is claimed again. Record in
`docs/DECISIONS.md`.
