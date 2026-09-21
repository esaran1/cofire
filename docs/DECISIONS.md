
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

## The ledger: corrected to measured bytes, by appending rather than rewriting

**What the true figure is.** 555136 bytes per windowed ESI read, measured by
issuing the exact byte ranges and counting what came back: 17 strips of 28800 B
plus the 65536 B header GDAL reads before anything else. Larimer's window is one
strip narrower at 526336 B; the larger figure is used so projections stay
conservative.

Three estimates have now been in the ledger, and all three are preserved in the
entries that used them:

    1930000 B  original guess, 3.5x too high
     460800 B  strip count, correct but omitting the header
     555136 B  measured over the wire

**Recorded 2330.0 MB, true 862.9 MB, residual error 0.0 MB.** The overcharge was
withholding about 1.6 GB of real headroom, which is what blocked the Larimer
12WK series earlier and what would have blocked the 2010 backfill.

**Why the entries were not rewritten.** An earlier attempt to retro-correct the
1089 historical entries was refused as audit tampering, and that refusal was
right. A download ledger is only worth keeping if it says what was recorded at
the time. So `add_correction` appends a dated adjustment carrying its reason and
its evidence, and the file serialises `recorded_bytes`, `correction_bytes` and
`total_bytes` separately. A reader can see both what was charged and what it
should have been, and can check the arithmetic.

**A caveat on what "measured" means here.** The bytes are measured at the
protocol level: the ranges a windowed read requires, fetched deliberately and
counted. GDAL's own network counter was unavailable in this build, and the
sandbox exposes only `lo0`, so this is not an observation of GDAL's actual
socket traffic. If GDAL issues extra probes the true figure is slightly higher.
The projection is conservative in the other direction by using the larger
domain, and the whole backfill fits with about 1 GB to spare, so the residual
uncertainty does not change any decision.

## The ESI cache was not keyed by start year

The first 2010-onward backfill reported `cache hit` for all four series and
transferred nothing, because `_out_path` keyed only on product and stride. An
extended fetch therefore silently returned the shorter cached series. The start
year is now part of the key, with 2018 keeping the existing paths so no refetch
was needed.

This is the same class of bug as the subset-scoping failure in v0.6, where a
Pueblo fetch re-served Larimer geography: a cache key that omits a dimension the
data actually varies along. Worth noting because it is the third time this
project has hit it.

## CFSv2 forecast weather: archive exists, subsetting does not, so it is dropped

Phase 1 never actually investigated this, so it was checked now rather than
reported from memory.

**A historical archive does exist.** The NOAA CFS public S3 bucket
`noaa-cfs-pds` carries forecast runs keyed by issue date from **2018-10-31 to
2026-09-20**, covering most of the training record:

    https://noaa-cfs-pds.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=cfs.

    cfs.20181031/ ... cfs.20260920/     forecast runs, by issue date
    cdas.20230422/ ...                  analysis, rolling, starts 2023

Each issue holds 6-hourly GRIB2 with `.idx` sidecars giving per-record byte
offsets, so individual variables can be range-read:

    cfs.20200101/00/6hrly_grib_01/flxf2020010100.01.2020010100.grb2   4.27 MB
    record 5   TMP:surface        90679 B
    record 31  PRATE:surface      41105 B
    record 45  PEVPR:surface      ~40000 B

**But the records are global.** A GRIB record is one variable over the whole
planet, so a range read retrieves a global field, not a Colorado subset. Priced
for weeks 1 to 4 of the four variables named in the brief:

    4 variables per 6-hourly step        256 KB
    112 steps per issue (28 days)         28.6 MB
    375 weekly issues, 2018-11 to 2025-12  10.74 GB single member
                                           42.97 GB four members

**The spatial subsetting service cannot reach the training years.** NOMADS
`filter_cfs_flx.pl` accepts a `subregion` with lat/lon bounds and would cut this
to a few kilobytes per field, but it returns HTTP 403 for a 2020 issue date:
"This data has expired and is no longer available." It serves only recent runs.

**Decision: dropped.** 10.74 GB is more than four times the entire session
budget and about eight times the true remaining headroom, for the cheapest
single-member configuration. There is no route to a cheaper one: the archive
that has the history will not subset, and the service that subsets does not have
the history.

**What this costs, stated plainly.** The fire exceedance targets at h >= 4 have
no physical source of skill without forecast weather. Four-week and eight-week
ERC percentile exceedance is largely determined by weather that has not happened
yet, and the model sees only antecedent conditions. Any apparent skill on
`f_gt90_h4` and `f_gt90_h8` should be read as persistence of fuel state, not as
weather forecasting, and the reported numbers for those targets should be
interpreted with that ceiling in mind.

## The fire targets were one target under three names

`f_gt80`, `f_gt90` and `f_gt97` had **identical** values at every horizon.

The cause is in `erc_pct`, which is a percentile of ERC against that cell's own
week-of-year training distribution. The distribution held one value per training
year, about **4 values**, and a percentile against 4 points can only return 0,
25, 50, 75 or 100. Across the whole feature store `erc_pct` took **9 distinct
values**, and 17.1% of them were exactly 100, so every threshold above 80
selected the same rows.

Fixed by pooling a circular +/- 3 week window when building the percentile
climatology, giving about 28 values per cell-week. Measured after the rebuild:

    distinct erc_pct values   9      ->  69
    fraction exactly 100      0.171  ->  0.031
    f_gt80_h4 rate            0.173  ->  0.189
    f_gt90_h4 rate            0.173  ->  0.101
    f_gt97_h4 rate            0.173  ->  0.053

The rates now nest properly. Anomaly moments (fm100, fm1000, tmmx) stay on the
single week: they are means rather than order statistics, so 4 values is
adequate and widening them would blur a real seasonal signal.

This invalidates every previously reported fire-target number. They were all
measuring the same 17% exceedance event.

## Seasonal climatology is a worse baseline here, and the reason is the finding

The reviewer is right that a flat constant would credit a model for knowing the
calendar, and these targets are seasonal *within* a year: on Pueblo the monthly
rate of `f_gt90_h4` varies 4.5x and `d_intensify1_h4` 11.6x.

But a week-of-year climatology fitted on training years scores **worse** than
the flat constant on 24 of 27 targets. The reason is that the seasonal shape
does not repeat. Correlation between the training and validation week-of-year
profiles:

    median -0.030, positive on 9 of 27 targets
    d_ge2_h4  -0.893      d_ge2_h8  -0.869
    d_nochange_h8 +0.663  d_nochange_h4 +0.393

`d_ge2_h4` is the clearest case: training peaks in summer at 0.66 where
validation is 0.000, and training sits at 0.045 in week 7 where validation is
0.902. The two profiles are near-perfectly anti-correlated.

**Interpretation.** What looks like a seasonal cycle within any one year is a
drought episode that happened to occupy that part of that year. Drought in
Colorado is not a calendar phenomenon at this sample size; it is an episodic one
whose timing varies. Fitting a week-of-year profile on four training years
imports the timing of those specific episodes.

`d_nochange` is the exception, and consistently so: it is the complement of
anything happening, so it tracks the genuinely seasonal quiescent period rather
than episode timing.

**Decision.** `seasonal_climatology_baseline` is implemented and reported for
every target, because the reviewer's concern is legitimate and the reader should
see the number. But the **flat training constant stays the primary reference**,
since it is the harder opponent on 24 of 27 targets, and a skill score is only
honest against the strongest available baseline. Reporting against seasonal
climatology as primary would inflate every BSS in the table.

## Forecast weather, checked properly this time

The first check used `noaa-cfs-pds`, raw global GRIB, which was never the
intended product. The reviewer named three better sources. All three were
checked.

**1. Climatology Lab CFSv2-gridMET: exists, but carries no historical issues.**

The product is real and is the right one: CFSv2 downscaled onto the gridMET
4 km grid, served over OPeNDAP at

    https://thredds.northwestknowledge.net/thredds/dodsC/
      NWCSC_INTEGRATED_SCENARIOS_ALL_CLIMATE/bcsd-nmme/dailyForecasts/
      bcsd_nmme_metdata_CFSv2_forecast_{pr,pet,tasmax,tasmin,...}_daily.nc

Grid 585 x 1386, which is CONUS at gridMET resolution, exactly the grid already
in use. But the time axis is **212 consecutive days, 2026-10-01 to 2027-04-30**:
one live forecast run, overwritten each cycle, with no issue-date dimension. The
file server has `RangelandForecast/data/hindcasts/` and `.../forecasts/`, and
**both directories are empty**. The THREDDS root carries seven sub-catalogs
(MACA, TerraClimate, downscaled scenarios) and none is a forecast archive. The
2011-2021 hindcasts from the skill study are not published here.

**2. NMME at the IRI Data Library: has issue dates, wrong years.**

Data requests work without authentication; only the HTML browse UI redirects to
a login. A Colorado box comes back subset server-side, as the reviewer expected:

    .NCEP-CFSv2/.HINDCAST/.MONTHLY/.prec  X -109/-102  Y 37/41
    dims S=348 L=10 M=24 Y=5 X=8          13.4 MB

`S` is the forecast issue dimension, 348 monthly issues. But it runs
**1982-01 to 2010-12**, and `.MONTHLY` is the same range. CFSv2 has no
`.FORECAST` or `.REALTIME` series at IRI: both return 404 while
`CanSIPS-IC4/.FORECAST` returns data, so the pattern is right and CFSv2 simply
does not have one. CanSIPS itself covers only 2024-07 onward, 27 issues, and is
a different model.

The training window is 2018 onward. A hindcast archive ending in 2010 cannot be
joined to it.

**Cost of the gap, restated.** Fire exceedance at h >= 4 still has no forecast
weather behind it. With the percentile fix the three fire thresholds are now
genuinely distinct targets, so this matters more than it did when they were one
target: `f_gt97_h8` at a 5.3% base rate is being asked to anticipate weather
eight weeks out from antecedent conditions alone.

**3. SubX at the IRI Data Library: this one covers the training window.**

    .SubX/.NCEP/.CFSv2/.hindcast/.pr    S = 27389 issues, 1999-01-01 .. 2017-09-30
    .SubX/.NCEP/.CFSv2/.forecast/.pr    S issues,         2017-10-15 .. 2026-09-20

The `.forecast` series begins the day after the hindcast ends and runs to the
present, so together they cover the whole training record and the sealed 2026
holdout. `S` is a true forecast-issue dimension with roughly daily issues,
leads run to 44 days, and the server subsets in the URL. A both-domain box for
January 2020 at leads 0 to 28 came back correctly shaped:

    dims S=125 M=4 L=29 Y=4 X=3      698 KB in 113 s

**Priced.** 96 months from 2018-01 to 2025-12: 67 MB per variable, 134 MB for
two, against 385 MB of true remaining budget. The bytes fit comfortably.

**The binding constraint is wall time, not bytes.** At 113 s per month-request,
two variables is about 6 hours of requests. The standing rule is no single stage
over 60 minutes, so this needs staging and checkpointing across several runs
rather than one ingest, and it cannot be finished inside the remaining session
time alongside the analysis sequence.

**A caution found while pricing it.** The IRI server returns **HTTP 200 with an
HTML error page** for a malformed path: a wrong `M/average` ordering produced
1488 bytes, status 200, that turned out to be "Error 404: Bad Request". A byte
count alone would have passed it. Any ingest here must verify that the payload
actually opens as NetCDF before recording it in the ledger.

Server-side ensemble averaging was tried as a way to cut the cost and does not
help: `[M]average` over a single quarter timed out at 280 s having returned
nothing, against 113 s for a full month of all four members. The aggregation
costs more than it saves, so the 6 hour figure stands.

**Status: found, priced, not ingested in this session.** This is the source a
future session should use, and the reviewer was right that the product mattered:
the raw-GRIB check was against the wrong thing, and the correct sources were
reachable all along.

## The two-stage result: stage 1 works where the diagnostic said it would

The oracle decomposition named, per target, whether the remaining Brier gap was
base rate or discrimination. Stage 1 predicts the level from slow climate state.
If the diagnostic is sound, stage 1 should help on the base-rate targets and
hurt on the others. That is exactly what it does:

    dominant term    n    median recovery    lower Brier than constant
    base_rate       35        +0.700             11/35
    discrimination  16        -0.883              1/16

Median recovery across all 51 is +0.458, and two-stage scores lower Brier than
single-stage on 30 of 51, and lower than the constant on 12 of 51 against 5 of
51 for the single-stage model. Imposing a level on a target whose level was
never the problem costs skill, which is why the negative half of that table is
a confirmation rather than a disappointment.

**But almost none of it is separable from noise.** Only 4 of 51 targets have a
block-bootstrap interval excluding zero:

    pueblo  d_ge2_h2        BSS +0.3386  [+0.229, +0.447]  n_eff_weeks  25.2
    larimer d_intensify2_h8 BSS +0.0636  [+0.018, +0.174]  n_eff_weeks  13.4
    larimer d_intensify2_h4 BSS +0.0363  [+0.009, +0.140]  n_eff_weeks  27.8
    larimer d_intensify2_h2 BSS +0.0092  [+0.002, +0.954]  n_eff_weeks 108.6

The effective sample sizes are the reason. Thirteen effective weeks cannot
support a confident claim, and that number is honest only because `ar1_neff`
was fixed earlier in this session: it previously reported about 1.5 for any
input, computed on the calendar rather than the data.

**Predictor selection is spread evenly**, which is itself informative. Across
51 fits: pdo 23, pr_deficit_12w 21, oni 19, esi_12wk 18, swe_pct_median 17. No
predictor dominates, which is what one expects when each carries a little signal
and the selection is largely choosing among noise. The four-predictor cap was
fixed before fitting and is doing real work here.

**Honest summary.** The mechanism is real and the diagnostic predicted where it
would help. The magnitude, on this sample, is mostly indistinguishable from
zero. `d_ge2_h2` on Pueblo is the one clear exception at BSS +0.34 with an
interval well clear of zero, and it is also the target with the largest
base-rate swing, which is consistent with the rest of the picture rather than
a surprise.

## The confirmation pass: what survives when the references are right

Five corrections were applied together, because each changes what the numbers
mean and applying them one at a time would have invited reading the most
favourable intermediate state.

**The earlier two-stage table used the wrong reference.** Its BSS was against a
flat training constant (`two_stage.py`, `ref = brier(const[m], y[m])`).
`brier_seasonal` was computed and stored but never used. Seasonal climatology is
now primary, and every target also carries persistence, Markov and constant.

**Per-target predictor selection is gone.** Selection frequencies of 17 to 23
across five predictors over 51 fits is a search ranking noise. One fixed
specification is used everywhere: all five slow predictors plus season,
ridge-penalised, with a single penalty chosen once on pooled LODO across every
target and both domains. The selected penalty is **100**, which is heavy
shrinkage and is itself a statement about how little signal the predictors
carry.

**The rare-event bootstrap was reporting meaningless intervals.** Larimer
`d_intensify2_h2` has **3 positive domain-weeks out of 104**, and its
unstratified interval came out as [+0.002, +0.954]. Positive and negative weeks
are now resampled separately to their own counts, and a target with fewer than
12 positive weeks is reported **not estimable** rather than given a number. This
removed 11 of 51 targets, including three of the four that previously appeared
to separate.

**Multiplicity is controlled.** Holm within each event family, where horizon
variants of one event are a family, then Benjamini-Hochberg at q=0.10 across
what survives. A negative skill score is never a discovery regardless of its
p-value.

### Result

    51 targets -> 40 estimable -> 13 survive BH -> 9 clear every baseline

The four that survive BH but fail a baseline are informative:

    larimer d_nochange_h2/h4/h8   markov -0.217, -0.359, -0.515
    pueblo  d_intensify2_h8       persistence -0.021

`d_nochange` is the persistence-dominated case the review predicted: the model
clears climatology while losing badly to a transition matrix that already knows
how sticky drought categories are. Reporting it as skill would have been wrong.

### The nine, with every baseline

    domain   target            h   seasonal [95% CI]        persist  markov  posWk
    pueblo   d_intensify1_h4   4   +0.1558 [+0.070,+0.262]   +0.105  +0.066    42
    pueblo   f_gt80_h2         2   +0.1215 [+0.034,+0.229]   +0.318     n/a    37
    pueblo   f_gt80_h4         4   +0.1110 [+0.022,+0.243]   +0.397     n/a    36
    pueblo   f_gt80_h8         8   +0.1041 [+0.029,+0.210]   +0.420     n/a    35
    larimer  f_gt97_h4         4   +0.0993 [+0.052,+0.189]   +0.451     n/a    27
    larimer  f_gt97_h2         2   +0.0901 [+0.046,+0.178]   +0.414     n/a    28
    larimer  f_gt97_h8         8   +0.0883 [+0.052,+0.153]   +0.449     n/a    25
    larimer  d_intensify1_h2   2   +0.0691 [+0.026,+0.133]   +0.006  +0.157    20
    larimer  f_gt90_h8         8   +0.0531 [+0.018,+0.096]   +0.419     n/a    40

### Two caveats that belong with the table

**`d_intensify1_h4` does not agree across domains**: +0.1558 on Pueblo against
**-0.5357** on Larimer. The standing two-domain rule treats disagreement as
evidence of fitting one geography, so it is excluded from the look-3 set despite
being the largest surviving effect.

**The fire targets have no Markov reference**, so they clear three hurdles where
the drought targets clear four. They also have no forecast weather behind them,
since SubX was found but not ingested. Their skill against persistence is large
(+0.32 to +0.45) because persistence is a weak forecast for an exceedance
target, and their skill against climatology is the number that matters.

## The library replacements overturned the result

This is the most consequential correction in the session. The eight-target
pre-registration submitted for look 3 does not survive it, and that
pre-registration is withdrawn.

**BH and Holm were correct.** `benjamini_hochberg` and `holm` agree with
`statsmodels.stats.multitest.multipletests` on every case tested, including the
step-up and step-down edge cases. No result changes.

**The block bootstrap was understating uncertainty.** The hand-rolled version
resampled whole weeks independently with replacement. That is a valid block
bootstrap only if weeks are exchangeable, and in a drought series they are not:
what matters is runs of consecutive weeks. `arch.bootstrap.CircularBlockBootstrap`
resamples blocks of consecutive weeks, wrapping at the series end, and produces
materially wider intervals:

    domain   target           h   custom              circular block
    larimer  d_intensify1_h2  2   [+0.026, +0.133]    [-0.007, +0.290]
    larimer  d_nochange_h8    8   [+0.003, +0.085]    [-0.035, +0.119]
    larimer  f_gt90_h8        8   [+0.018, +0.096]    [-0.004, +0.136]
    pueblo   f_gt80_h2        2   [+0.034, +0.229]    [-0.020, +0.370]
    pueblo   f_gt80_h4        4   [+0.022, +0.243]    [-0.042, +0.389]
    pueblo   f_gt80_h8        8   [+0.029, +0.210]    [-0.024, +0.322]

**Six of thirteen conclusions flip.** Every flip is from significant to not
significant. The point estimates are unchanged, because the statistic on the
full series does not depend on the resampling scheme; only the uncertainty was
wrong, and it was wrong in the flattering direction.

**Effective sample size also changes**, because `neff_from_acf` sums the
observed autocorrelations instead of assuming AR(1). On the surviving targets it
moves from a custom 20.1 to 52.7 into a library 19.4 to 36.7. Neither is
uniformly larger: a 20-point moving average, where autocorrelation terminates at
lag 20, gets n_eff 19.8 from the ACF estimator against 10.6 from AR(1), because
the AR(1) fit implies a geometric tail the series does not have. The ACF version
is the better estimate and is now what the pipeline reports.

### What is left

    13 survived BH under the custom bootstrap
     7 still separate under the circular block bootstrap
     4 of those also clear every applicable baseline
     3 after two-domain agreement

The three are `f_gt97` on Larimer at h2, h4 and h8. `d_intensify1_h4` clears the
bootstrap and the baselines at +0.1558 on Pueblo but scores -0.5357 on Larimer,
so the two-domain rule excludes it. `d_nochange_h2` and `d_nochange_h4` clear
the bootstrap but lose to Markov by -0.217 and -0.359, and `d_intensify2_h8`
loses to persistence at -0.021.

**The lesson is about the direction of the error.** A hand-rolled statistic
that is wrong tends to be wrong in the direction that makes the work look
better, because that is the direction in which a mistake is not investigated.
The custom bootstrap was tested, and its tests passed, and it was still wrong
about the thing that mattered.

## The fire transition baseline absorbs every fire result

Two baselines were added for the fire targets, both with the corrections the
drought Markov baseline needed: support counted in weeks, rates estimated from
rows, a blended fallback.

- **Fire transition**: exceedance rate at t+h by current ERC decile and season,
  pooled across cells, gated at 32 independent weeks.
- **Damped persistence**: a logistic regression on the current ERC percentile
  alone. Two parameters.

Both satisfy the training bound against the constant on 18 of 18 fire targets.

**Result: 0 of 18 fire targets clear the transition baseline with an interval
above zero.** Only 4 of 18 have a positive point estimate at all.

The three Larimer `f_gt97` targets that were the entire remaining survivor set:

    target       vs seasonal   vs transition   vs damped persistence
    f_gt97_h2      +0.0901        +0.0039           -0.0457
    f_gt97_h4      +0.0993        -0.0046           -0.0162
    f_gt97_h8      +0.0883        -0.0047           -0.0097

The apparent skill against seasonal climatology was the model learning that fire
danger persists. A two-parameter logistic on today's ERC percentile captures it
and then some.

**`f_gt80` on Larimer is significantly worse than the transition baseline** at
all three horizons, with intervals entirely below zero: -0.1976 [-0.302, -0.044]
at h2, -0.1444 [-0.229, -0.017] at h4, -0.1071 [-0.180, -0.019] at h8. The
model is actively worse than the decile table there.

## Survivor count under the agreed definition: zero

The agreed definition is the same target passing BH/Holm and every baseline in
**both** domains. Checked explicitly:

`f_gt97` **does not pass on Pueblo**. It is not estimable there, with 6 to 7
positive weeks against the 12-week floor, so no interval exists and it cannot
pass BH. The three Larimer `f_gt97` results have no counterpart.

Combined with the fire transition result above, which removes them on their own
domain as well, **the survivor count is 0**.

There is currently no target on which this model demonstrates forecast skill
over an appropriate baseline in both domains.
