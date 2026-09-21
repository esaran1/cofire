# Pre-registration: look 3 on the 2026 holdout

**This session does not take this look.** It ends here, at a frozen
specification, for a human to approve or reject. The holdout stands at **2
looks** on config `0957e415fa7f3fad`, recorded in
`artifacts/hindcast/run_log.json` and enforced by `tests/test_look_seal.py` and
by `COFIRE_ALLOW_LOOK` in the hindcast stage.

Everything below was decided before the look and is fixed. This document
supersedes the earlier look-3 pre-registration, which named no specific targets
and predated the corrections that changed which results exist at all.

## What this look is for

Every number in this session is **exploratory**. The targets below survived a
sequence of filters applied to validation data, and surviving a filter chosen
after seeing data is not evidence. Look 3 exists to test a small, named set of
claims on data that has never been used, once.

## The claims

Eight target-and-domain pairs. Each is one hypothesis: that the frozen two-stage
model achieves a positive Brier skill score against **week-of-year seasonal
climatology** on 2026.

    domain   target            h   validation BSS [95% CI]      persist  markov
    pueblo   f_gt80_h2         2   +0.1215 [+0.034, +0.229]      +0.318     n/a
    pueblo   f_gt80_h4         4   +0.1110 [+0.022, +0.243]      +0.397     n/a
    pueblo   f_gt80_h8         8   +0.1041 [+0.029, +0.210]      +0.420     n/a
    larimer  f_gt97_h4         4   +0.0993 [+0.052, +0.189]      +0.451     n/a
    larimer  f_gt97_h2         2   +0.0901 [+0.046, +0.178]      +0.414     n/a
    larimer  f_gt97_h8         8   +0.0883 [+0.052, +0.153]      +0.449     n/a
    larimer  d_intensify1_h2   2   +0.0691 [+0.026, +0.133]      +0.006   +0.157
    larimer  f_gt90_h8         8   +0.0531 [+0.018, +0.096]      +0.419     n/a

These are what remained after: 51 targets, 40 estimable under the rare-event
rule, 13 surviving Benjamini-Hochberg at q=0.10 with Holm within event family, 9
clearing every applicable baseline, and 8 agreeing in sign across both domains.

## What is excluded, and why

Recorded so the selection cannot be revisited after the look.

- **`d_nochange` at h2, h4, h8 (larimer).** Survived BH against climatology but
  loses to the Markov baseline by -0.217, -0.359 and -0.515. A model that clears
  climatology and loses to a transition matrix has no forecast skill for a
  persistence-dominated target.
- **`d_intensify2_h8` (pueblo).** Survived BH but loses to persistence at
  -0.021.
- **`d_intensify1_h4`.** The largest surviving effect at +0.1558 on Pueblo, and
  **-0.5357 on Larimer**. The standing two-domain rule treats disagreement as
  evidence of fitting one geography.
- **Eleven targets not estimable.** Fewer than 12 positive domain-weeks in
  validation, so no interval can be computed. `d_intensify2_h2` on Larimer has
  three.

## The frozen specification

No part of this may be refitted, retuned or reselected before the look.

**Stage 1**, the domain event rate: ridge regression on the logit of the
domain-week rate, predictors `oni, pdo, swe_pct_median, esi_12wk,
pr_deficit_12w` plus `sin_doy` and `cos_doy`, **penalty 100**, chosen once on
pooled LODO across all targets and both domains. Intercept unpenalised. Fitted
on one row per domain-week, never per cell.

**Stage 2**, the cell ranking: LightGBM binary classifier on the v1 feature set,
no class weighting, learning rate 0.05, 31 leaves, 150 rounds, seed 2026, one
thread. Features exclude every `_h\d+$` column.

**Combination**: `stage1_logit + w * (cell_logit - mean(cell_logit))`, with `w`
fitted by one-parameter logistic regression on pooled out-of-fold LODO
predictions, floored at 0 and capped at 1.

**Row set**: rows where every v1 source group is present, the same restriction
used throughout.

## Reference baseline

**Week-of-year seasonal climatology**, domain-wide, circular +/- 3 week window,
shrunk toward the overall training rate, estimated on training years only. This
is the primary and the only reference the pass rule uses.

Persistence, Markov and the flat constant are **reported** for every target but
do not enter the rule. They were used to select the set; using them again to
judge it would be scoring the same filter twice.

## The bootstrap

Stratified block bootstrap by week, 400 replicates, positive and negative weeks
resampled separately to their own counts, 95 percent percentile interval. A
target with fewer than **12 positive domain-weeks** in the 2026 evaluation
window is reported **not estimable** and counts as neither a pass nor a failure.

## The pass rule, fixed in advance

Per target: **pass** if the point BSS against seasonal climatology is positive
**and** the lower bound of the 95 percent interval is above zero.

Overall, stated before the look:

- **Confirmed** if at least 5 of the 8 pass, and no target fails with an
  interval entirely below zero.
- **Partially confirmed** if 2 to 4 pass.
- **Not confirmed** if 0 or 1 passes.
- Any target reported not estimable is excluded from both the numerator and the
  denominator, and the thresholds scale: at most 8 minus the not-estimable count
  can pass, and the "confirmed" bar becomes a simple majority of the estimable
  ones.

Multiplicity is **not** reapplied at look 3. The set was already reduced by BH
at q=0.10; applying it again to eight pre-registered hypotheses would be
correcting twice for the same selection.

## Recorded predictions

So that a surprising result is visibly surprising rather than absorbed.

- The fire targets will do **worse** on 2026 than on validation. Their skill
  comes from ranking fuel state, they have no forecast weather behind them
  (SubX was located but not ingested), and 2026 has an unusually high drought
  base rate at 0.2745 for `d_intensify1_h4` on Pueblo against a 0.0114 to
  0.1948 range in prior years.
- `d_intensify1_h2` on Larimer is the most likely single failure: its validation
  margin over persistence is +0.006, which is within noise of zero.
- The most likely overall outcome is **partially confirmed**, 2 to 4 passing.
- Coverage of the shipping interval will still fail at h8, unchanged from the
  earlier prediction and unaffected by anything in this document.

If 7 or 8 pass, that is not a triumph to report as one. It would be more
consistent with a leak than with genuine skill of this magnitude, and it should
be investigated before it is believed.

## Stopping rule

One run. The run log gains exactly one record, `look_index` 3. A technical
failure is recorded and not retried until a human reviews the cause, because a
retry after a partial look is a fourth look wearing the name of the third.

## What a human is approving

That these eight claims, this specification, this baseline, this bootstrap and
this pass rule are worth spending the third of a small number of looks on. The
honest expected value is modest: the effects are small, the effective sample
sizes run from 20 to 53 weeks, and the strongest single result was excluded for
failing to replicate across domains.
