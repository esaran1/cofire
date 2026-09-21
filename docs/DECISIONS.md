
## Gate 1: the ESI per-file estimate was wrong by 4.2x

**Decision.** Correct `BYTES_PER_FILE_ESTIMATE` from 1_930_000 to 460_800 for
all *future* ESI fetches. Leave every historical ledger entry exactly as
written.

**Why.** The ESI GeoTIFFs are uncompressed float32 stored in single-row strips
(7200 x 1 x 4 bytes = 28.8 KB per strip). A county-scale window spans ~15 rows,
so a windowed read pulls ~16 strips = 460,800 bytes. The original 1.93 MB was a
guess. Measured from the file's own profile:

    blockxsize=7200 blockysize=1 tiled=False compress=None dtype=float32
    larimer window=25x15 -> 16 strips -> 0.46 MB
    pueblo  window=19x15 -> 17 strips -> 0.49 MB

**Consequence.** The ledger's 2124.7 MB is roughly 4.2x the true spend of about
507 MB. That overcharge is what raised `BudgetExceeded` on the Larimer ESI 12WK
series (207 files, projected 399.5 MB against 375.3 MB remaining). The budget
was never actually exhausted; the bookkeeping said it was.

**On not rewriting the ledger.** Retro-correcting the 1089 historical entries
was attempted and refused as audit tampering, which is correct. A download
ledger is an audit record: its value comes from being what was recorded at the
time. The corrected constant applies going forward, and this entry is the
reconciliation. Anyone reading `data/ledger.json` should treat its total as an
upper bound carrying a known 4.2x overcharge on the 1089 ESI entries.

**Honesty caveat.** 460_800 is still derived from the file layout, not observed
on the wire. True byte measurement was not possible in this environment: the
build has no `osgeo`, so GDAL's network counter is unavailable; `netstat -ib`
exposes only `lo0`; and GDAL's CPL_DEBUG stream could not be captured at either
the Python or the file-descriptor level. `_transferred_bytes()` in `esi.py` now
uses the GDAL counter where a build provides it, and records the estimate with
an "(estimated)" note otherwise, so the two are never confused again.

## Gate 1: ESI 12WK sampling holds only at stride 2

**Decision.** Keep biweekly (stride 2) sampling with linear interpolation. Do
not go coarser to save budget.

**Why.** Tested against the only true weekly 12WK series we hold (Pueblo 2021),
stride 2 gives mae/sd = 0.166 and stride 3 gives 0.195, both inside the 0.20
tolerance. But sub-sampling the biweekly series across all eight years, which
emulates stride 4, fails in 6 of 8 years:

    2018 0.177 PASS   2022 0.211 FAIL
    2019 0.241 FAIL   2023 0.230 FAIL
    2020 0.265 FAIL   2024 0.330 FAIL
    2021 0.206 FAIL   2025 0.163 PASS
    median 0.221, worst 0.330

The stride-3 pass rests on 2021 alone, and 2024 shows the assumption degrades
worst in volatile years, which are exactly the years the model must get right.
One favorable year is not evidence of generalisation.

**Caveat carried into Phase 3.** Stride 2 itself is validated on a single year,
because 2021 is the only year for which weekly 12WK was fetched. The ablation
must therefore report the interpolated-12WK arm as resting on a one-year
tolerance check, not a multi-year one.

## Gate 1: Larimer ESI coverage is elevation-limited, and that is confounded

**Observation.** After the v1 join, ESI 4WK is present on 84.6% of Larimer
cell-weeks but 99.2% of Pueblo's. The gap is spatial, not temporal: no cell is
entirely empty, but per-cell coverage ranges 0.592 to 0.993 in Larimer, and
correlates -0.828 with mean elevation. The worst cells sit at 3100-3400 m in
the Front Range; the best at 1900-2200 m on the plains.

**Why.** ESI derives from ALEXI thermal infrared, which requires clear-sky land
surface temperature retrievals. Persistent snow and cloud over high alpine
terrain leave those pixels legitimately missing. This is a property of the
instrument, not a fetch failure: 0 of 207 requests failed.

**Consequence for the ablation.** ESI availability in Larimer is a proxy for
low elevation. A tree can therefore gain apparent skill from the *missingness
pattern* rather than from the ESI values, because "ESI is present" partly
encodes "this is a plains cell", and plains and montane cells have different
drought and fire climatology. Any Larimer ESI lift must be read with this
confound in mind.

**Guard.** The ablation reports Larimer and Pueblo separately and never pools
them. Pueblo, at 99.2% coverage, is close to a clean test of the ESI signal;
Larimer is not. Agreement across the two domains is the evidence that a lift is
real, which is why the brief requires both. Where Larimer shows lift and Pueblo
does not, the finding is reported as confounded rather than as skill.

## Phase 3: three corrections before any ablation number was believable

The first ablation run reported ROC-AUC 1.000 and Brier skill 0.995 against the
Markov baseline. Nothing about a four-week drought forecast is that easy, so
the number was treated as a symptom rather than a result. Three separate
defects came out of it.

**1. Nine future-dated columns were being used as features.** The regression
feature store carries `usdm_h2/h4/h8`, `erc_pct_h*` and `fire_index_h*`, built
with `shift(-h)`. They are the prediction targets, shifted into the future.
`feature_columns` excluded names starting with `d_` and `f_` but not these.
`usdm_h4` correlated 0.38 with its own target. Excluded by an explicit
`_h\d+$` rule, and AUC fell from 1.000 to about 0.60, which is a plausible
range for this problem.

**2. The effective sample size was computed on the calendar.** `block_bootstrap`
passed the *week labels* to `ar1_neff`. Evenly spaced labels have an AR(1)
coefficient near 1, so `n_eff` reported about 1.5 for 104 weeks regardless of
the data, and would have appeared in every row of the results table. It now
recomputes the statistic per week and measures the autocorrelation of that.
Four tests pin the behaviour.

**3. The Markov baseline was the worst forecast in the comparison.** Its Brier
on Pueblo `d_intensify1_h4` was 0.2245 against persistence at 0.1016 and a
constant at 0.0936. Two causes, one fixed and one recorded:

- Unanimous (category, month) cells produced hard 0.0 and 1.0 probabilities
  under the maximum-likelihood estimate, and `min_count=30` does not prevent
  that. Fixed with Laplace smoothing (alpha=1), the Bayesian estimate under a
  uniform prior rather than a tuned parameter. This moved Brier only 0.2254 to
  0.2245, so it was not the main cause.
- The real cause is a regime shift. Markov over-forecasts intensification by
  2.2x on validation (predicted 0.220, actual 0.102), worst in category 1
  (predicted 0.459, actual 0.170). The training years intensified; the
  validation years did not. The baseline correctly encodes training-period
  transition statistics that no longer held.

**Consequence, and the honest headline.** Ranked by Brier on Pueblo
`d_intensify1_h4`:

    constant at train base rate   0.0936   AUC 0.500
    LightGBM + isotonic           0.1127   AUC 0.598
    LightGBM raw                  0.1577   AUC 0.594
    Markov                        0.2245   AUC 0.515

A constant forecast scores lower Brier than every model. The models carry
real discrimination (AUC 0.598 is meaningfully above 0.5, so they rank cells
correctly) but their
calibration is worse than a constant, and Brier is dominated by calibration on
rare events. Isotonic recalibration narrows the gap without closing it.

The +0.50 "Brier skill against Markov" from the first clean run is therefore
not evidence of skill. It is an artefact of measuring against the weakest
forecast available. `constant_event_baseline` is now part of every comparison
and `bss_vs_constant` is the column to read first in the lift table.

## Phase 3: fire targets have no Markov baseline, by construction

`MarkovBaseline.predict_events` returns only the `d_*` drought keys. It is an
empirical USDM *category transition* matrix, and ERC percentile exceedance is
not a USDM category transition, so there is nothing for it to return. The
ablation therefore records `bss_vs_markov = nan` for every `f_gt*` target.

This is left as `nan` rather than filled. A number there would have to come
from some other baseline, and silently relabelling a different comparison as
"skill against Markov" is exactly the kind of substitution that makes a results
table untrustworthy.

Fire targets are still floored: `constant_event_baseline` and
`climatology_event_baseline` both cover them, and `bss_vs_constant` is the
column the report reads first in any case. The fire rows are therefore scored
against a constant at the training base rate and against per-cell
week-of-year climatology, with the Markov column empty and visibly so.

## Phase 4: PID is not adopted, and the reason is not the one predicted

The pre-registration (`docs/PREREGISTRATION_V1.md`, hash in STATUS.md) predicted
that PID would not help much. That prediction was wrong in an interesting
direction, but the verdict is still **not adopted**, for a procedural reason
that matters more than the numbers.

**Not adopted, because only one domain could be evaluated.** The rule requires
the improvement to hold on both Larimer and Pueblo. Only Pueblo has prediction
parquets: `artifacts/predictions/` holds Pueblo (lat 37.8 to 38.5) and no
Larimer equivalent exists, only archived summary JSON. Pueblo alone meets the
numeric criteria (deviation improves 0.1179, width ratio 0.872), but one domain
passing is the rule being untested, not the rule being met.

**A mislabelling bug was caught on the way.** The first run reported
byte-identical results for both domains. `run_domain` took a `domain` argument
and never used it, reading the same files twice. Two-domain agreement is the
brief's main guard against fitting one geography, so counting one domain twice
would have turned that guard into a rubber stamp while appearing to satisfy it.
`_assert_is_domain` now checks that at least half the rows fall inside the named
domain's bounding box and refuses to report otherwise.

**The substantive finding, on Pueblo only.** At the 8-week horizon both frozen
split conformal and ACI collapse:

    h=8      coverage   mean|dev|   width
    split      0.364      0.553     43.98
    aci        0.363      0.552     43.75
    pid_p      0.899      0.095     85.63
    pid_pi     0.873      0.069     75.90
    pid_full   0.785      0.120     64.66

A 36% realised coverage against a 90% target is a 54-point miss, and ACI is
indistinguishable from the frozen baseline it was supposed to improve on. The
PID arms hold 79 to 90%, and they pay for it: widths roughly double, from 44 to
between 65 and 86. That is the honest trade and it is why width is a
pre-registered secondary endpoint rather than a footnote.

**`pid_full` is the worst PID arm.** Adding the scorecaster makes deviation
worse at every horizon (0.1400 against `pid_pi`'s 0.0718 at h=2 and h=4). The
scorecaster pulls the radius toward the recent median score, which on this data
means pulling it down in calm stretches just before volatility returns. The
pre-registration fixed `pid_full` as the arm compared against ACI, so that is
what the adoption rule used, and the rule is not rewritten after seeing that
`pid_pi` would have looked better. That `pid_pi` is the strongest arm is
recorded here as an observation for a future pre-registration, not as this
session's result.

**What is needed to finish this properly.** Larimer prediction parquets, from a
pipeline run on the Larimer subset. Until those exist the comparison is
single-domain and the verdict stands at not adopted.

## Fix 1: the Markov baseline was broken in three ways, none of them the obvious one

The reviewer's bound is the right diagnostic: a transition matrix conditioned on
(category, month) contains the unconditional rate as a special case, so on its
own training data it cannot score worse. Measured, it did not — training Brier
0.0758 against a constant's 0.1272 — while validation inverted to 0.2245 against
0.0936. The bound held in sample and failed out of sample, which rules out
degenerate 0/1 probabilities (only 0.85% of predictions were near 0 or 1) and
points at overfitting. Three separate causes, found by measurement after two
wrong guesses.

**1. Support was counted in rows, not weeks.** USDM moves in spatially coherent
blocks. Measured on Pueblo training data, 84% of (category, month, week) blocks
are more than 98% unanimous across all 432 cells, so a week carries roughly one
observation rather than 432. Under the row gate, 42 of 47 category-month cells
qualified; under a week gate, 0 of 47 did. `min_count=30` was satisfied by a
single week of one county, and the estimator memorised individual drought
episodes. Support is now counted in distinct weeks.

**2. Rates must still be estimated from rows.** The first repair estimated the
rates from week-weighted counts too, and that broke the bound in the other
direction: every category row sat up to 0.05 off the row rate in a consistent
direction, because weeks with many cells in a category were downweighted in
fitting but not in scoring. Row-level Brier is minimised by the row mean. So the
two units do different jobs: **gate on weeks, estimate on rows.**

**3. The fallback was the unconditional marginal.** With a strict week gate most
cells fall back, and `global_row` is the marginal over *destinations*, which
forgets where the chain started. It told a cell sitting in D2 that D0 was the
most likely next state, because D0 is the commonest state overall. On Larimer,
where every category fell back at a strict gate, that inflated `d_improve1_h2`
Brier by 642% over the constant. Pure persistence is the opposite error: a point
mass states P(category >= 3) = 1 for a D3 cell, which broke the bound on the
absolute-level `d_ge3` targets. The fallback is now a blend, weight 0.75 on
staying put.

**Settings, all selected on validation across both domains, never on the
holdout.** `min_weeks=32` is the largest gate at which neither domain violates
the bound: Pueblo would prefer 48 (0.0892 against 0.0901) but Larimer fails 12
of 18 targets there. `persistence_weight=0.75` is the smallest value at which
Larimer's improve targets satisfy the bound; Pueblo is indifferent across the
whole range.

**Result.** The bound now holds on 18 of 18 drought targets on both domains.
Mean validation Brier is 0.0455 on Larimer and 0.0901 on Pueblo.

**A note on the synthetic fixture.** At 200 weeks it preferred
`persistence_weight=0`, the opposite of what both real domains need, because
that length forced constant fallback and never exercised the estimator. It was
lengthened to 600 weeks rather than used to select the parameter. A fixture that
disagrees with both real domains is measuring its own construction.

**h-step construction was already correct.** Each horizon is estimated from its
own direct `usdm_h{h}` transitions rather than a one-step matrix raised to a
power, so no first-order assumption is imposed.

## Fix 2: class weights removed, Platt replaces isotonic, and a ceiling appears

**Class weighting is gone** from LightGBM (`scale_pos_weight`) and from logistic
regression (`class_weight="balanced"`). Weighting is standard when the goal is
ranking and wrong when the goal is a probability: it moves the output off the
scale Brier scores, by construction. That is what produced AUC 0.598 with a
Brier worse than a constant, which is real discrimination attached to unusable
probabilities.

**Platt replaces isotonic**, fit on pooled out-of-fold predictions from the LODO
folds rather than on one calibration split. Isotonic is non-parametric and needs
many positives per bin; on targets whose base rate is 0.4% it fits the noise in
a handful of events and produces a step function that does not transfer. Platt
has two parameters and cannot chase that noise. Measured on Pueblo
`d_intensify1_h4`, it cuts reliability from 0.0409 to 0.0174 and Brier from
0.1310 to 0.1072.

**But it overshoots, and the reason is not fixable by calibration.** Platt lands
at mean prediction 0.2257 against an actual 0.1015, because the pooled
out-of-fold base rate is 0.1771 and the validation year's is 0.1015. The
calibrator is correctly fit to the years it saw. Those years simply ran
differently. The base rate of `d_intensify1_h4` on Pueblo by year:

    2018 0.1948   2020 0.1771   2022 0.1230   2024 0.0114
    2019 0.0755   2021 0.1315   2023 0.0802   2025 0.0673

A 17x range, with no trend to extrapolate. On a rare event Brier is dominated by
calibration, and calibration is dominated by the base rate, so this swing sets a
ceiling on what any method fit to past years can achieve.

**The ceiling, measured.** Giving LightGBM an oracle calibrator that knows the
true validation base rate, which is not available in practice:

    constant at train rate    brier 0.0931  rel 0.00190  res 0.00000  auc 0.500
    constant at TRUE rate     brier 0.0912  rel 0.00000  res 0.00000  auc 0.500
    lgbm raw                  brier 0.1310  rel 0.04094  res 0.00047  auc 0.607
    lgbm oracle-calibrated    brier 0.0907  rel 0.00020  res 0.00109  auc 0.607

Discrimination is worth 0.0005 Brier once the base rate is known. Not knowing
the base rate costs 0.0019, four times more. The models do carry signal, and
that signal is smaller than the year-to-year base-rate uncertainty it has to
overcome. This is a property of the problem at this sample size, not a defect
left to fix, and the ablation should be read against that ceiling rather than
against zero.

## Fix 3: equal row sets, and the restriction is not free

Every arm, the gridMET-only arm included, is now restricted to rows where every
source group is present, so a group's lift cannot be confounded with how many
rows it was fit on. The unrestricted gridMET-only arm is reported beside it as
`gridmet_full_record`.

The restriction matters more than expected. On Pueblo `d_intensify1_h4` the
restricted gridMET arm scores Brier 0.1030 against the full-record arm's 0.1258.
The ESI-era rows are genuinely easier, so comparing an ESI arm against the
full-record baseline would have credited ESI with a difference that belongs to
the sample. On Pueblo the restriction keeps 99.2% of rows; on Larimer, where ESI
coverage is elevation-limited, it will cost considerably more, and that cost is
reported rather than hidden.
