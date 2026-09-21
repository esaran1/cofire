
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
