# COFIRE design

## The claim

COFIRE forecasts drought and fire-spread conditions, states how uncertain each forecast is, says
when that uncertainty itself cannot be trusted, and turns the result into a decision.

Each clause is load-bearing, and the third is the one that distinguishes this system.

## What COFIRE does not claim

COFIRE does **not** claim better forecast skill than persistence. This was tested and the answer is
no:

- On the 2026 hindcast, no trained arm improved on persistence at 4 or 8 weeks for either target.
- On leave-one-drought-year-out folds, mean skill on the ERC percentile is −2.0% with a confidence
  interval spanning zero: indistinguishable from "next month looks like this month".
- Re-specifying the target to predict *change* instead of *level* was tried. It significantly helps
  drought (+7.9pp, CI [+3.1, +14.2]) but still loses decisively to persistence (−23.9%), and on the
  headline ERC target it is indistinguishable from the level parameterisation.

That work is finished and is not being pursued further. The numbers live in `artifacts/metrics.md`
and `artifacts/lodo/lodo.md`, reported as the negative result they are. Product copy must not imply
otherwise: `scripts/check_copy.py` fails the build on a fixed list of superiority phrases (see
`SUPERIORITY` in that script) anywhere in `app/` or `docs/`.

The comparison itself stays in `artifacts/metrics.md`, which the lint deliberately does not scan —
reporting a negative result requires naming the comparison, while advertising copy does not.

## Why the uncertainty layer is the product

A 4-week forecast that ties persistence is still useful **if you know how much to trust it**. Most
forecast products show an interval and leave the reader to assume it means what it says. COFIRE
measures whether its own intervals hold, and reports the answer even when the answer is bad.

Two findings shaped this:

1. **A real bug made intervals shrink under stress** (v0.5). The adaptive-conformal update targeted
   the coverage rate where it needed the miss rate, so its only stationary point was a 90% *miss*
   rate. Coverage decayed to 0.26 on a stationary stream with no distribution shift at all. Fixed,
   with ten regression tests that fail on the old code.

2. **Fixing the bug was not enough, and no pool construction closes the rest** (v0.6). Six
   pre-registered calibration-pool variants were tested on LODO folds. All six were rejected against
   a criterion fixed in advance. Best mean coverage: 0.409 against a 0.90 target. The reason is that
   held-out years carry a ~2.4x residual inflation that no covariate computed from the pool
   predicts. Under the original splits this is an in-sample/out-of-sample gap, uniform across
   held-out 2023/2024/2025 (p90 59.2/60.6/62.7 vs 20-26 on training years); a v0.7 leakage audit
   confirmed no leak (`artifacts/uncertainty/leak_check.md`). Because the inflation is constant
   across pool years, reweighting across them cannot recover it.

The honest conclusion is that this record cannot support a calibrated 90% interval for a regime it
has not seen. So COFIRE says that, per issue date, in the interface.

## The three-state uncertainty status

Computed from calibration diagnostics in `cofire/model/uncertainty/status.py`, never hand-set.

| state | condition | product behaviour |
| --- | --- | --- |
| **calibrated** | current regime inside the pool's range, and pool coverage >= 0.60 | interval shown normally |
| **extrapolating** | regime exceeds the pool maximum by <= 2 pool SD | interval widened by the pre-registered rescaling and shown with a visible caveat |
| **uncalibrated** | pool coverage < 0.60, or regime exceeds the pool by > 2 pool SD | **interval suppressed**; point forecast and Why drivers still shown |

The regime covariate is the domain-mean USDM category of the issue week, compared against the pool's
range over its constituent years. Thresholds are constants in the module, not magic numbers scattered
through the UI.

Consequence worth stating plainly: on the 2026 record the status is **uncalibrated** — mean USDM
2.231 against a pool maximum of 0.916, 3.7 pool standard deviations past anything in the record. The
app therefore hides the interval for exactly the regime that produced the No-go verdict. That is the
intended behaviour, not a failure of the feature.

## Architecture

| layer | module | role |
| --- | --- | --- |
| features | `cofire/model/features.py` | SPI/SPEI, lags, leakage-safe rolling stats |
| arms | `models/lightgbm_arm.py`, `models/pi_convlstm.py` | LightGBM per horizon; physics-informed ConvLSTM |
| evaluation | `eval.py`, `sanity.py` | MAE/Brier/ECE, week-block CIs, six leakage gates |
| shift testing | `lodo.py` | leave-one-drought-year-out; costs no holdout budget |
| uncertainty | `conformal.py`, `uncertainty/multiregime.py`, `uncertainty/status.py` | split conformal + ACI, pool variants, three-state status |
| serving | `cofire/api/`, `app/` | precomputed forecasts only; no model runs at request time |

## Discipline

- The 2026 hindcast is a locked holdout with a public look counter (`artifacts/hindcast/run_log.json`).
  It stands at 2 looks. Any further look is pre-registered in `docs/PREREGISTRATION.md`, whose
  trigger is currently unmet.
- Calibration experiments are pre-registered in `docs/PREREGISTRATION_CALIBRATION.md` with the
  variant list, acceptance criteria and width cap fixed before running. Every variant is reported,
  including failures.
- Effective sample size is respected: 125,280 cell-weeks are not 125,280 independent samples. The
  drought AR(1) effective n is 3.0. Headline intervals are week-block bootstrap.
- Statewide is staged and gated; no stage may exceed 60 minutes.
