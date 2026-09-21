# Pre-registration: look 3 on the 2026 holdout

**This session does not take this look.** It ends here for a human to approve or
reject. The holdout stands at **2 looks** on config `0957e415fa7f3fad`, recorded
in `artifacts/hindcast/run_log.json` and enforced by `tests/test_look_seal.py`
and `COFIRE_ALLOW_LOOK` in the hindcast stage.

This supersedes the earlier eight-target pre-registration (sha256
`88d8fdf7...`), which was withdrawn when the circular block bootstrap flipped 6
of 13 conclusions.

## What changed, and why this look is different

The earlier pre-registration asked whether a machine-learning model showed skill
against baselines. It does not. Under correct references, a rare-event
bootstrap, multiplicity control and the library implementations, the survivor
count is **zero**: no target where the ML model demonstrates skill over an
appropriate baseline in both domains.

So the baselines ship, and there is nothing left to claim skill over. This look
tests **calibration**, not skill. There are no skill hypotheses in it, because
the shipped forecast *is* the baseline.

## Configuration A, frozen

sha256 `67da282e8b377ea0b59834372945e5071d5bab4774fd78172a43c432b00ad49b`,
over `artifacts/shipping/choices.json`,
`artifacts/shipping/continuous_arms.json` and the pinned constants below.

**Probabilistic targets**, 27 of them, one family each, frozen in
`choices.json`: Markov 18, ERC-decile transition 6, damped-persistence logistic
3. Pooled across domains with an indicator on 21 of 27, per domain otherwise.
Markov settings: `min_weeks=32`, `prior_strength=4.0`,
`persistence_weight=0.75`.

**Continuous ERC percentile**: `damped_regression` at h2 and h4, `decile_mean`
at h8, chosen once on pooled LODO MAE.

**Intervals**: the vendored reference conformal PID,
`quantile_integrator_log`, with the paper's gains `lr=0.1`, `Csat=2.0`,
`KI=1.0`, `T_burnin=100`, target coverage 0.90. Gains are not searched.

## Configuration B, and the adoption rule

Configuration B is A plus SubX CFSv2 weeks 1 to 4 anomaly covariates, entering
the conditional models as a logistic extension of the transition tables.

**The rule, stated exactly.** B is adopted **if and only if**, on pooled
leave-one-drought-year-out with the circular block bootstrap, at least one
target's Brier skill score against configuration A has a 95 percent confidence
interval entirely above zero **in both domains**. If adopted, **only the targets
that individually pass switch to B; every other target stays on A.**

The SubX run happens **once**, after the fetch completes and before look 3, with
the rule applied mechanically. No iteration, no re-specification, no second run
with different covariates. If the rule selects nothing, A is frozen unchanged
and that is the recorded result.

## Confirmatory tests on 2026

Applied to whichever configuration the rule selects.

**1. Interval coverage.** Reference PID at h2, h4 and h8, per domain, on 2026
issues.

- **Pass** if realised coverage is within **0.05** of nominal 0.90, that is
  within [0.85, 0.95], **and** the longest run of consecutive misses is below
  **200** cell-weeks.
- The miss-run bound is set from the validation evidence: the observed runs are
  8 to 19, and ACI's failures ran to 1860. A bound of 200 is roughly ten times
  the worst observed value and an order of magnitude below the failure mode, so
  it separates the two without being tuned to either.

**2. ACI on the same streams**, recorded as the comparison. No pass criterion.
Its validation values are 0.9320, 0.8961 and 0.8057 on Larimer and 0.9019,
0.5970 and 0.6887 on Pueblo.

**3. Reliability of every shipped probabilistic target**, per domain: the
reliability term of the Murphy decomposition, plus a reliability diagram.

- **Pass** if the reliability term is below **0.01** for that target and domain.
- Set from the validation evidence, where 24 of 27 pooled targets are below
  0.01 and the worst is `d_ge2_h8` at 0.060. A threshold at 0.01 is the level
  most of the shipped set already meets, so failure means a real degradation
  rather than a stricter ruler.

**4. Targets with zero LODO resolution are scored for calibration only.** Eight
targets have zero resolution in at least one domain, listed in
`artifacts/shipping/step1_by_domain.csv`. A forecast that does not vary between
cells has no discrimination to confirm, so only its reliability term is tested
and no discrimination claim is made for it.

**5. Local coverage.** Long-run coverage is guaranteed by the conformal
construction, so it is demoted to a sanity check and is not a primary test. What
is tested instead is whether coverage holds *locally*, which the construction
does not guarantee:

- **Minimum rolling 13-week coverage**, per horizon and domain. Pass if the
  worst 13-week window on 2026 is at or above **0.70**. Justification: with 13
  weekly windows the binomial standard error at p=0.90 is about 0.083, so 0.70
  is roughly 2.4 standard errors below nominal and separates ordinary sampling
  noise from a genuine local failure.
- **Coverage conditional on current USDM category**, D0-D1 against D2+, each
  within **0.10** of nominal, that is within [0.80, 1.00]. The tolerance is
  looser than the global one because conditioning splits the sample, and the D2+
  stratum is the smaller of the two in both domains.

Both are reported per horizon and per domain, and both must pass for the
coverage criterion to pass.

**6. Informativeness of the continuous forecast.** Per continuous target and
horizon:

- MAE of the shipped point forecast against a **climatological median
  predictor**, the per-cell week-of-year median of the future percentile, with a
  circular block bootstrap interval on the difference.
- PID mean width as a fraction of the **climatological 90 percent interval
  width**, per cell and week of year, estimated on training years.

**Classification rule, fixed here.** A continuous target and horizon is
classified **climatological** if the width ratio exceeds **1.0** or the MAE
difference interval against the median predictor includes zero.

The threshold of 1.0 is not tuned. It is the point at which the interval the
product would display is exactly as wide as quoting the historical range for
that week. Above it, a "forecast" interval is wider than history, which cannot
be more informative than history. The two quantities are directly comparable:
PID targets 90 percent coverage of the absolute residual and reports a two-sided
width of 2q, against a 5th-to-95th-percentile climatological spread.

This is a classification, not a verdict on the method. A well-calibrated
interval that is wider than climatology is still correctly calibrated; it is
simply not worth displaying as a forecast.

**No skill claims against baselines.** The shipped forecast is the baseline.

## Reference values, measured before the look

These are LODO values on training years, computed and recorded **before** the
look so the thresholds above are set against known quantities rather than
against the holdout.

**Target definition, confirmed.** `erc_pct` is a percentile of ERC against that
cell's own week-of-year training distribution, pooled over a circular plus or
minus 3 week window (`features.py`, `PCT_HALF_WINDOW = 3`). Checked
empirically: the monthly mean of `erc_pct` spans 40.5 to 60.8 against raw ERC's
39.9 to 63.6, so the seasonal cycle is removed as intended. The residual
variation is interannual drift, not a calendar signal.

    domain   h  arm                 MAE   median MAE   gain [95% CI]        PID width  clim width  ratio
    larimer  2  damped_regression  24.97     32.91     +7.94 [+4.80, +10.74]   92.94      33.70    2.758
    larimer  4  damped_regression  25.22     32.82     +7.61 [+4.95, +10.25]   91.46      32.73    2.795
    larimer  8  decile_mean        26.64     32.02     +5.38 [+2.27,  +8.27]   94.51      34.07    2.774
    pueblo   2  damped_regression  23.43     29.65     +6.22 [+2.49,  +9.88]   90.89      36.05    2.521
    pueblo   4  damped_regression  23.25     29.61     +6.36 [+2.15,  +9.97]   93.12      35.24    2.643
    pueblo   8  decile_mean        23.64     27.31     +3.67 [-0.63,  +6.98]   89.10      36.94    2.412

**What this says, stated before the look.** Applying the rule above to these
LODO values classifies **all six continuous target-and-horizon pairs as
climatological**, on the width criterion, since every ratio is between 2.41 and
2.79. `pueblo h8` fails on the MAE criterion as well, its interval including
zero at [-0.63, +6.98].

The point forecasts do carry information: five of six have MAE gains over the
median predictor with intervals clear of zero, 3.67 to 7.94 percentile points.
The *intervals* do not. A residual MAE of about 24 percentile points on a 0 to
100 scale needs a wide interval to cover 90 percent of cases, and that width
exceeds what history alone would quote.

Recording this now means the look cannot change the classification, and the
product consequence below is already decided.

## Product consequence, decided now

Any continuous target and horizon classified climatological renders on the Place
Card as **the historical range for that week of year**, labelled as such, with
no forecast interval and no language implying a prediction. The point forecast
may still be shown, because it is informative, but the uncertainty around it is
presented as what history says rather than as what the model claims.

On the LODO evidence above that is **all six**, so the Place Card ships showing
historical ranges for the continuous ERC target at every horizon on both
domains. The look does not change this: it is decided here.

## Overall outcome, fixed in advance

- **Confirmed** if every coverage test passes, including the local coverage
  tests, and at least 80 percent of target-and-domain reliability tests pass.
- **Partially confirmed** if all coverage tests pass but reliability falls below
  that share.
- **Not confirmed** if any coverage test fails.

Coverage is the gating criterion because it is what the product promises: an
interval labelled 90 percent that contains the truth 60 percent of the time is a
broken product, whatever the probabilities do.

## Recorded predictions

- Coverage will pass at all three horizons on both domains. Validation holds
  0.8987 to 0.8995 across six cells, and the conformal guarantee is
  distribution-free, so 2026 being unusual should not break it. This is the
  strongest prediction in the document.
- ACI will fail at h8 on at least one domain, continuing its validation
  collapse.
- Reliability will be worse on 2026 than on validation, because the 2026 drought
  base rate is 0.2745 for `d_intensify1_h4` on Pueblo against a 0.0114 to 0.1948
  range in prior years, and an empirical conditional model fitted to those years
  will be miscalibrated against a rate outside them. `d_ge2` at h4 and h8 is the
  most likely reliability failure.
- Local coverage is the most likely coverage failure. Global coverage is
  guaranteed by construction, but a 13-week window during a fast regime change
  is exactly where a controller lags, and 2026 carries an unusually high drought
  base rate.
- Conditional coverage on D2+ is more likely to fail than on D0-D1, because it
  is the smaller stratum and the one the training years cover least well.
- The expected overall outcome is **partially confirmed**: global coverage
  passing, local or conditional coverage marginal, reliability degraded by the
  regime shift.
- SubX will not be adopted. The rule requires both domains, and nothing in this
  project has cleared a both-domains bar yet.

If coverage fails at h2, that is more consistent with a plumbing fault than with
a real result, since the conformal guarantee is weakest at long leads and h2 is
the easiest case. It should be investigated before it is believed.

## Superseded version

This document supersedes sha256
`341b68e788b50b77226c965464fbcec594f20177d6d00a080a9405ff5001b0c0`, which
lacked the local coverage tests, the informativeness classification and the
product consequence. That version was never acted on and no look was taken
under it.

## Stopping rule

One run. The run log gains exactly one record, `look_index` 3. A technical
failure is recorded and not retried until a human reviews the cause.

## What a human is approving

A calibration test of a forecast layer made of empirical conditional models and
a vendored conformal controller. The honest summary is that the ambitious part
of this project did not work, the modest part does, and this look asks only
whether the modest part remains calibrated on a year it has never seen.
