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

## The shipped configuration

**Final config sha256
`f65b7f7a28bcba199b38e9ea2d43f364f9ca7db16b9b32a042c850a70534de99`**, over the
frozen family choices, the continuous arms, the SubX verdict and the pinned
constants. This is what look 3 tests.

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

**The run has been executed. Result: one target adopted.**

    target      domain   Brier A   Brier B   BSS B vs A [95% CI]
    f_gt90_h2   larimer  0.14459   0.13393   +0.0737 [+0.0036, +0.1119]
    f_gt90_h2   pueblo   0.18622   0.12536   +0.3268 [+0.2006, +0.4509]

54 comparisons, 43 estimable, 10 passing in a single domain, 1 passing in both.
`f_gt90_h2` ships on **configuration B**; all other targets ship on **A**.

The leakage guard was active: the lead-dependent climatology is refit per fold
with the held-out year excluded, `assert_no_self_contribution` verifies no
held-out week fed its own anomalies, and A was rescored on exactly the rows B
sees, 74,880 of 218,880 on Larimer and 67,392 of 196,992 on Pueblo.

**The evidential basis is one year.** Only 2020 falls inside the 2018 to 2020
training split, so each comparison rests on a single held-out year and the
bootstrap prices uncertainty within that year rather than across years. Ten
single-domain passes out of 43 estimable comparisons is roughly what a 5 percent
per-comparison error rate produces unaided, which is the reason the rule demands
both domains. `f_gt90_h2` is adopted because the rule was fixed in advance and
it passed; its confirmation on 2026 is a genuine test of a thin result.

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
classified **informative** only if the circular-block-bootstrap 95 percent
interval of the width ratio lies **entirely below 1.0**. Otherwise it is
classified **climatological**.

The anchor of 1.0 is not tuned. It is the point at which the interval the
product would display is exactly as wide as quoting the historical range for
that week. Above it, a "forecast" interval is wider than history, which cannot
be more informative than history. The two quantities are directly comparable:
PID targets 90 percent coverage of the absolute residual and reports a two-sided
width of 2q, against a 5th-to-95th-percentile climatological spread in the same
units.

Requiring the whole interval below 1.0, rather than the point estimate, makes
the rule conservative by construction and independent of where the point
estimate happens to fall. A ratio estimated at 0.98 with an interval reaching
1.15 is not evidence that the forecast interval is narrower than history.

This is a classification, not a verdict on the method. A well-calibrated
interval wider than climatology is still correctly calibrated; it is simply not
worth displaying as a forecast.

**No skill claims against baselines.** The shipped forecast is the baseline.

## Reference values, measured before the look

These are LODO values on training years, computed and recorded **before** the
look so the thresholds above are set against known quantities rather than
against the holdout.

**Target definition, confirmed.** `erc_pct` is a percentile of ERC against that
cell's own week-of-year training distribution, pooled over a circular plus or
minus 3 week window (`features.py`, `PCT_HALF_WINDOW = 3`). Checked
empirically: the monthly mean of `erc_pct` spans 40.5 to 60.8 against raw ERC's
39.9 to 63.6, so the seasonal cycle is removed as intended.

**A unit error in the previous version, corrected.** The climatological width
was computed by grouping on a *single* week of year, which holds about **three**
training values per cell. The 5th and 95th percentiles of three values are its
minimum and maximum, so the width collapsed to 33 to 37 for a quantity that must
be near 90 on a near-uniform percentile marginal. It is now pooled over the same
circular plus or minus 3 week window used to define the percentile itself.

    single week, 3 values per cell    50.6
    pooled +/- 3 weeks                81.2
    cross-cell marginal               91.4

**Which figure the rule uses, and why two appear.** The rule uses the
**LODO figure, 73.5 to 75.5**, because the ratio is computed inside the same
folds the forecast is scored in. The 81.2 quoted above is the same estimator run
on the **full** training frame. The difference is a small-sample tail effect,
not an estimator discrepancy, and it was traced rather than assumed:

    same estimator, full training frame, per row          80.96
    same estimator, full frame, unique (cell, woy)        80.96
    independent probe, unique (cell, woy), 60 cells       81.17
    same estimator, inside the LODO fold                  73.54

Per-row and per-cell-week means agree to two decimals, so it is not a weighting
artefact. It is the number of values available: a pooled 7-week window holds
about 7n values for n training years, so the full frame gives about 21 and a
LODO fold about 14, and a 5th-to-95th spread estimated from 14 values sits
inside one estimated from 21. Fewer values, narrower apparent tails.

Ties were checked and ruled out: the fraction of `erc_pct_h4` values pinned at 0
or 100 is 0.0000 to 0.0248 by season on Larimer and 0.0000 to 0.0445 on Pueblo,
far too small to move a width by 7 points.

**A limitation this exposed, stated plainly.** The training split runs 2018 to
2020, so of the four nominal LODO fold years only **2020** falls inside it. Every
LODO figure in this document therefore rests on **one fold fit on two years**.
That is thin, it is why the fold width is biased low, and it bounds how much
weight any LODO number here can carry. It does not change the classification:
the ratio intervals are 1.111 to 1.369 and would have to fall by roughly a fifth
to reach 1.0, which the 81.2 full-frame width moves them further from, not
closer to.

`tests/test_clim_width.py` asserts the estimator's invariant on a synthetic
uniform panel, which is the check that would have caught the original error.

**Corrected reference values, LODO, training years:**

    domain   h  arm                 MAE   clim MAE   gain [95% CI]         PID w  clim w  ratio [95% CI]
    larimer  2  damped_regression  24.97    31.81   +6.85 [+3.98, +9.58]   92.94   73.46  1.265 [1.210, 1.324]
    larimer  4  damped_regression  25.22    31.45   +6.23 [+3.36, +8.66]   91.46   73.54  1.244 [1.168, 1.322]
    larimer  8  decile_mean        26.64    31.05   +4.41 [+1.88, +6.70]   94.51   73.45  1.287 [1.206, 1.369]
    pueblo   2  damped_regression  23.43    29.43   +5.99 [+2.21, +10.07]  90.89   75.43  1.205 [1.148, 1.260]
    pueblo   4  damped_regression  23.25    29.45   +6.20 [+1.72, +10.03]  93.12   75.51  1.233 [1.165, 1.298]
    pueblo   8  decile_mean        23.64    27.44   +3.80 [+0.35,  +7.24]  89.10   75.44  1.181 [1.111, 1.248]

**What this says, stated before the look.** Under the rule above, **all six
classify as climatological**: every ratio interval lies entirely *above* 1.0, so
none can be classified informative. The correction changed the magnitude, from
ratios of 2.41 to 2.79 down to 1.18 to 1.29, but not the conclusion.

It did change one thing. With correct units **all six MAE gains now clear zero**,
where `pueblo h8` previously did not, at [-0.63, +6.98] against a corrected
[+0.35, +7.24]. So every point forecast is informative against a climatological
median predictor, by 3.80 to 6.85 percentile points, while no interval is.

That split is the finding: the point forecasts carry real information and the
intervals around them do not, because a residual MAE near 24 percentile points
on a 0 to 100 scale requires more width to cover 90 percent of cases than the
historical range for that week already spans.

## Product consequence, decided now

Fixed here so the look cannot influence it.

**Where the target is classified climatological and the MAE gain interval
clears zero**, which on the LODO evidence is all six, the Place Card shows:

- the **point forecast**, because it is informative, and
- the **historical week-of-year range of raw ERC for that cell**, labelled as
  the historical range.

The historical range is quoted in **raw ERC units, not percentile units**,
because "somewhere between the 5th and 95th percentile" tells a reader nothing:
it is the definition of the scale restated. A range in ERC is a quantity a fire
manager already reads.

**Where the MAE gain interval does not clear zero**, the Place Card shows the
historical range only, with no point forecast.

No forecast interval is displayed for any target classified climatological, and
no wording implies a prediction of the range.

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

This document supersedes two earlier versions, neither of which was acted on
and under neither of which was any look taken:

- sha256 `341b68e788b50b77226c965464fbcec594f20177d6d00a080a9405ff5001b0c0`,
  which lacked the local coverage tests, the informativeness classification and
  the product consequence.
- sha256 `cabf75e1c847ae8038fcb02d2151d90383d5c4d21e605f90cf8aaadda687cef9`,
  whose climatological width was computed on single-week groups of about three
  values and understated it by roughly a factor of 2.2, and whose
  classification rule used a point estimate rather than an interval.
- sha256 `fdccb0f6a00a6ef27b92ea7ca4eeb87da6ee4e6f3ee26a6eedbe4d06b2b8b991`,
  which reported the corrected reference values without explaining why the
  in-fold width differs from the full-frame width, and without recording that
  only one LODO fold falls inside the training split. No reference value or
  classification changed; the basis is now stated.

## Stopping rule

One run. The run log gains exactly one record, `look_index` 3. A technical
failure is recorded and not retried until a human reviews the cause.

## What a human is approving

A calibration test of a forecast layer made of empirical conditional models and
a vendored conformal controller. The honest summary is that the ambitious part
of this project did not work, the modest part does, and this look asks only
whether the modest part remains calibrated on a year it has never seen.
