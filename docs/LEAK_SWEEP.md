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
