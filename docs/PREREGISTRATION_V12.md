# Pre-registration: v1.2 model stages 1 to 4

Recorded before any v1.2 model run. Its sha256 is written to `STATUS.md` in
the same commit that adds it, and no stage runs before that commit exists.
Nothing below changes after that commit. A new idea seen while running goes
into `docs/DECISIONS.md` as future work and is not run.

## What does not move

- `cofire/model/` is unchanged and `tests/test_frozen_model.py` stays green.
  All new code lives in `cofire/v12/`.
- Configuration A (config hash `ed0c2079a5bc0eee1d0aa11869d3bc5eb0af671b9f30ee0c5114c3b9ca7be157`)
  remains the configuration evaluated at the 2027-01-12 unseal. No v1.2 arm
  enters that evaluation.
- 2026 stays sealed. No metric, coverage, reliability or comparison is
  computed against any 2026 outcome. Every stage asserts the look counter
  reads 3 before it starts and after it ends.
- Every fitted artifact carries `fit_start` and `fit_end` and is read through
  the frozen strict loader.
- **All variants are reported, including failures**, with every grid value.

## Data and folds, shared by every stage

- **Record:** 2007 to 2025, the five domains (Denver, Upper South Platte,
  Dillon, Larimer, Pueblo), from the configuration A stores
  (`cofire/ship/build_v11.load`).
- **Evaluation folds:** held-out years **2012, 2013, 2020, 2021, 2022, 2023,
  2024, 2025**.
  - These are the four years that are LODO folds in every domain (v1.1 Stage
    4) plus the validation and calibration years, which configuration A never
    fitted on.
  - For held-out year Y, the training years are 2007 to 2025 without Y.
  - Every training row whose h-week label lands in Y is dropped (the h-week
    embargo).
  - `erc_pct` is recomputed per fold from that fold's training years only.
- **Pooled folds** means the eight held-out years concatenated, scored per
  target, horizon and domain.
- **Configuration A on a fold:** the frozen predictors called unchanged.
  Markov for drought; for fire, the family `fit_v11.load_choices` gives each
  domain (damped logistic in all five). Fitted on the fold's training rows.
- **Nested out-of-fold predictions.** Where a stage fits anything to
  configuration A's outputs, it uses predictions that configuration A made on
  years it was not trained on. For held-out year Y and each other training
  year y, configuration A is fitted on the training years without Y and y
  (embargoed at both, `erc_pct` from those years) and predicts y. Y's data
  never enters a model whose predictions feed Y's adjustment.
- **Targets:** the 27 event targets (18 drought, 9 fire) at h = 2, 4, 8.

## Metrics, per target, horizon and domain, on the pooled folds

1. Brier score, and its Murphy reliability and resolution terms (10 quantile
   bins, `prob_metrics.brier_decomposition`).
2. **The paired test against configuration A.**
   - It is `stats_lib.paired_bss_shuffled(pred = arm, ref = configuration A,
     y, weeks)`: real minus within-block-shuffled BSS, circular block
     bootstrap, 400 replicates, 20 shuffles, seed 2026.
   - A pair with fewer than 12 positive weeks on the pooled folds is not
     estimable.
   - The p-value comes from `stats_lib.bootstrap_pvalue`.
3. Multiplicity, within each stage's selected arm: BH at q = 0.10 across
   every estimable pair, then Holm at 0.05 within domain and event family
   (`multiplicity.family_of`).

## Selection rule, every stage

Each stage has a small grid fixed below. The grid value is chosen **once**,
as the one with the lowest pooled-fold Brier averaged with equal weight over
every target, horizon and domain the stage applies to. Only the selected
configuration goes to the adoption test, so the test is not repeated across
grid values. Every grid value is reported.

## Adoption rule, every stage

An arm replaces configuration A for a target, horizon and domain in the live
app only if, on the pooled folds:

1. the pair is estimable;
2. the paired test's CI lies above zero;
3. BH rejects across the stage's estimable pairs and Holm rejects within its
   domain and family;
4. the arm's reliability term is no larger than configuration A's for that
   pair.

Otherwise configuration A stays live for that pair. If two stages' arms both
qualify for a pair, the one with the larger paired difference is live.

**Surprisingly strong results.** Any qualifying pair whose real BSS against
configuration A exceeds 0.10 is rerun with 100 shuffles instead of 20. Both
results are reported before the rule is applied, and the rule uses the
100-shuffle run.

**Rendering of an adopted pair**, recomputed mechanically. No v1.2 arm may be
scored on 2026, so the look-3 reliability that decides Larimer and Pueblo's
rendering cannot be computed for it. An adopted pair therefore renders as a
per-cell probability if its pooled-fold reliability is at most 0.05 (the
preregistered look-3 threshold) and it is estimable on validation (12 or more
positive weeks in 2022 to 2023). Otherwise it renders as the regional base
rate, under the existing rule (unchecked drought targets show no number).
Pairs that keep configuration A keep their current rendering.

**Skill claims** follow the live arm. If a pair's live arm changes, its
survivor status is recomputed with the same leak-free validation test
(`survivors_v11`: 2022 to 2023, the seasonal or fire-transition reference,
BH and Holm across all five domains). The app reads `facts.survivors`.

**Expected outcome, recorded now.** Stages 1 and 2 keep each week's ranking of
cells nearly unchanged; their gains are in calibration and level. The
within-block shuffle keeps each block's event rate, so a level correction helps
on shuffled labels almost as much as on real ones. The paired test is
therefore expected to find little for stages 1 and 2, even where reliability
improves. Stage 3 changes rankings across categories and can show more. This
rule is the owner's and is applied as written; reliability results are
reported in full beside it.

## Stage 1: delayed-feedback logistic recalibration

The recalibrated probability is `q = sigmoid(a + b * logit(p_A))`, with `p_A`
clipped to [1e-4, 1 - 1e-4].

**Warm start, every variant.** (a0, b0) are fitted by L2-penalized logistic
regression on the fold's nested out-of-fold configuration A predictions,
penalty toward (0, 1) with weight 1.0 on the mean log loss. Intercept-only
variants fix b = 1.

**Static variants.** The state is fixed at the warm start and never updated
within the held-out year.

| id | parameters |
|---|---|
| S1-static-a | intercept only |
| S1-static-ab | intercept and slope |

**Online variants.** They start at the warm start and are updated within the
held-out year:

- **Delay.** An issue week's outcomes for horizon h become usable at the issue
  h weeks later, all cells of that week together. No cell's outcome is used
  earlier.
- **Update.** One update per newly resolved issue week, on the mean log-loss
  gradient over that week's cells.

| id | parameters | grid |
|---|---|---|
| S1-online-a | intercept only, SGD | learning rate 0.05, 0.2, 0.5 |
| S1-online-ab | intercept and slope, SGD | learning rate 0.05, 0.2, 0.5 |
| S1-ew | (a, b) refitted each issue week on the resolved held-out-year weeks, exponentially weighted, L2-penalized toward (a0, b0) with weight equal to 10 resolved weeks | half-life 8, 26 weeks |

**Which variants can ship.** A live online variant would update on resolved
2026 outcomes. That is a comparison of forecasts with 2026 outcomes, which
the seal forbids. So the online variants are evaluated and reported, but
**only the static variants are eligible for adoption** before the
2027-01-12 unseal.

A live static variant is fitted on the shipped configuration A's predictions
for 2022 to 2025. Those are years the shipped model was not trained on.

**Gate.** Every online variant runs through `cofire/ship/leak_gate.run_gate`
before any of its numbers are reported. The stream's outcomes are derived
from the gate's scores, so perturbing an unobservable row flips its outcome.
A synthetic test shows the gate fails the same variant with its delay
removed.

**Reported:**

- per pair: Brier, reliability, resolution, the paired test, and the adoption
  decision;
- per variant: pooled means;
- the number of h4 and h8 pairs that render the regional base rate today
  because of reliability and would render per-cell odds under the adoption
  rule.

## Stage 2: base rate from slow climate state

**Fixed specification**, no per-target selection: one ridge-penalized
logistic per target, horizon and domain, on domain-week event counts.

- **Response:** events and cells per issue week, binomial.
- **Predictors**, standardized on the fold's training rows:
  - ONI and PDO: the latest monthly value published by issue time, taking a
    month's value as available from the 15th of the following month.
  - April 1 SWE as percent of median, for issue weeks April through October,
    and 0 otherwise. Each station's median is computed from its own April 1
    values in the fold's training years. The domain value is the mean over
    the domain's stations.
  - Season: sine and cosine of day of year.
- **Not included:** the 13-week precipitation deficit. Precipitation for
  2007 to 2017 is not on disk for any domain, and precipitation is not one of
  the sources this session may fetch.
- **Stations:** SNOTEL stations inside each domain's footprint bounding box
  expanded by 0.25 degrees, with April 1 SWE reported in at least 15 of the
  19 years 2007 to 2025. Denver, which has no snowpack of its own, uses the
  union of the Upper South Platte and Dillon stations: its water supply. If a
  box holds no qualifying station, that domain uses the three nearest
  qualifying stations to its centre. The station lists are written to
  `artifacts/v12/stage2_stations.json` before any model is fitted.
- **Ridge grid:** penalty weight 0.1, 1, 10, 100, on the summed binomial
  deviance per domain-week, chosen once by the selection rule.

**Combination with configuration A**, with no further fitted weights:

- **S2-offset:** `p = sigmoid(logit(p_A) + logit(r_hat) - logit(r_A))`.
  `r_hat` is the stage-2 rate for that domain-week, and `r_A` is the mean of
  configuration A's predictions over the domain's cells that week.
- **S2-offset+S1:** S2-offset, then the stage-1 variant selected in stage 1
  (static, so it could ship), warm-started on nested out-of-fold S2-offset
  predictions.

**Reported per pair:**

- the base-rate cost recovered, by the oracle decomposition's definitions
  (`cofire/model/oracle_decomp.py`):
  - base-rate cost = Brier(constant at the training rate) minus
    Brier(constant at the held-out year's true rate);
  - recovered = (Brier(constant at the training rate) minus Brier(constant at
    r_hat)) divided by the base-rate cost;
- the paired test against configuration A, and reliability, for both
  combinations.

## Stage 3: partial pooling across the five domains

**Drought (Markov).**

- **What changes:** only the prior centre and strength of the Dirichlet
  posterior. Configuration A's support gates and fallback order are kept.
- **Centre:** each row's prior is centred on the pooled five-domain row for
  the same condition (category and month, category and season, or category).
  That row is the equal-weight mean of the normalized rows of every domain
  with support for that condition, so Larimer's cells do not outvote
  Denver's. Where no domain has support, the centre is the domain's own
  pooled rates, as in configuration A.
- **Strength:** kappa effective weeks, converted to row counts by the
  domain's number of cells.
- **Grid:** kappa = 4, 16, 64, 256 weeks. At kappa = 4 the centre changes but
  the strength is configuration A's.

**Fire (damped logistic).**

- **Pooled fit:** the same one-feature logistic, fitted on all five domains'
  training rows with each domain weighted equally (row weight 1 / its row
  count).
- **Domain coefficients:** (1 - w) times the domain's own, plus w times the
  pooled.
- **Grid:** w = 0, 0.25, 0.5, 0.75, 1. At w = 0 this is configuration A.

Drought and fire each select their value once, by the selection rule.

**Reported:**

- per pair: Brier, reliability, resolution, the paired test, and adoption;
- the change in survivors: the validation survivor test rerun with the
  selected stage-3 arm in all five domains;
- per-domain reliability;
- the number of estimable targets. Estimability depends on outcomes only, so
  it cannot change; it is reported to show that.

## Stage 4: lag-aware intervals (stretch)

Run only if stages 1 to 3 are complete by 2026-10-16.

- **Arm:** the reference conformal PID with the real delay (`ahead` = h weeks
  of rows, in a stream ordered by issue week then cell) and a fixed step
  (`proportional_lr = False`). Gains as in look 3: LR 0.1, C_SAT 2.0, K_I 1.0,
  T_BURNIN 100. Scores are absolute errors of the configuration A continuous
  point forecast.
- **The configuration passes the delayed-feedback gate**
  (`leak_gate.reference_pid_fixed_step`), checked again before any number is
  reported.
- **Evaluation stream:** 2022-01 to 2025-12 in time order, per domain and
  horizon. Point forecasts come from configuration A's continuous arm fitted
  on 2007 to 2021, which is out of sample for every row and is the live
  configuration. The first 13 weeks are burn-in and not scored.
- **Criteria**, each must pass:
  1. minimum rolling 13-week coverage at least 0.70;
  2. coverage conditional on D0 to D1, and on D2 and above, each within 0.05
     of 0.90;
  3. longest miss run at most 60 consecutive cell-weeks;
  4. the ratio of mean width to the in-fold climatological 5th-to-95th width,
     with a circular block bootstrap CI lying below 1.0.

  The climatological width comes from 2007 to 2021, configuration A's
  `climatological_width`.
- **A band is drawn** for a domain and horizon only if all four pass.
  Otherwise the history-range rendering stays.

## Reporting commitment

Every variant, every grid value and every pair goes in
`artifacts/v12/stage<N>/`, with a summary in `docs/DECISIONS.md`: failures,
non-estimable pairs and gate failures included. A gate failure is reported
with its first mismatch and values, and the stages that depend on it are
skipped.
