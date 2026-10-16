
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

## The reference conformal PID is better than the custom one on every metric

Run on identical score streams, calibration plus validation, 2026 never opened.
The reference is `quantile_integrator_log` from
`aangelopoulos/conformal-time-series`, the paper's quantile-plus-integrator
method with log saturation.

    h  implementation              coverage   width   longest miss run
    2  custom pid_p                 0.9007    87.66        168
    2  reference                    0.8986    72.79         21
    4  custom pid_p                 0.9003    90.03        288
    4  reference                    0.8989    74.42         13
    8  custom pid_p                 0.8990    85.63        209
    8  reference                    0.9030    72.00         31
    8  custom aci                   0.3630    43.75       1780

The reference holds the same nominal coverage at roughly **18% narrower
intervals**, and its longest run of consecutive misses is an order of magnitude
shorter: 13 to 31 against 145 to 288. The miss-run figure is the one that
matters operationally, because a forecast that is wrong for 288 consecutive
cell-weeks is unusable however good its average coverage looks.

**Why the custom version is worse.** Two differences. The reference saturates
the integrator through a tangent of a log-scaled argument, which grows without
bound as the error accumulates, where the custom `_saturate` is bounded at 10
and so stops responding once it is saturated. And the reference scales its
learning rate by the observed score range in a trailing window, so it adapts to
the scale of the residuals instead of using a fixed step.

**Decision: ship the reference implementation.** It wins on every metric at
every horizon, which is not a close enough call to need a tie-break rule.

**What survives of the PID finding.** The substantive claim was that ACI
collapses at h8 while a PID controller holds coverage. That claim holds, and
holds more strongly under the reference: ACI reaches 0.3630 coverage with a
1780-week miss run, against the reference's 0.9030 and 31. The direction of the
result is confirmed; the custom implementation was simply a poor version of it.

This is now the only positive methods result left in the project, and it
survived being checked against the authors' code.

## The operational benchmarks cannot be scored: neither archive exists

Both were checked directly rather than assumed.

**CPC Drought Outlooks.** Three candidate archives:

    ftp.cpc.ncep.noaa.gov/GIS/droughtlook/    dated shapefiles, DO_polygons-YYYYMMDD.zip
                                              92 issues, 2009-10-01 to 2013-07-18
    ftp.cpc.ncep.noaa.gov/GIS/NIDIS/mdo/      MDO_GIS.zip, 209 MB, last modified 2019-08-10
    ftp.cpc.ncep.noaa.gov/GIS/NIDIS/sdo/      SDO_GIS.zip, same structure

The dated archive is real and has the right structure, but it **ends in July
2013**, five years before the training window opens.

The NIDIS zips are a single file geodatabase, not an archive. Opened and
inspected: 11 layers, of which `DO_Merge` carries exactly the right schema,
`FID_improv`, `FID_persis`, `FID_dev`, `FID_Remove`, which are the four outlook
categories. But it holds **25 rows with `Fcst_Date` and `Target` both empty**:
one undated outlook, a map-production artifact rather than a time series. The
2019 modification date says it has not been updated in seven years.

**NIFC Predictive Services.** The monthly significant wildland fire potential
outlook is published as **PDF only**, at a fixed URL that is overwritten each
month:

    nifc.gov/nicc-files/predictive/outlooks/monthly_seasonal_outlook.pdf

No shapefile, no GeoJSON, no ArcGIS REST service, and no dated archive. There is
nothing to rasterize and nothing to score across a record.

**Consequence.** The per-target winner table cannot include the operational
products. The comparison the review wanted, which is the right comparison, is
not available from published data for the training years. What can be said is
that our model does not clear the appropriate statistical baselines, so the
question of whether it clears the operational products is moot: something that
loses to a decile lookup table is not a candidate to replace an expert forecast.

The app should therefore not display a model forecast for these targets. It
should link to the operational products, which is what a user should be reading
anyway.

## The shipping layer: empirical conditional models, reference PID for intervals

What ships is the baseline, because the baseline is what survived. The ML arms
stay in the repo and in the ablation results and are not in the serving path.

**Step 1, frozen per target on pooled LODO** (`artifacts/shipping/choices.json`):

    family counts   markov 18, transition 6, damped 3
    pooled wins     21 of 27

Drought targets all ship the fixed Markov model. Fire targets split: the ERC
decile transition table wins 6 and the damped-persistence logistic wins 3, and
the damped logistic wins precisely where the target is rarest, `f_gt97` at h4
and h8 and `f_gt80` at h8, which is where a decile table runs short of events
per cell. Pooling across domains with an indicator wins 21 of 27, consistent
with the unanimity finding: two domains are two independent series, and doubling
them matters more than the row count suggests.

**Worth stating plainly: several shipped targets have resolution 0.000000.**
`d_intensify1_h2`, `d_intensify2_h2`, `d_intensify2_h4` and `d_intensify2_h8`
ship as essentially climatology. They carry reliability but no discrimination.
The Place Card must not present those as a forecast that distinguishes one cell
from another, because it does not.

**Step 2, reference conformal PID in the shipping path.** The authors'
implementation is vendored byte-identical at
`cofire/model/uncertainty/reference_pid.py`, exempted from ruff and mypy so it
stays that way, and wrapped by `shipping_pid.py` where the project-specific
parts live. `pid.py` is kept as the comparison arm.

LODO coverage against a nominal 0.90, on the calibration and validation stream
with 2026 never opened:

    horizon  fold  coverage  width  longest miss run
    2        all     0.8986  72.79        21
    2        2024    0.8966  69.33        34
    2        2025    0.8991  74.90        20
    4        all     0.8989  74.42        13
    4        2024    0.8984  71.77        20
    4        2025    0.8976  77.04        34
    8        all     0.9030  72.00        31
    8        2024    0.9042  69.78        14
    8        2025    0.9016  76.82        20

Every fold is within 0.005 of nominal. ACI on the same streams gives 0.8938 at
h2, 0.9326 at h4 and 0.3630 at h8, with miss runs of 360, 212 and 1780.

**A limitation on this table.** Only Pueblo has prediction parquets, so these
are Pueblo figures. The Larimer equivalent needs a pipeline run that has not
happened, and the look-3 pre-registration must either state Pueblo only or wait
for that run. It cannot claim both domains on this evidence.

## The PID table wrapped the wrong forecast, and fixing it improved the result

**What the first table measured.** The residual streams came from
`ensemble_calibrate.parquet` and `ensemble_valid.parquet`, written by
`train.py` from the `ensemble` arm, which blends LightGBM with the PI-ConvLSTM
variants. Checked rather than assumed: `erc_pct_h4_hat` correlates 0.4844 with
`erc_pct` and spans 30.2 to 77.6 against the observed 0 to 100, which is a
fitted regressor shrinking toward the mean, not persistence.

So PID was wrapping an ML forecast that is no longer shipped. The table was
measuring intervals around a point forecast nobody will see.

**The continuous analogue of step 1**, chosen once on pooled LODO MAE:

    h=2  damped_regression    h=4  damped_regression    h=8  decile_mean

`damped_regression` is the least-squares analogue of the damped-persistence
logistic: regress the future percentile on today's, one predictor. `decile_mean`
is the conditional mean by current decile and season, the analogue of the
transition table, and it wins at the longest horizon where today's value has
decayed most.

**Reference PID on the shipped streams, both domains:**

    domain   h  arm                 coverage  width  miss run   MAE
    larimer  2  damped_regression     0.8991  72.83      9     23.94
    larimer  4  damped_regression     0.8990  75.33     18     24.85
    larimer  8  decile_mean           0.8995  79.77      8     25.95
    pueblo   2  damped_regression     0.8991  59.95     19     21.38
    pueblo   4  damped_regression     0.8987  64.97     11     23.59
    pueblo   8  decile_mean           0.8989  70.89     10     25.61

Every cell is within **0.0013** of nominal 0.90, with longest miss runs of 8 to
19. That is tighter than the ensemble-stream table, which ran 0.8966 to 0.9042
with runs to 34.

ACI on the same streams: 0.9320, 0.8961, 0.8057 on Larimer and 0.9019, 0.5970,
0.6887 on Pueblo, with miss runs reaching 930 and 1860. The h8 collapse is not
a Pueblo artefact; it appears on Larimer too, at 193.

**This also removes the Larimer blocker.** The shipped forecast is computed
directly from the feature store, so it needs no prediction parquets and no ML
pipeline run. Both domains now have PID coverage on the forecast that actually
ships, which is what the look-3 pre-registration needs.

## Step 1 by domain, under the frozen family choices

The family per target stays exactly as frozen; nothing was reselected per
domain. What changes is only which domain the LODO score is computed on.

    target            h  family      Brier_lar  Brier_pue   Res_lar   Res_pue
    d_ge2_h2          2  markov        0.07999    0.04775   0.16729   0.17016
    d_ge2_h4          4  markov        0.12794    0.08998   0.13329   0.12975
    d_ge2_h8          8  markov        0.16973    0.18832   0.12952   0.05707
    d_ge3_h2          2  markov        0.04398    0.04804   0.09416   0.05133
    d_ge3_h4          4  markov        0.05900    0.08533   0.09727   0.02650
    d_ge3_h8          8  markov        0.10173    0.11924   0.08826   0.00567
    d_nochange_h4     4  markov        0.15401    0.19141   0.03544   0.01929
    d_nochange_h8     8  markov        0.22508    0.26939   0.03490   0.04686
    d_improve1_h8     8  markov        0.03511    0.10762   0.00002   0.04374
    f_gt80_h2         2  transition    0.19889    0.25173   0.00600   0.00887
    f_gt90_h8         8  transition    0.14498    0.14710   0.00343   0.00724
    f_gt97_h8         8  damped        0.09427    0.05857   0.00488   0.00062

(Full table in `artifacts/shipping/step1_by_domain.csv`.)

**Eight targets have zero resolution in at least one domain, not four.** The
pooled figures reported earlier hid Larimer-specific failures:

    d_intensify1_h2   lar 0.000000  pue 0.000000
    d_intensify2_h2   lar 0.000000  pue 0.000000
    d_intensify2_h4   lar 0.000000  pue 0.000000
    d_intensify2_h8   lar 0.000000  pue 0.000000
    f_gt97_h2         lar 0.000000  pue 0.000946
    d_intensify1_h4   lar 0.000000  pue 0.003613
    f_gt97_h4         lar 0.000000  pue 0.000159
    d_intensify1_h8   lar 0.000000  pue 0.012560

Every `d_intensify` target has zero resolution on Larimer at every horizon. The
Markov model there predicts the same intensification probability for every cell,
which is what a transition matrix does when the conditioning variable carries no
within-domain variation that survives the week gate.

**Consequence for the product.** The zero-resolution list is domain dependent, so
the Place Card rule cannot be a fixed list of four target names. It must read
the per-domain resolution from `step1_by_domain.csv` and render a regional base
rate wherever resolution is zero for the domain being displayed.

**The resolution figures also bound what look 3 can test.** A target with zero
resolution has no discrimination to confirm, so it can only be scored for
calibration, which is what the pre-registration says.

## A unit error in the climatological width, caught by a dimensional argument

The reviewer spotted it from first principles: PID widths were 89 to 95 in
`erc_pct` units while the climatological width read 33 to 37, and a week-of-year
relative percentile has a near-uniform marginal, so its 5th-to-95th width must
be near 90. Two quantities in the same units cannot differ that way.

**The variable was right and the grouping was wrong.** The width was computed on
`erc_pct_h{h}`, the correct column, grouped by `(cell_id, week_of_year)` on a
*single* week. That group holds about **three** training values per cell, and the
5th and 95th percentiles of three values are its minimum and maximum:

    single week, 3 values per cell    50.6
    pooled +/- 3 weeks                81.2
    cross-cell marginal               91.4

The reported 33 to 37 was lower still because thin groups fell back to a
cross-cell figure. Fixed by pooling the same circular plus or minus 3 week
window that defines the percentile in the first place.

This is the third instance of one failure mode in this project: an order
statistic estimated from about three or four values per cell-week. It produced
the identical fire targets earlier, and it produced this. The shape to watch for
is a per-cell per-week group in a record only four years long.

**Corrected table:**

    domain   h  MAE    clim MAE  gain [95% CI]          ratio [95% CI]
    larimer  2  24.97   31.81    +6.85 [+3.98, +9.58]   1.265 [1.210, 1.324]
    larimer  4  25.22   31.45    +6.23 [+3.36, +8.66]   1.244 [1.168, 1.322]
    larimer  8  26.64   31.05    +4.41 [+1.88, +6.70]   1.287 [1.206, 1.369]
    pueblo   2  23.43   29.43    +5.99 [+2.21, +10.07]  1.205 [1.148, 1.260]
    pueblo   4  23.25   29.45    +6.20 [+1.72, +10.03]  1.233 [1.165, 1.298]
    pueblo   8  23.64   27.44    +3.80 [+0.35,  +7.24]  1.181 [1.111, 1.248]

**The conclusion is unchanged, the magnitude was wrong.** Ratios fall from 2.41
to 2.79 down to 1.18 to 1.29, and all six still classify as climatological
because every interval lies entirely above 1.0.

**One conclusion did change.** With correct units all six MAE gains clear zero,
where `pueblo h8` previously did not: [-0.63, +6.98] became [+0.35, +7.24]. So
every point forecast is informative against a climatological median predictor
and no interval is.

**Why the shipped width is 73 to 75 rather than 90.** The pooled window trades
some spread for usable sample size, and a single cell's own distribution is
tighter than the cross-cell marginal. 91.4 is the right check on the *synthetic
uniform* invariant, which `tests/test_clim_width.py` asserts at 80 to 95; 73 to
75 is the right value for a real per-cell interval.

## The single SubX run: one target adopted

The rule was applied mechanically, once, with no iteration.

**Leakage guard, active.** The lead-dependent SubX climatology is refit inside
each fold with the held-out year excluded, and `assert_no_self_contribution`
raises if any held-out week fed the climatology used for its own anomalies. Five
tests cover it, including one that confirms the assertion fires rather than
merely existing. Configuration A is rescored on exactly the rows B sees: the
SubX-covered subset, 74,880 of 218,880 rows on Larimer and 67,392 of 196,992 on
Pueblo.

**Coverage limitation, recorded in the run output.** SubX has no hindcast
coverage inside the training split. The hindcast ends 2017-09-30 and the split
begins 2018, so B draws only on the forecast series.

**Result: 54 comparisons, 43 estimable, 10 passing in one domain, 1 passing in
both.**

    target      domain   Brier A   Brier B   BSS B vs A [95% CI]
    f_gt90_h2   larimer  0.14459   0.13393   +0.0737 [+0.0036, +0.1119]
    f_gt90_h2   pueblo   0.18622   0.12536   +0.3268 [+0.2006, +0.4509]

`f_gt90_h2` switches to configuration B. Every other target stays on A, which is
what the rule says and is why it was written as a both-domains rule: five
Larimer targets and five Pueblo targets passed individually, and only one
overlaps. Ten single-domain passes out of 43 estimable comparisons is close to
what a 5 percent per-comparison error rate would produce by itself.

**The caveat that belongs with this result.** Only **one** LODO fold, 2020,
falls inside the 2018 to 2020 training split, so each comparison rests on a
single held-out year. The circular block bootstrap prices the uncertainty
within that year, not across years, and no amount of resampling inside one year
substitutes for seeing another. `f_gt90_h2` is adopted because the rule says so
and the rule was fixed in advance, but its evidential basis is one year on each
domain, and the look-3 pre-registration states that.

**Why this target is plausible rather than surprising.** `f_gt90_h2` is fire
danger above the 90th percentile at a two-week lead. Two weeks is the horizon at
which a subseasonal precipitation and temperature forecast still carries real
information, and fire danger responds to weather on that timescale. If any
target were going to benefit from forecast weather, this is the one.

## The hand-written DODS parser was wrong; the library path reconciles exactly

The hand parser produced a Larimer 2018 domain mean of **21.4** against the
store's **43.6** for the same year and variable, while returning values in a
physically plausible 0 to 96 range. Two faults, one root.

**Fault 1: the bbox was a literal.** I used 40.25 to 41.00, which is 18 latitude
rows; `Settings.bbox` is 40.324 to 40.998, which is 16. Different terrain,
silently.

**Fault 2: the byte offset was assumed.** `Data:\n` plus 8 bytes was a guess at
the XDR framing, and it was never verified against a known value.

**The fix is to stop parsing a binary wire format by hand.**
`xarray.open_dataset` on the OPeNDAP URL, `.sel` with the bbox read from
`Settings`, and the descending latitude axis handled by ordering the slice high
to low. Result on Larimer 2018:

    reconciliation: ok=True, n_compared=175200, max|diff| = 0

Exact, every cell-day. Pueblo: ok=True, n=157680, max|diff| = 0.

**A permanent gate, not a one-off check.** `reconcile` compares a newly fetched
source-year cell for cell against an overlapping year already in the store, and
nothing is ingested until it passes. Six tests cover it, including a
time-shifted array whose marginal statistics are *identical* to the reference:
anything comparing means would pass it, and only a cell-for-cell check catches
it.

**The gate caught a real fault immediately.** Pueblo failed on its first run
with "no overlapping coordinates", because `reference_daily` globbed `raw/` and
returned Larimer's file. The raw caches are subset-scoped, `raw/gridmet` against
`raw/gridmet_pueblo`, so the path is now derived rather than searched. This is
the third appearance of the unscoped-cache fault in this project, after the v0.6
subset mix-up and the ESI start-year key, and this time a gate caught it before
any wrong data was written.

**Fetched.** ERC 2004 to 2017, both domains, 28 files, about 10 MB through the
reconciled path. USDM 2007 to 2017, 11 yearly bundles, 550 MB. Ledger stands at
2914 MB true of the 3000 MB cap.

**Record start is 2007**, bound by USDM rather than ERC. The 2012 gate is
cleared with five years to spare.

**On the USDM spatial archive.** Checked before defaulting to the zips.
`ndmcgeodata.unl.edu` serves WMS only, which returns rendered images rather than
polygons, and WFS returns `InvalidParameterValue`. The county statistics API is
5 kB per county-year but returns county-level area percentages, and the existing
raster carries 2.14 distinct USDM values per week across 480 cells, so
substituting it would redefine the target. The zips were used, as specified.

## The split defect, and which earlier tables it touched

**Two faults in `config.py`.**

`apply_subset_defaults` forced `train 2019 to 2022` for every dev subset, and
both domains run as dev subsets. That is the thin training window the 2007
back-extension exists to fix, and it was in the configuration all along.

Worse, the method is called by `get_settings()` and **not** by a bare
`Settings()`, so the two constructors disagreed: bare gave `train_start=2004`,
the factory gave `2019`. Analysis code in this project constructs both. A
calibration path and an evaluation path could therefore run on different
training windows without any error, which is the same class of fault as the
original ACI bug.

Both are fixed. The class default and the override now both read 2007 to 2021,
and `tests/test_split_consistency.py` asserts the two paths agree for every
domain, that the window is at least ten years, and that it never starts before
the USDM record.

**Which earlier tables were affected, audited rather than assumed.** Every
analysis module, `confirm.py`, `two_stage.py`, `oracle_decomp.py`, `pooled.py`
and `shipping.py`, constructs bare `Settings()`. They therefore used the class
defaults, **not** the 2019 override:

    reported and used:  train_end 2021, valid 2022 to 2023

Measured on the realised splits, with the feature store starting in 2018:

    train  74880 rows, years 2018, 2019, 2020
    cal    25440 rows, years 2020, 2021
    valid  49920 rows, years 2022, 2023

So the effective training window was **three years**, 2018 to 2020, with a 2020
to 2021 calibration carve-out, and validation was 2022 to 2023 exactly as
reported.

**No earlier table ran on a split other than the one it reported.** The
disagreement between the constructors was real and dangerous, and it happened
not to bite, because the modules that mattered all took the same branch. The
thinness of the training window is the substantive problem, and the extended
rerun supersedes those tables rather than correcting them.

One consequence worth carrying forward: the single usable LODO fold reported
earlier, 2020, follows directly from a 2018 to 2020 training window. The
extended record should make 2012, 2018, 2020 and 2021 all usable.

## The decoupled builder: usdm and erc reconcile exactly, erc_pct does not

`features_a.py` builds configuration A's features from a coordinates-only grid
template, so the record extends to 2007 using the ERC and USDM already fetched
rather than the 189 MB of unused gridMET variables the full builder would have
demanded against 86 MB of budget.

**Reconciliation against the store, 2018 to 2025:**

    column    larimer                    pueblo
    usdm      max|diff| 0   n=200640     max|diff| 0   n=180576
    erc       max|diff| 0   n=200640     max|diff| 0   n=180576
    erc_pct   max|diff| 43.79            max|diff| 38.10

**Three faults the gate caught on the way to erc matching**, none of which made
a value look implausible:

1. **Year-boundary duplicates.** The week ending 2023-01-03 exists in both
   `weekly_2022.nc` and `weekly_2023.nc` with domain means 25.90 and 14.41. The
   store resolves this with `drop_duplicates(keep="last")` at `features.py:127`
   and `:293`. Keeping the first occurrence gave 50.25 where the store says
   27.0.
2. **Per-file resampling truncated cross-year weeks.** Daily extension files are
   now concatenated before resampling.
3. **A partial week from the extension outranked the store.** The 2017 file
   resamples to a week labelled 2018-01-02 covering only 27 to 31 December, and
   under `keep="last"` it beat the cube's complete week: 35.2 against the
   store's 46.0. Fixed by ordering the authoritative store last and dropping any
   weekly bin the daily record cannot fill with seven days.

**erc_pct is a derived quantity and is expected to differ.** It is a percentile
against the *training* distribution, and the extension changes that
distribution: 213 distinct values against the store's 69, because fifteen
training years resolve a percentile far better than three. That improvement is
the point of the extension.

**But the difference is not fully explained by the training window, and that is
not resolved.** Recomputing `erc_pct` on the store's own 2018 to 2020 window
still leaves max|diff| 47.4, and a hand calculation on one cell reproduces
neither figure: the store reports 11.76 where a pooled +/-3 week window over
that cell's training rows gives 27.27 and the decoupled builder gives 55.56. The
store's 69 distinct values confirm it does use the widened window, so the
remaining difference is in how the training pool is assembled, and
`features.py` builds it through `TrainingStats` and `transform` rather than from
the feature frame.

**The gate is left failing on erc_pct.** `tests/test_features_a_reconcile.py`
passes for `usdm` and `erc` on both domains and fails for `erc_pct`, which is
the honest state. Nothing downstream has been run on this data. Resolving it
means reading `fit_training_stats` and reproducing its pooling exactly, not
relaxing the tolerance.

## erc_pct: one reference implementation, and what the two old ones did wrong

The definition, stated once and now implemented once in `cofire/model/erc_pct.py`:
the empirical percentile of a cell-week's ERC within that cell's pool of
training values whose week-of-year lies within +/- 3 of it on a circular
calendar, with `scipy.stats.percentileofscore(kind="mean")`.

`kind="mean"` rather than `"weak"` because a value drawn from its own pool
should be unbiased: for a pool of n distinct values the n results are evenly
spaced about 50 under `"mean"`, while `"weak"` skews them upward by 100/(2n).

**The hand-calculated cell, fully reproducible.** Cell `40.8583_-105.1833`,
week 2018-01-02, woy 1, window weeks [50, 51, 52, 1, 2, 3, 4]. On a 2018 to
2020 training window the pool holds 22 values:

    40.0 51.1 44.6 42.1 35.6 54.0 51.7 32.0 46.6 43.3 47.6
    29.4 33.3 48.3 36.6 44.6 43.4 41.4 66.7 43.9 44.1 47.7

Target ERC 40.0: 5 strictly below, 1 equal, n=22.

    strict  = 500/22   = 22.7273
    weak    = 600/22   = 27.2727
    mean    = 550/22   = 25.0000   <- reference

The store reported **11.7647**, which is none of these.

**Why the store differed: the wrong training window, not the wrong formula.**
Its window code in `fit_training_stats` uses the same circular wrap as the
reference. The persisted `artifacts/training_stats.pkl` carries
`train_end = 2022-12-31` and a pool of **34** values for that cell-week, giving
4/34 = 11.7647 exactly under `kind="weak"`. A woy-1 pool spans 7 weeks, so 34
values is five training years and 22 is three.

So `erc_pct` in the store was fitted on **2018 to 2022**, which includes the
validation years. The percentile target saw its own evaluation period.

**Disagreement with the reference, measured on the store's own window:**

    domain   store vs reference              builder vs reference
    larimer  79.9% of cell-weeks, max 14.71  97.6%, max 42.38
    pueblo   81.4% of cell-weeks, max 11.43  98.4%, max 36.67

The store differs by the tie convention; the decoupled builder differs by the
wider 2007 to 2021 training window, which is the intended change.

**Both now delegate to the reference.** `features.py::_percentile` and
`features_a.py::erc_percentile` call the same function, so fitting and
transformation cannot drift apart again. Eight tests cover the reference,
including the year wrap at weeks 50 to 3, the tie convention, and a pool listed
row by row for hand-checking.

## Which earlier results were computed on a flawed target

`erc_pct` feeds every fire target, since `f_gt80`, `f_gt90` and `f_gt97` are
exceedances of it, and `erc_pct_h{2,4,8}` are its horizon shifts.

**Affected, and superseded rather than corrected:**

- every fire row of `artifacts/ablation/confirm.csv`
- `artifacts/ablation/fire_baselines.csv` in full, which is the table that
  retired the three `f_gt97` survivors
- the fire rows of `artifacts/ablation/oracle_decomposition.csv` and
  `two_stage.csv`
- the fire entries of `artifacts/shipping/choices.json`, 9 of 27 targets
- `artifacts/shipping/continuous_reference.csv` in full, since the continuous
  target *is* `erc_pct`
- the SubX result for `f_gt90_h2`, the one target that switched to
  configuration B

The drought targets are built from USDM categories and are unaffected.

Two of the conclusions those tables support are worth flagging as now resting
on a flawed target: that the fire transition baseline absorbed every fire
survivor, and that `f_gt90_h2` was the single SubX adoption. Both are plausible
on their face and neither is confirmed. The extended rerun recomputes them.

## Fit-window audit: one demonstrable leak, five unrecorded, none touching 2026

**Gate: no artifact touches the sealed holdout.** The calibration JSONs contain
the string "2026" only as digit substrings inside float residuals such as
`32.4669475332026`, plus `seed: 2026`. No date field reaches the holdout year,
so the audit continues rather than stopping.

**The table**, split in effect 2007-01-01 to 2021-12-31:

    artifact                            fit_start   fit_end      scope        verdict
    training_stats.pkl (10 statistics)  unrecorded  2022-12-31   train        VIOLATION
    calibration/conformal.json          unrecorded  unrecorded   calibration  unrecorded
    calibration/bootstrap.json          unrecorded  unrecorded   calibration  unrecorded
    shipping/choices.json               unrecorded  unrecorded   train        unrecorded
    shipping/continuous_arms.json       unrecorded  unrecorded   train        unrecorded
    shipping/subx_verdict.json          unrecorded  unrecorded   train        unrecorded

**The leak is wider than `erc_pct`.** `training_stats.pkl` holds **ten** fitted
statistics under one `train_end`, not one: `spi_gamma`, `spei_gamma`,
`erc_by_woy`, `bi_by_woy`, `fm100_mean`, `fm1000_mean`, `tmmx_mean`,
`tmmx_std`, `pr_roll13_mean`, `pr_roll13_std`. All were fitted through
2022-12-31 against a split ending 2021.

What each fed:

- `erc_by_woy` gives `erc_pct`, which gives every fire target. Already recorded
  as superseded.
- `bi_by_woy` gives `bi_pct`, and `fm100_mean`, `fm1000_mean`, `tmmx_mean`,
  `tmmx_std`, `pr_roll13_*` give the anomaly features. `spi_gamma` and
  `spei_gamma` give SPI and SPEI.
- Those anomaly and drought-index features feed the **ML arms only**. They are
  not in configuration A, which reads USDM, ERC, `erc_pct` and calendar fields.

**So the drought targets are unaffected.** They are built from USDM categories,
which come from rasterised polygons rather than from any fitted statistic. The
ML-arm ablation tables are affected, and they are already not shipped and not
being re-run.

**The five unrecorded artifacts are not cleared, only unproven.** Absence of a
recorded window is not evidence of a clean fit, which is why
`checked_load(strict=True)` now refuses an artifact that declares nothing. All
five are regenerated in the rerun, with windows recorded.

**The invariant.** `cofire/model/fit_window.py`: an artifact declares
`[fit_start, fit_end]` and a scope, and the loader asserts the window lies
inside the train split, or the calibration split for calibrators and controller
warm-up state. It raises rather than warns, because a warning in a long
unattended run is a log line nobody reads. Eight tests, including one that
loads an artifact declaring `fit_end = 2022-12-31` and requires the failure.

## Step 3: the fire conclusion holds, and a shuffled control shows why

**Family selection changed on 6 of 27 targets, all fire, all the same way.**
Under the corrected `erc_pct` every fire target now selects the damped
persistence logistic, 9 of 9, where the flawed target gave transition 6 and
damped 3. Drought families are unchanged at markov 18 of 18, which is expected:
they are built from USDM and never touched `erc_pct`.

    target      h   2018+ family -> extended    2018+ Brier  extended Brier
    f_gt80_h2   2   transition   -> damped          0.19159       0.18271
    f_gt90_h2   2   transition   -> damped          0.12873       0.11565
    f_gt97_h2   2   transition   -> damped          0.07567       0.04187
    f_gt80_h4   4   transition   -> damped          0.19462       0.19447
    f_gt90_h4   4   transition   -> damped          0.13356       0.12327
    f_gt90_h8   8   transition   -> damped          0.12890       0.12714

The continuous analogue also moved: h8 now selects damped regression where it
previously selected the decile mean, and pooled selection wins 20 of 27 against
21 of 27.

**Re-tested conclusion: does the fire transition baseline still absorb every
fire result? Yes.** Zero of 18 fire targets clear it in both domains. Seven
clear it in a single domain, and the domains disagree about which horizons:
Larimer at h2 and h4, Pueblo only at h8.

**The shuffled-target control says those seven are artefacts.** Permuting the
target within week blocks, preserving the marginal, and rerunning the identical
comparison:

    domain   target      h   real BSS [CI]            shuffled BSS [CI]
    larimer  f_gt80_h2   2   +0.0234 [+0.001, +0.046]  +0.0252 [+0.012, +0.038]
    larimer  f_gt80_h4   4   +0.0262 [+0.011, +0.042]  +0.0097 [+0.004, +0.015]
    larimer  f_gt90_h4   4   +0.0298 [+0.011, +0.052]  +0.0249 [+0.010, +0.038]
    larimer  f_gt97_h2   2   +0.0976 [+0.058, +0.170]  +0.0859 [+0.040, +0.123]
    larimer  f_gt97_h4   4   +0.0554 [+0.003, +0.114]  +0.0693 [+0.009, +0.112]
    pueblo   f_gt80_h8   8   +0.0632 [+0.014, +0.101]  +0.0291 [-0.006, +0.055]
    pueblo   f_gt90_h8   8   +0.0415 [+0.016, +0.068]  +0.0165 [+0.001, +0.031]

**Six of seven controls also show an interval above zero**, and on `f_gt97_h4`
the shuffled control at +0.0693 *exceeds* the real result at +0.0554. A skill
score that survives destroying the target is not measuring skill.

The mechanism is that the damped logistic and the transition table are both
functions of the same current ERC decile, so their Brier scores differ by a
structural amount that has nothing to do with the outcome. The bootstrap then
prices that structural difference tightly, because it is consistent across
weeks, and reports an interval clear of zero.

**Consequence.** No fire target ships as skillful. The failure-handling rule
that required this control is what caught it, and the rule earned its place: the
seven single-domain passes would otherwise have looked like the extension
recovering results the flawed target had hidden.

## Stages A and B: the intervals became informative on the extended record

**Stage A, reference PID coverage.** Warm-up on the calibration split only,
scored on validation 2022 to 2023:

    dom      h     cov   width  run  roll13   D0-D1     D2+
    larimer  2  0.8983   63.91   21  0.8954  0.8987  0.8955
    larimer  4  0.8985   66.58   11  0.8963  0.8973  0.9086
    larimer  8  0.8989   68.76   15  0.8963  0.9006  0.8842
    pueblo   2  0.8978   52.80   31  0.8921  0.8969  0.9042
    pueblo   4  0.8975   55.77   21  0.8910  0.8969  0.9020
    pueblo   8  0.8977   58.81   16  0.8917  0.8978  0.8973

All five preregistered criteria pass. The local tests are the informative ones,
since long-run coverage is guaranteed by construction: the minimum rolling
13-week coverage is 0.8910 to 0.8963 against a 0.70 floor, and the two drought
strata differ by at most 0.024. ACI on the same streams reaches a rolling
minimum of 0.4220 at Pueblo h8 with a 993-week miss run.

**Stage B, the width-ratio classification, and it changed.**

    domain   h   MAE gain [CI]         ratio [CI]              2018+    extended
    larimer  2   +3.25 [+2.28, +4.12]  0.970 [0.958, 0.982]    clim  -> INFORMATIVE
    larimer  4   +2.11 [+1.43, +2.70]  0.994 [0.978, 1.010]    clim  -> climatological
    larimer  8   +1.13 [+0.77, +1.51]  1.006 [0.987, 1.021]    clim  -> climatological
    pueblo   2   +6.36 [+4.99, +7.81]  0.922 [0.902, 0.941]    clim  -> INFORMATIVE
    pueblo   4   +5.81 [+4.53, +6.91]  0.943 [0.927, 0.959]    clim  -> INFORMATIVE
    pueblo   8   +3.38 [+2.40, +4.36]  0.977 [0.960, 0.993]    clim  -> INFORMATIVE

Four of six are now informative, against none on the 2018+ record where every
ratio sat between 1.18 and 1.29. The cause is the training record: fifteen years
of per-cell week-of-year history give a point forecast whose residuals are
tighter than the climatological spread, where three years did not.

**The shuffled-target control confirms it, and this is the contrast with the
fire result.** Permuting the target within week blocks and rerunning:

    domain   h   real ratio [CI]         shuffled ratio [CI]      real MAE gain  shuffled
    larimer  2   0.970 [0.958, 0.982]    1.142 [1.136, 1.147]     +3.25          -0.71
    pueblo   2   0.922 [0.902, 0.941]    1.211 [1.203, 1.219]     +6.36          -0.75
    pueblo   4   0.943 [0.927, 0.959]    1.162 [1.154, 1.170]     +5.81          -0.30
    pueblo   8   0.977 [0.960, 0.993]    1.076 [1.068, 1.083]     +3.38          +0.23

Every shuffled ratio rises above 1.0 with its interval entirely above, and every
shuffled MAE gain collapses to zero or below. **0 of 4 invalidated.**

This is the opposite of the fire comparison, where six of seven controls
reproduced the effect. There the two arms were both functions of the same ERC
decile and differed structurally; here the interval width tracks the residuals,
and destroying the target makes the residuals larger and the ratio worse, which
is what a real result looks like.

**Rendering consequence.** Under the preregistered rule, `larimer h2` and
`pueblo` at h2, h4 and h8 render as forecast intervals; `larimer` at h4 and h8
render as the historical week-of-year range of raw ERC. The MAE gain interval is
above zero on all six, so the point forecast is shown in every case.

## v1.1 Stage 1: the Denver domains

CO-01 is the City and County of Denver. Neither Larimer nor Pueblo is in it, so
v1.1 adds Denver and the two watersheds Denver Water collects from. Boundaries
are resolved by name and recorded in `artifacts/domains/footprints.json` by
`cofire/ship/domains.py`; every fetch went through `cofire/ship/safe_fetch.py`
(132,695 bytes, all JSON from hydro.nationalmap.gov).

| Domain | Matched boundary | Area | Footprint cells | Rectangle | bbox (W, S, E, N) |
|---|---|---|---|---|---|
| Denver | Census cb_2023 county GEOID 08031, "Denver County" (on disk) | 400.7 km² | 52 | 8 x 13 = 104 | -105.1104, 39.5979, -104.5896, 39.9104 |
| Upper South Platte | WBD HUC8 10190002 "Upper South Platte", 23 of its 50 HUC12s | 2,629.3 km² | 202 | 18 x 21 = 378 | -105.8604, 38.8896, -105.0063, 39.6188 |
| Dillon | WBD HUC8 14010002 "Blue", 12 of its 19 HUC12s | 864.6 km² | 79 | 9 x 13 = 117 | -106.2771, 39.3479, -105.7563, 39.7021 |

For comparison, Larimer is 16 x 30 = 480 cells and Pueblo 18 x 24 = 432.

**Name resolution.** The HUC8 query for names containing "South Platte" in
Colorado returned five candidates (10190001 South Platte Headwaters, 10190002
Upper South Platte, 10190003 Middle South Platte-Cherry Creek, 10190012 Middle
South Platte-Sterling, 10190018 Lower South Platte); exactly one is named
"Upper South Platte". The query for "Blue" returned one, 14010002 "Blue".

**Cut at the reservoir.** Both HUC8s run past their reservoirs, so each domain
is the HUC12 holding the reservoir plus every HUC12 whose WBD `tohuc` chain
drains into it. Strontia Springs Reservoir was located by GNIS name in USGS NHD
(GNIS 00197627, 0.328 km²); it lies in HUC12 101900020701 "Platte Canyon-South
Platte River". Plum Creek, Bear Creek, Chatfield and Sloan Lake, which join
below the dam, are dropped. The NHD lookup for Dillon Reservoir timed out twice,
and was not needed: WBD names HUC12 140100020401 "Dillon Reservoir-Blue River",
which is the outlet. Green Mountain Reservoir and the lower Blue are dropped.

**What the Upper South Platte domain leaves out.** HUC8 10190001 "South Platte
Headwaters" (South Park, 4,154.9 km², including Antero and Elevenmile) also
drains to Strontia Springs. It is outside the domain because the brief names a
single HUC8. It can be added later as its own domain.

**No clip.** Neither watershed is larger than the existing domains (202 and 79
cells against 480 and 432), so none was clipped by distance from its reservoir.
Denver has fewer cells because the county is small; growing it would add cells
outside the district.

**Footprint within rectangle.** The frozen pipeline selects cells by bbox, so
each new domain is fetched and processed as the rectangle enclosing its
footprint. The bbox is padded by a quarter cell around the footprint's
outermost centres, so the frozen clip selects exactly that rectangle
(`tests/test_domains.py`). The footprint mask marks which rectangle cells
belong to the domain; half of Denver's rectangle is Aurora, Lakewood and
Arapahoe County.

**Enclaves.** Glendale and Holly Hills are Arapahoe County enclaves surrounded
by Denver. They appear as holes in the Denver polygon (1.52 km² centred at
39.704 N, 104.935 W and 1.31 km² at 39.667 N, 104.920 W; identified by
location, since Census place boundaries are not on disk). At 4 km both fall
inside Denver footprint cells: a hole's cell always touches the surrounding
ring. So the Denver domain covers all of CO-01.

**Runtime registration.** `domains.register()` adds the three domains to
`config.SUBSETS` at runtime, so the frozen code runs on them unchanged with
`COFIRE_SUBSET_NAME=<domain>`. The watersheds carry a nominal FIPS (08093 Park,
08117 Summit) that only the frozen USDM county-statistics fallback would read;
the v1.1 build requires rasterized shapefiles and fails rather than fall back.

## v1.1 Stage 2: ERC for the new domains, and why it is not an NCSS download

USDM needed no transfer: the 2007 to 2026 national yearly archives are on disk
and rasterize onto any grid.

ERC 2004 to 2025 came through the reconciled path, the frozen
`erc_extension.fetch_year` (`xarray.open_dataset` on the OPeNDAP URL, `.sel`
with the domain bbox), called unchanged for each registered domain by
`cofire/ship/erc_fetch.py`.

**NCSS, which would have produced a file for `safe_fetch`, is broken on the
server.** Every subset request, down to one cell-day, returns HTTP 500 with the
body "-101: NetCDF: HDF error" (probe logged, 23 bytes). The whole-file
fileServer route costs tens of MB per variable-year, which the 85.7 MB left
under the ledger's global ceiling cannot carry.

**How the fetch rules apply to an OPeNDAP stream.** No file crosses the wire,
so `safe_fetch` cannot wrap the read itself. `erc_fetch` applies each rule that
has a meaning for a stream:

1. HTTPS and the allowlist on the URL. A HEAD on the `.dds` endpoint must not
   redirect, because the NetCDF library would follow a redirect unchecked.
2. HEAD first, then the `.dds` through `safe_fetch`. The exact DAP2 wire size
   comes from its shape (UInt16 sent as 4-byte XDR words, plus coordinate maps
   and metadata) and is checked against the session cap and the ledger before
   data moves.
3. The library refuses an HTML error page, and the array must have the
   domain's exact rectangle, at least 95% finite cell-days, values in 0 to 200,
   and non-zero spread, or nothing is cached.
4. Each cached year is checked against its peers' sizes.
5. No archives are involved.
6. No new packages. The frozen reader's pydap fallback is not installed and
   was not added; one read failed on a transient error, was refused, logged,
   and succeeded on resume.
7. Each read is logged with URL, computed bytes, the cached file's sha256 and
   a timestamp.

**Priced before fetching.** One variable-year (Denver 2020): 178,348 bytes
projected, 97,907 bytes cached, 1.7 s. Projected 2004 to 2025: Denver
3,916,744, Upper South Platte 12,727,368, Dillon 4,334,792, total 20,978,904
bytes. 2026, needed only for scoring-free forecasts: 715,852 bytes, not yet
fetched.

**Spent this session:** 21,345,687 bytes (OPeNDAP 21,175,808 including the
refused read, DAP metadata 13,028, DAP ASCII gate samples 24,133, WBD 119,315,
NHD 13,380, NCSS probe 23). Session cap 2.0 GB; ledger global remaining
64,327,490 bytes.

## v1.1 Stage 3: configuration A stores for Denver, Upper South Platte, Dillon

Built by the frozen `features_a.build`, unchanged, through
`cofire/ship/build_v11.py`, 2007 to 2025 (992 weeks). The frozen builder needs
a processed cube for coordinates; each new domain gets a coordinates-only
`weekly_template.nc` taken from its own ERC cache (same grid by construction)
and carrying no `erc` variable, so `weekly_erc` ignores it for data. Stores
hold the full rectangle; the loader keeps footprint cells only and asserts none
is missing. Each build took 30 s under the watchdog.

**Reconciliation gate.** No new-domain cell coincides with a Larimer or Pueblo
cell (0 shared), so the cell-for-cell store comparison cannot apply. The
applicable gate is against the source: for each domain, 3 random years x 4
random footprint cells x 7 days were requested again as raw DAP ASCII (a
different wire format parsed by different code) through `safe_fetch` and
compared with the cache. Result: 84 cell-days per domain, max|diff| 0 on all
three, and every sampled index returned the coordinates the cache assigns it
(`artifacts/domains/erc_gate.json`). The fetch path itself is the one that
reconciled with max|diff| 0 on Larimer (175,200 cell-days) and Pueblo
(157,680).

**erc_pct** comes from the single reference implementation with pools from
2007 to 2021 only. Uniformity check, per-cell 5th to 95th percentile width over
the training years (asserted median 85 to 95, minimum 80):

| Domain | median | min | max |
|---|---|---|---|
| Denver | 89.51 | 88.20 | 89.95 |
| Upper South Platte | 88.57 | 86.84 | 90.35 |
| Dillon | 88.05 | 86.67 | 89.40 |
| Larimer | 88.57 | 86.59 | 90.48 |
| Pueblo | 88.57 | 87.62 | 89.52 |

Integer ERC ties keep the width a little under 90 in every domain.

**Scoping.** Every path is derived from the active domain: `processed_<domain>`
stores, `erc_ext/<domain>_*.nc` caches (22 files asserted, each name carrying
the domain), and `processed_<domain>/usdm/weekly.nc`. The loader asserts its
root carries the domain name; Larimer's legacy unscoped `data/processed` is
the one documented exception.

**Not estimable in validation (fewer than 12 positive weeks, 2022 to 2023):**
Denver 10 of 27 (d_ge3 x3, d_intensify1_h2, d_intensify2 x3, f_gt97 x3);
Upper South Platte 11 (d_ge2 x3, d_ge3 x3, d_intensify2 x3, f_gt97_h4,
f_gt97_h8); Dillon 15 (d_ge2 x3, d_ge3 x3, d_intensify1 x3, d_intensify2 x3,
f_gt97 x3). Larimer 7 and Pueblo 8 on the same count. Full per-target counts
and the USDM category distribution by year are in
`artifacts/domains/stage3.json`.

**Denver's fire targets are estimable, contrary to the expectation.** The fire
targets are ERC above the cell's own training percentile (80, 90, 97), so f_gt80
and f_gt90 occur at similar rates in any domain by construction: Denver has 38
to 39 validation positive weeks at 80 and 16 to 17 at 90. They measure how dry
Denver is relative to its own record, not wildland fire danger in a city.
Only f_gt97 falls short (6 weeks). The Denver Place Card therefore shows fire
danger from the source watersheds, as planned, and Denver's own ERC targets
are labeled as relative dryness wherever they appear.

## v1.1 Stage 4: configuration A fitted per domain, selection leak-free

`cofire/ship/fit_v11.py`. The frozen predictors are called unchanged: Markov
for drought, damped logistic and ERC-decile transition for fire, damped
regression and decile mean for the continuous percentile. The frozen
`shipping.choose` is not used, because it runs folds without an embargo and
with `erc_pct` pools that include the held-out year. Here every fold recomputes
`erc_pct` from its own training years and drops training rows whose h-week
label lands in the held-out year (asserted per fold).

Split: train 2007 to 2021, validate 2022 to 2023, calibrate 2024 to 2025.
Configuration A ships no calibrator, so 2024 to 2025 fit nothing and are not
used for selection. Nothing touches 2026.

**LODO folds** (training years whose footprint-mean USDM category exceeds that
domain's 2007 to 2021 median):

| Domain | median | folds |
|---|---|---|
| Denver | 0.2448 | 2010, 2011, 2012, 2013, 2017, 2020, 2021 |
| Upper South Platte | 0.2509 | 2011, 2012, 2013, 2017, 2018, 2020, 2021 |
| Dillon | 0.0114 | 2012, 2013, 2016, 2018, 2019, 2020, 2021 |
| Larimer | 0.1609 | 2011, 2012, 2013, 2016, 2017, 2020, 2021 |
| Pueblo | 0.4596 | 2011, 2012, 2013, 2014, 2018, 2020, 2021 |

**Shared years, used for pooled selection: 2012, 2013, 2020, 2021.** Pueblo's
list equals its frozen `DOMAIN_FOLDS`; Larimer's lacks 2018, which the frozen
list carried only as a shared year.

**Pooled selection.** Each domain is fitted on its own rows and scored on its
own held-out rows in the shared years; arms are compared on the mean of the
five per-domain scores, so Larimer's 480 cells do not outvote Denver's 52.

| target | damped | transition | choice | frozen |
|---|---|---|---|---|
| f_gt80_h2 | 0.174596 | 0.177365 | damped | damped |
| f_gt80_h4 | 0.201666 | 0.209206 | damped | damped |
| f_gt80_h8 | 0.219477 | 0.226171 | damped | damped |
| f_gt90_h2 | 0.129711 | 0.131327 | damped | damped |
| f_gt90_h4 | 0.147308 | 0.151422 | damped | damped |
| f_gt90_h8 | 0.156306 | 0.160380 | damped | damped |
| f_gt97_h2 | 0.062546 | 0.063116 | damped | damped |
| f_gt97_h4 | 0.067233 | 0.068372 | damped | damped |
| f_gt97_h8 | 0.068140 | 0.069726 | damped | damped |

Continuous arm: damped regression at h2, h4 and h8 (all 15 domain-horizon
comparisons), matching the frozen choice. Drought: Markov, the only candidate.

On each domain's own folds damped wins 40 of 45 fire targets. The five
exceptions are all h2 in the watersheds (Dillon f_gt90, f_gt97; Upper South
Platte f_gt80, f_gt90, f_gt97), by at most 0.00043 Brier. Selection is pooled
by design, so damped ships in all five domains.

**Artifacts.** `artifacts/v11/choices.json` and `continuous_arms.json`, each
with a fit window 2007-01-01 to 2021-12-31, scope train, loaded through the
frozen strict `checked_load` (tested to raise on a window past 2021).
Larimer and Pueblo keep `artifacts/rerun_a`, so the frozen config hash is
unchanged.

## v1.1 Stage 5, stated before running: survivor test and agreement rule

Written and committed before the Stage 5 test is run.

**Pair-level survivor** (unchanged definition, now over five domains): a
target and domain pair survives when it is estimable (at least 12 positive
validation weeks), the paired real-minus-shuffled BSS interval from the
circular block bootstrap lies above zero, BH at q = 0.10 rejects across every
estimable pair in all five domains together, and Holm rejects within its
domain and event family. Fits are embargoed at the 2021/2022 boundary, and
`erc_pct` pools come from 2007 to 2021 only. Larimer and Pueblo are scored with
their frozen families, the new domains with the v1.1 families. Validation is
2022 to 2023. Nothing is computed on 2026.

**Agreement rule, for a target-level claim across domains:** a target counts
as skillful across domains only if it passes in every domain where it is
estimable, and passes in at least two domains. A target that survives in one
domain and fails in another where it is estimable does not agree, and is
reported as a single-domain result.

**What the app claims.** Skill claims in the app stay pair-level (a target in a
domain), read from `facts.survivors`. If one of the 11 current survivors fails
under the five-domain test (for example because the larger BH family moves its
threshold), `facts.json` and the pages are updated to drop it.

**Surprisingly strong results.** Every pair's real and shuffled BSS are both
reported. Any new-domain pair whose real BSS exceeds the largest real BSS
among the current 11 survivors is flagged and shown beside its shuffled
control before it is used anywhere.

**Reliability and rendering for the new domains.** No 2026 evaluation exists
for them, so rendering is decided on validation 2022 to 2023 with the
preregistered look-3 threshold: Murphy reliability term at most 0.05. A target
renders as a per-cell probability when it is estimable and its per-cell
reliability passes; otherwise it renders the regional base rate with the
reason (not estimable, or reliability failed). The regional base rate's own
reliability is reported beside it. Larimer and Pueblo keep their look-3
rendering.

## v1.1 Stage 5 results: 21 survivors over five domains, no cross-domain agreement

`cofire/ship/survivors_v11.py`, run after the rules above were committed
(79f6989). Output `artifacts/v11/survivors_v11.csv` and
`survivors_v11_summary.json`.

**Reproduction check.** Larimer and Pueblo recomputed through the new runner
match `artifacts/audit/survivors_embargoed.csv` on all 51 pairs with max|diff| 0
for the paired difference, both CI ends, the p-value and positive weeks.

**Counts.** 115 pairs with non-constant validation labels (Larimer 24, Pueblo
27, Denver 26, Upper South Platte 20, Dillon 18); 83 estimable; 21 survive
BH (q = 0.10, across all 83) and Holm (within domain and family). **All 11
current survivors hold** with unchanged CIs. 10 new pairs survive, all in the
new domains.

| Domain | Target | Arm | Pos. weeks | Real BSS | Shuffled BSS | Paired diff [95% CI] | |
|---|---|---|---|---|---|---|---|
| Denver | d_improve1_h2 | markov | 24 | +0.2854 | +0.0597 | +0.2257 [+0.1009, +0.3527] | new |
| Denver | d_improve1_h4 | markov | 35 | +0.4024 | +0.1593 | +0.2431 [+0.0950, +0.4534] | new |
| Denver | d_nochange_h2 | markov | 90 | +0.1792 | +0.0995 | +0.0797 [+0.0198, +0.1533] | new |
| Dillon | f_gt80_h8 | damped | 34 | +0.0656 | +0.0340 | +0.0317 [+0.0100, +0.0502] | new |
| Larimer | d_ge2_h2 | markov | 21 | +0.5489 | -0.2841 | +0.8331 [+0.1668, +1.1959] | current |
| Larimer | d_ge2_h4 | markov | 19 | +0.1241 | -0.3620 | +0.4861 [+0.0174, +0.8697] | current |
| Larimer | d_improve1_h2 | markov | 32 | +0.2016 | -0.0034 | +0.2050 [+0.0996, +0.3262] | current |
| Larimer | d_improve1_h4 | markov | 36 | +0.3342 | +0.0077 | +0.3266 [+0.1822, +0.5115] | current |
| Larimer | d_improve1_h8 | markov | 40 | +0.3748 | +0.0036 | +0.3713 [+0.2401, +0.5624] | current |
| Larimer | d_nochange_h2 | markov | 102 | +0.1526 | -0.0128 | +0.1654 [+0.0642, +0.2784] | current |
| Larimer | d_nochange_h4 | markov | 100 | +0.2556 | +0.0003 | +0.2554 [+0.0946, +0.4240] | current |
| Larimer | d_nochange_h8 | markov | 96 | +0.3442 | -0.0036 | +0.3478 [+0.1738, +0.5007] | current |
| Pueblo | d_ge2_h2 | markov | 39 | +0.6352 | +0.3305 | +0.3048 [+0.0913, +0.5134] | current |
| Pueblo | f_gt80_h8 | damped | 33 | +0.0722 | +0.0322 | +0.0400 [+0.0124, +0.0679] | current |
| Pueblo | f_gt90_h8 | damped | 19 | +0.0437 | +0.0196 | +0.0242 [+0.0026, +0.0455] | current |
| Upper South Platte | d_improve1_h2 | markov | 22 | +0.3087 | +0.0384 | +0.2703 [+0.1347, +0.4371] | new |
| Upper South Platte | d_improve1_h4 | markov | 31 | +0.4663 | +0.1179 | +0.3485 [+0.1733, +0.6767] | new |
| Upper South Platte | d_nochange_h2 | markov | 102 | +0.2477 | +0.0706 | +0.1770 [+0.0534, +0.3282] | new |
| Upper South Platte | d_nochange_h4 | markov | 100 | +0.3788 | +0.1184 | +0.2604 [+0.1111, +0.4217] | new |
| Upper South Platte | d_nochange_h8 | markov | 96 | +0.5074 | +0.2273 | +0.2802 [+0.0571, +0.5446] | new |
| Upper South Platte | f_gt80_h8 | damped | 37 | +0.0753 | +0.0301 | +0.0452 [+0.0100, +0.0778] | new |

**Surprisingly strong: none.** The largest real BSS among the new survivors is
+0.5074 (Upper South Platte d_nochange_h8), below the largest among the current
11 (+0.6352, Pueblo d_ge2_h2). Every pair's shuffled control is reported.

**Agreement rule: no target qualifies.** Every target that survives somewhere
fails in at least one domain where it is estimable:

| Target | Denver | Upper South Platte | Dillon | Larimer | Pueblo |
|---|---|---|---|---|---|
| d_improve1_h2 | pass | pass | fail | pass | fail |
| d_improve1_h4 | pass | pass | fail | pass | fail |
| d_nochange_h2 | pass | pass | fail | pass | fail |
| d_nochange_h4 | fail | pass | fail | pass | fail |
| d_nochange_h8 | fail | pass | fail | pass | fail |
| f_gt80_h8 | fail | pass | pass | fail | pass |
| d_ge2_h2 | fail | n.e. | n.e. | pass | pass |
| d_ge2_h4 | fail | n.e. | n.e. | pass | fail |
| d_improve1_h8 | fail | fail | fail | pass | fail |
| f_gt90_h8 | fail | fail | fail | fail | pass |

(n.e. = not estimable or no positive validation weeks.) So COFIRE makes no
target-level claim across domains. Skill claims stay pair-level.

**Fire conclusion, re-run.** 4 fire pairs survive: Pueblo f_gt80_h8 and
f_gt90_h8 (both already among the 11), Dillon f_gt80_h8 and Upper South Platte
f_gt80_h8. None at h2 or h4, none in Denver or Larimer. f_gt80_h8 passes in
three domains and fails in two where it is estimable, so it does not meet the
agreement rule. The family conclusion is unchanged: damped logistic in every
domain (Stage 4).

**Validation reliability and rendering for the new domains** (preregistered
look-3 threshold, Murphy reliability at most 0.05):

| Domain | probability | base rate: fewer than 12 weeks | base rate: reliability failed | no positive validation weeks |
|---|---|---|---|---|
| Denver | 16 | 8 | 1 (d_improve1_h8, 0.0851) | 1 (d_ge3_h8) |
| Upper South Platte | 16 | 4 | 0 | 7 |
| Dillon | 11 | 6 | 1 (d_nochange_h8, 0.0667) | 9 |

Per-cell and regional-base-rate reliability for every pair are in the CSV.
Denver's fire probabilities (f_gt80, f_gt90) pass reliability; they measure
ERC relative to Denver's own record and are labeled so.

**facts.json.** No current survivor failed, so nothing is withdrawn. The new
domains' pairs enter the app in Stage 6, read from this table.

## v1.1 Stage 6: the app covers Denver, and Denver's card carries its water

**Domain switcher.** Denver, Upper South Platte, Dillon, Larimer, Pueblo, with
Denver the default. The choice lives in `?domain=` and local storage
(`app/lib/domain.ts`), and a switcher in the site nav drives every route.

**Data path.** 2026 forecasts for the new domains come through the
scoring-free export (`cofire/ship/export.py`, which asserts that no realized
outcome column survives), built by the frozen `look3.build_holdout` on the
registered domain and cut to the footprint. That needed each new domain's 2026
ERC: 715,852 bytes over the same OPeNDAP wrapper, used for forecasts only. The
look counter read 3 before and after. The monolithic 240 MB forecast index is
replaced by per-domain, per-issue bundles (`cofire/ship/bundles.py`, 20 MB for
all 38 issues). The API rebuilds its old cell view from them, and a static
build can serve them unchanged. The demo fixture fell from 12.8 MB to 1.2 MB.

**Denver Place Card.** Denver's drought odds per cell, a note that Denver was
added after the seal and checked on 2022 and 2023 only, and a watershed panel:
the chance of fire-spread conditions above the 80th, 90th and 97th
percentiles in the Upper South Platte above Strontia Springs and the Blue River
above Dillon, averaged over each watershed and labelled as where Denver's
water comes from. One line on post-fire sediment: after the 1996 Buffalo Creek
and 2002 Hayman fires, sediment washed into Strontia Springs Reservoir for
years. Denver's own ERC targets are labelled "Drier than N% of past weeks
here", because in a city they measure dryness against the city's own record,
not wildland fire danger.

**Rendering.** New domains render per the validation rule recorded before
Stage 5 (Denver 16 probability and 11 base rate, Upper South Platte 16 and 11,
Dillon 11 and 16, plus 3 continuous horizons each with no band). Every
base-rate row says "same for the whole city / watershed / county" and gives
its reason one click away.

**A stale claim fixed.** The rendering reasons read survivors from the
original stage 1 table, so the app told users Pueblo d_ge2_h4 "beats its
baseline", a pair the leak-free refit withdrew. Rendering now reads the
five-domain leak-free table. The reason wording also now says validation,
not "the training record".

**Urban Ember Score.** `cofire/ship/ember_city.yaml`, scored by
`cofire/ship/ember_zones.py` with the frozen rule (group weight split evenly
across items). Groups and weights: water before restrictions 0.40 (Denver
Water summer watering rules, conservation guidance, Drought Response Plan;
Denver Water and CSU Extension), ready for smoke days 0.30 (AirNow and CDPHE,
US EPA, CDC), not starting a fire 0.30 (Denver Fire Department, NFPA, National
Weather Service). Denver opens on it. The other four domains open on the
frozen wildland-edge checklist, which is unchanged.

**Hardcoded-statistics lint.** New, `scripts/check_stats.py`, in `make lint`.
It flags fractions, "N of M" counts, worded percentages, and decimals with two
or more places in app JSX text and strings, and allows only the preregistered
criteria phrases. It caught one: the Hindcast page's "30/30 interval tests
passed", in a branch that could only render if the retraction disappeared.
That branch is removed.

**Verification.** Playwright, 54 tests passing, 45 of them new: every route
(map, Predict, Observe, Harden, Hindcast, Method, landing) for every domain;
the Denver cell with its watershed panel; a watershed cell; a non-estimable
target cell (Dillon, drought reaching D2, base rate with the "did not happen in
2022 or 2023" reason); and the switcher moving map and card. Copy lint,
em-dash ban, hardcoded-statistics lint, ruff, mypy strict (97 files), tsc and
`next build` are green. The Python suite passes.

## v1.1 Stage 7: the weekly refresh, and what it found

**`make refresh` (`cofire/ship/refresh.py`).** It asserts the look counter
reads 3 before and after. The target issue is the latest Tuesday whose USDM
map has been released (Thursday 08:30 ET, 13:30 UTC) and whose seven ERC days
are on the server. Missing weekly maps are fetched through `safe_fetch`, their
zip entries are checked, and they are added to the yearly archive, which is
what that archive is made of (the server's 15 September weekly zip is
byte-for-byte the size of the archive's member). ERC is extended by new days
only, over the reconciled OPeNDAP path: the frozen `.sel` with the day axis
sliced first, re-reading the last cached week for revisions and comparing one
day 60 days back exactly. The export, bundles, demo fixture and story are then
rebuilt. The run is idempotent: a second run fetched 1,155 bytes of DDS
metadata and left the export unchanged. It is resumable, since each step skips
what is on disk. Each run appends to `artifacts/ship/refresh_log.json`.

**Found: the latest issue had no drought map.** See the STATUS correction
dated 2026-09-27. The export emitted 2026-09-22 with USDM coded 0 everywhere,
because that week's map was missing and the frozen rasterizer fills a gap with
"none". Larimer and Pueblo's ERC that week was a three-day mean. Look 3's
labels for target week 2026-09-22 carry the same fault (one week per
horizon); they are not recomputed, because the seal forbids another look. The
export now emits an issue only if its USDM map is in the archive and every ERC
day of its week is present, stamps `available_at` (the USDM release, the last
input published), and asserts it is not in the future. Tests guard each rule.

**Gate failed: gridMET revised 2026.** The refresh gate compares a store
domain's daily record, rebuilt into weeks, with its processed 2026 cube on
every complete week. Larimer: first mismatch at the week ending 2026-06-30,
cell (40.6917, -105.6000), fetched 64.1429 against store 71.1429; 17,280
cell-weeks compared, max|diff| 7.0. Pueblo: first mismatch at 2026-08-25, cell
(38.1500, -104.3917), fetched 40.7143 against store 48.0000; max|diff| 7.29.
Day by day the two records differ on 203 (Larimer) and 184 (Pueblo) of 261
days from late February on, up to 20 ERC units. The same path reproduces June
2025 exactly (14,880 cell-days, max|diff| 0), so the server revised its
provisional 2026 file after the stores were built. Following the failure rule,
the revised record is not used: it is set aside as `*.nc.ungated`, both
counties stay on their stored 2026 data cut to complete weeks, and the export
stops at the last issue complete in every domain, 2026-09-15. Adopting the
revision is a decision for the owner (`COFIRE_REGATE=1` re-runs the gate
after one is made). The three new domains' 2026 data is the server's current
version, the only one they have ever had.

**Cost.** The first refresh fetched the 22 September map (3,000,870 bytes)
and Larimer and Pueblo's 2026 daily ERC (about 1 MB). A steady-state week costs
about 3.0 MB for the map plus tens of kilobytes of ERC, roughly 160 MB a year.
The ledger's global ceiling has 59.6 MB left, which carries the refresh for
about 19 weeks unless the ceiling is raised.

**Running without data/ (the cron).** A GitHub runner starts from a clean
clone, and the frozen builder re-rasterizes USDM from 1.2 GB of national
archives each run. `cofire/ship/datapack.py` builds a 13.9 MB pack instead,
stored as a release asset:

- USDM clipped to the frozen config's buffered Colorado box, same zip layout.
  Gate: the frozen rasterizer gives identical cubes from clipped and national
  archives for every domain, 2007 to 2026-09-22, with 0 differing out of
  1,556,330 cell-weeks (`artifacts/domains/usdm_clip_gate.json`).
- The daily ERC caches with their gate markers.
- The store cubes, cut to the ERC variable.
- Colorado's counties for the story map.

Restoring refuses absolute paths, `..` and any entry outside `data/`.
`.github/workflows/refresh.yml` runs Fridays at 18:30 UTC. Each run is its own
ledger session (`refresh-<run id>`, capped at 50 MB) and commits the export,
the ledger and the demo.

**Deployment: blocked by the plan.** `scripts/build_static.sh` builds the whole
app as a static site (26 MB, the bundles served as files) that passes every
route for every domain under `/cofire/` with no HTTP errors (35 of 35 checks).
`.github/workflows/site.yml` builds it on every push and after every refresh.
Enabling GitHub Pages returned HTTP 422, "Your current plan does not support
GitHub Pages for this repository": the repository is private on a plan
without private Pages. The deploy job runs once the repository variable
PAGES_ENABLED is true. Any of these fixes it, and each is the owner's call:
make the repository public, move to a plan with private Pages, or publish the
built site from a separate public repository.

## v1.1: the missing 2022-12-27 map, fixed and rerun on validation

**Root cause: the server's archive.** USDM's 2022 yearly zip on the server is
98,909,841 bytes, last modified 22 December 2022 10:53 GMT, before the 27
December map was released on 29 December. Ours is the same size: the frozen
fetch saved it as served and nothing in our ingest renames, extracts or drops
members. The week was never in the file. (A 2020 member named in lowercase,
`usdm_20200623_M.zip`, is read correctly by the frozen matcher, which
lower-cases names; the new calendar check does the same.)

**Guard.** `cofire/ship/usdm_calendar.py` asserts that each year's archive
holds exactly its Tuesdays, through the latest issue for the current year.
The store builder, the export and the refresh all call it, and the test
deletes a week and asserts failure. 2007 to 2025 now pass.

**Fetch and rebuild.** The map came through `safe_fetch` (1,800,699 bytes,
sha256 8a1a9ab3...) into the national archive and the pack's Colorado archive.
All five stores were rebuilt by the frozen builder. Only each store's
`year=2022.parquet` changed; every 2007 to 2021, 2023, 2024 and 2025 file is
byte-identical. The only changed column is `usdm`, only in the week of
2022-12-27 (outcome weeks are derived from it at load time).

| Area | Changed cell-weeks | Mean category that week, old / new |
|---|---|---|
| Denver | 12 (footprint; 39 in the rectangle) | 0 / 0.375 |
| Upper South Platte | 0 | 0 / 0 |
| Dillon | 0 | 0 / 0 |
| Larimer | 122 | 0 / 0.254 |
| Pueblo | 295 | 0 / 1.227 |

**Rerun, drought targets only, protocol unchanged** (leak-free, paired
shuffled control, circular block bootstrap, BH across all 83 estimable pairs
with the fire rows carried over unchanged, Holm within domain and family, at
least 12 positive weeks). Fire statistics are identical to before.

Drought survivors, paired difference [95% CI], before / after:

| Pair | Before | After |
|---|---|---|
| Denver d_improve1_h2 | +0.2257 [+0.1009, +0.3527] S | +0.2271 [+0.1027, +0.3533] S |
| Denver d_improve1_h4 | +0.2431 [+0.0950, +0.4534] S | +0.2438 [+0.0979, +0.4544] S |
| Denver d_nochange_h2 | +0.0797 [+0.0198, +0.1533] S | +0.0810 [+0.0205, +0.1549] S |
| Larimer d_ge2_h2 | +0.8331 [+0.1668, +1.1959] S | +0.8331 [+0.1669, +1.1959] S |
| Larimer d_ge2_h4 | +0.4861 [+0.0174, +0.8697] S | +0.4861 [+0.0174, +0.8698] S |
| Larimer d_improve1_h2 | +0.2050 [+0.0996, +0.3262] S | +0.2078 [+0.1031, +0.3244] S |
| Larimer d_improve1_h4 | +0.3266 [+0.1822, +0.5115] S | +0.3327 [+0.1887, +0.5114] S |
| Larimer d_improve1_h8 | +0.3713 [+0.2401, +0.5624] S | +0.3731 [+0.2418, +0.5648] S |
| Larimer d_nochange_h2 | +0.1654 [+0.0642, +0.2784] S | +0.1703 [+0.0715, +0.2825] S |
| Larimer d_nochange_h4 | +0.2554 [+0.0946, +0.4240] S | +0.2581 [+0.0922, +0.4267] S |
| Larimer d_nochange_h8 | +0.3478 [+0.1738, +0.5007] S | +0.3448 [+0.1724, +0.4994] S |
| Pueblo d_ge2_h2 | +0.3048 [+0.0913, +0.5134] S | +0.3418 [+0.1055, +0.5890] S |
| **Pueblo d_ge2_h4** | +0.2158 [-0.0018, +0.3728] no | **+0.2427 [+0.0067, +0.4227] S** |
| Upper South Platte d_improve1_h2, h4; d_nochange_h2, h4, h8 | unchanged, S | unchanged, S |

Survivors: 21 to 22. Pueblo d_ge2_h4 passed the original stage 1 test, so
under the claim rule it is claimed again (`withdrawn_by_leak_free_refit` is
now empty). No target meets the agreement rule, before or after.

**Display decisions for the new domains:** none changed. The two near the
threshold: Denver d_improve1_h8, reliability 0.0851 to 0.0839, base rate
before and after; Dillon d_nochange_h8, 0.0667 to 0.0667 (Dillon's store did
not change), base rate before and after. Every other drought reliability moved
by at most 0.0010 and stayed on its side of 0.05. Estimability changed for no
pair. The export's forecast numbers are unchanged; only the reason strings
that quote validation reliability, and Pueblo d_ge2_h4's claim, changed.

## v1.1: data vintages instead of overwrites

**Why.** gridMET revises provisional data, and the refresh used to overwrite.
A forecast issue could then be silently recomputed from numbers that did not
exist when it was published.

**Provisional window: 240 days, measured.** No provisional period was stated
in the gridMET documentation available to this project, so it was measured.
Two vintages of Larimer and Pueblo's 2026 record, fetched a week apart
(2026-09-20 and 2026-09-27), differ from 2026-02-28 (Larimer) and 2026-03-04
(Pueblo) onward. That is 202 and 198 days before the older copy's last day.
Revisions are densest recently: 37% and 58% of September cell-days, and
0% in January and February. A fresh read of October to December 2025 matches
the stored copies exactly (83,904 cell-days). Window = the 202-day maximum
plus a margin of about five weeks, since two vintages a week apart bound the
reach only from below. Record: `artifacts/audit/gridmet_revision_window.json`.

**Rules** (`cofire/ship/vintages.py`):

- Every fetch is stored as its own file under `data/vintages/`, keyed by
  source, domain, year, the days it covers and its UTC fetch time. A vintage
  is never overwritten; the manifest is `artifacts/vintages/manifest.json`.
- The series as of a time is every fetch up to that time, applied in order.
- A fetch may revise days inside the window. Each revised cell-day is logged
  with date, cell, old and new value (`artifacts/vintages/revisions/`). A
  revision older than the window refuses the fetch.
- The refresh re-reads the last 14 held days, plus one day 7 days beyond the
  window that must match exactly.
- Each issue is pinned to the vintage it was first produced from
  (`artifacts/ship/issue_vintages.json`), and a pin never moves. The export
  rebuilds each issue from its own vintage; only issues never produced before
  use the latest. Every export row carries `erc_vintage`.

**The frozen weekly convention is kept.** Larimer and Pueblo's stores hold
one weekly cube per year, resampled from that year's days only, with the
later year's cube winning the week that straddles New Year (so their boundary
weeks are partial means, in training too). Their current-year cube is rebuilt
from the vintage the same way. A first attempt that bypassed the cube changed
the 2026-01-06 issue from the six-day mean it was published with (Larimer
44.11) to a one-day mean (48.23); rebuilding the cube restores it exactly.

**Migration** (`cofire/ship/vintage_migration.py`, run once): 97 ERC files
seeded as vintages. Larimer and Pueblo's first 2026 vintage is the copy the
stores were built from (fetched 2026-09-20 03:01 and 20:17 UTC). Their second
is the 2026-09-27 re-read, adopted through the gate:

| | revised cell-days | dates | largest change |
|---|---|---|---|
| Larimer | 17,580 | 2026-02-28 to 2026-09-18 | 20 ERC |
| Pueblo | 13,769 | 2026-03-04 to 2026-09-18 | 20 ERC |

All 37 published issues per domain were pinned to their original vintage and
reproduce exactly (46,065 rows, no column changed). The 2026-09-22 issue is
new for every domain, Larimer and Pueblo from the adopted vintage, so the
export now runs to 2026-09-22 with real USDM at that week.

**Tests** (`tests/test_vintages.py`): a revision inside the window is
accepted, logged and versioned; a revision outside it fails the gate and
leaves no vintage; an old issue's series is identical after a new vintage
lands, and its pin cannot move; a vintage cannot be overwritten.

## v1.1: the weekly refresh has its own ledger and a per-run ceiling

CI transfers go to `artifacts/ci/ledger.json` (`COFIRE_LEDGER_PATH`), no longer
to the local project ledger. The six transfers the first two CI runs recorded
locally (2,310 bytes) were copied there, and a correction was appended to the
local ledger taking them out of its total, with the entries left as written.

**Measured per-run size: 3,592,759 bytes.** Largest 2026 weekly USDM map,
3,412,666 B (38 maps; median 2,355,010). Plus ERC for five domains, 180,093 B
(7 new days and the 14-day re-read, one gate day, the DDS, all DAP2 wire bytes
by the refresh's own formula). The data pack restored from the release asset
is GitHub-internal and not a source transfer.

**Ceiling: 3 x 3,592,759 = 10,778,277 bytes per run.** It is the run's session
cap, so `safe_fetch` and the ERC reader refuse any transfer that would cross
it. A check step (`python -m cofire.ship.ci_budget check`) then fails the job
with an error annotation if the run's total exceeds it, and writes the total
to the job summary. The allowlist, redirect check, magic-byte check and
error-page rejection run in CI through the same code as locally. The CI
ledger's own budget is a 1.0 GB backstop.

## v1.1: preparing for a public repository

Visibility and ownership are unchanged; making the repository public is a
manual step for the owner.

**Secrets.** All 100 commits were scanned: common key and token formats
(AWS, GitHub, OpenAI-style, Slack, Google API), private-key blocks,
credential assignments with values, tracked `.env` files, databases and logs,
home-directory and scratch paths. None found. The only env file ever tracked
is `.env.example`, whose credentials are blank in every revision. Two personal
identifiers would become public, and git history keeps them whatever the
current tree says, so they are the owner's call:
`tech.mahi@gmail.com` as the tile-policy contact in `app/lib/basemap.ts`, and
the commit author address `evan.msaran@gmail.com` on 97 commits.

**Licenses.** Inventory in `docs/THIRD_PARTY.md`. Changes:

- The landing photo's credit lacked the author and license link that CC BY
  2.0 requires. It now reads "Photo by DVIDSHUB, CC BY 2.0, via Wikimedia
  Commons", with links, matching the Commons file metadata.
- The OpenStreetMap attribution now links to openstreetmap.org/copyright.
- The Method page gains a credits section from `facts.json`: gridMET citation,
  the USDM credit line, USGS, Census, OpenStreetMap, the photo.
- An unused, uncredited CC BY image (`westfork.jpg`) was removed.
- Fonts (SIL OFL) and code libraries (MIT, BSD, Apache-2.0, NCSA) need no
  on-screen credit.
- The repository has no LICENSE; choosing one is the owner's decision.

**Size.** Largest tracked file 2,194,539 bytes
(`artifacts/ship/forecast_issues.parquet`); nothing near 50 MB. Largest blob
ever in history: 12,826,197 bytes (a demo index since removed).

**`AI_USAGE.md`** rewritten from what the repository records:

- The owner directed the research through written instructions.
- The agent generated effectively every file: 96 of 100 commits carry its
  co-author trailer, 3 are the automated refresh, and the untrailed initial
  scaffold's own `AI_USAGE.md` lists its files as agent-generated.
- The four files once marked "intended for hand-rewrite" show no hand rewrite
  in history.
- A section for the student's own contributions is left blank for the student.

## v1.1: drought fallback rates conditioned on the current category

A wiring check of the map and Place Card (every control, every value against
the bundle data) found the controls correct, but three things that made the
output look stuck or wrong:

- **Drought odds are the same for every cell in the same drought category.**
  This is the frozen Markov model: it conditions on the current category and
  the season only. Denver's 52 cells fall in two categories this week, so
  clicking around Denver gives two sets of drought odds. The card now says so;
  fire-spread odds vary per cell.
- **The fallback rate for drought ignored the current category.** Where a
  per-cell drought probability did not pass its check, the card showed the
  area's unconditional seasonal rate. That produced "11% chance of D2 or worse
  in 4 weeks" for Larimer, where most cells are already in D2 or D3. It also
  produced impossible numbers: a 6% chance of worsening two categories from D3
  (USDM stops at D4). The fallback is now the training-era rate among cells in
  the same category, within +/- 3 weeks of the issue, pooled over all seasons
  when that window has fewer than 8 weeks (`conditional_base_rate` in
  `cofire/ship/export.py`). Which targets fall back is unchanged; only what the
  fallback shows. Fire fallbacks keep the seasonal rate. A test asserts no
  exported number describes an impossible move.
- **The fire map looked flat.** Forecast dryness sits mostly between 35 and 65,
  one colour on a 0 to 100 ramp. The ramp now diverges around 50 (typical), and
  the map has a legend. The card's "Dryness for this week" heading showed the 2,
  4 or 8 week forecast and now says so.

**Decided by the owner: unchecked drought targets show no number.** A card
mixed model rows (targets that passed their check) with fallback rows
(targets that did not). The two are different estimators, so a card could
contradict itself: a Denver D3 cell showed D3 or worse 69% (history) against
staying at D3 76% (model). 14 of the 15 area-and-range drought blocks were
mixed.

A drought target that did not pass its check now carries no number in the
export. The card shows the row as "not shown" with its reason, the map leaves
such cells clear with a legend note, and the recorded rate stays in
`{target}_base_rate`. This is stricter than the pre-registration, which said
the regional rate would be shown.

- **Result:** 0 contradictions left among drought numbers across all 141,930
  area, issue, cell and horizon checks.
- **Predict's "most likely category"** is derived only when every move it
  needs was checked. Impossible moves count as exactly zero: no easing from
  none, no worsening from D4, no worsening by two from D3. This week it
  covers Denver 31 of 52 cells, Dillon 59 of 79 and the Upper South Platte
  140 of 202. It covers none of Larimer or Pueblo, whose 4-week drought
  checks failed on look 3; there the page says so.
- **Fire fallbacks still show the seasonal rate.** They disagree with the
  model's rows in 874 of those checks, by at most 0.023 (for example, above
  the 97th percentile showing more than above the 90th). Not changed without
  a decision.

## App Challenge plan: decisions by the owner, 2026-10-04

- **The 2026 seal stays until 2027-01-12.** The model is shown in Beat the
  Model but never scored, and no metric of any kind is computed against 2026
  outcomes before that date. 2027-01-12 is the second Tuesday after the last
  2026 drought map (week of 2026-12-29, released 2026-12-31). It is set now
  and not moved. What is computed at the unseal is to be written down and
  committed before that date; the unseal is look 4. gridMET values for late
  2026 will still be provisional on that date, and the unseal report must
  say so.
- **Denver's-water context numbers.** No exception to the HTML rule in
  `safe_fetch`.
  - **Dillon storage:** the Colorado Division of Water Resources REST API
    (`dwr.state.co.us`, now allowlisted) has a structured feed. Station
    `DILRESCO`, parameter `STORAGE`, daily values in acre-feet, through
    `telemetrystations/telemetrytimeseriesday`. Probed through `safe_fetch`
    and logged in the ledger. On 2026-10-03 it read 164,566 acre-feet, flag
    `O` (provisional).
  - **The watering-rule stage** is hand-entered, with its date and source
    link.
  - **Both are labeled current conditions, not forecasts.**
  - **The probe found a `safe_fetch` fault.** That API answers HEAD with 405,
    and `safe_fetch` read the 405's own headers as the file's length and
    type. It now ignores them and caps the GET by the caller's stated
    maximum; a test covers it.
- **The Denver's-water view is the student's to build.** The AI agent reviews
  it and does not write it. The repository transfer, making it public, the
  student's rewrite and the student's section of `AI_USAGE.md` are the
  student's too.
- **No unsourced fact goes into the app or the video.** The planned claims
  about new Colorado River operating rules and "the worst hydrologic year on
  record" are dropped unless cited.
- **The upstream step-size issue is drafted** in `docs/UPSTREAM_ISSUE_PID.md`,
  for the student to file.
- **Build order:**
  1. Spanish localization and screen-reader parity for the map. The Spanish
     needs review by a person before release.
  2. The weekly brief.
  3. Tested links and a staleness badge.
  4. EnviroScreen, once its size is confirmed against the ledger.

## Links and staleness, 2026-10-04

- **Every outside link is in one registry.** That covers the help links on
  the brief, the program behind each Ember action, the smoke-map link on the
  Place Card, and the data credits (`app/lib/links.ts`, `app/lib/facts.json`).
  - A test fails if a page renders an outside link that is in neither.
  - A weekly workflow (`links.yml`) opens every link and checks the page's
    title, which catches a page that moved and left a soft 404.
  - The link check reads web pages, not data: nothing is cached or parsed
    past the title. So it does not go through `safe_fetch` (which refuses
    HTML by design) or the ledger.
- **Ignition actions get no link.** No checked Denver page was found for
  fireworks, smoking materials, grills or Red Flag work, so those Ember
  actions have no program link rather than a guessed one.
- **The smoke link makes no claim.** It says the app does not forecast smoke
  and points to the AirNow Fire and Smoke Map. The plan's line "when the
  source watersheds burn, Denver gets the smoke" was not used, because no
  source for it was cited.
- **Staleness badge.** A Tuesday issue goes live with Friday's refresh and
  stays the newest until the next Friday, so a current issue is at most 10
  days old.
  - Past 11 days, the map and the brief say the numbers are the last good
    ones and how old they are.
  - It showed on 2026-10-04, because the 2026-10-02 refresh had failed.

## EnviroScreen context layer, 2026-10-04

- **Source.** Colorado EnviroScreen 2.0 (CDPHE, published 2024-11-14), by
  census tract. Denver's 178 tracts were fetched once through `safe_fetch`:
  77,016 B, logged in the ledger. The ledger had about 57.2 MB left
  afterwards.
  - The file is `app/lib/enviroscreen_denver.json`, built by
    `cofire/ship/enviroscreen.py`. It records its source, its fetch time and
    the sha256.
- **Allowlist.** ArcGIS Online (`services3.arcgis.com`) is shared by every
  organization, so the allowlist now also checks paths on shared hosts. Only
  CDPHE's EnviroScreen layers pass.
- **A `safe_fetch` fault found by this fetch, fixed with a test:**
  - A gzip response's `Content-Length` counts compressed bytes while the
    stream yields decompressed ones. `safe_fetch` now asks for identity
    encoding, and caps a compressed body by the caller's stated maximum.
- **Indicators shown:** the overall EnviroScreen percentile, extreme heat
  days, fine particle pollution and asthma hospitalizations.
  - **Drought is not shown.** It is county-level, the same 35.4 in every
    Denver tract, so it says nothing about neighborhoods.
  - **Wildfire Risk is not shown.** It reads high across urban Denver and
    would suggest a wildland fire danger the app does not claim for the city.
- **Context only.** The layer is labelled "context, not a forecast" on the
  legend and the card. It enters no model and no forecast number.
- **No neighborhood names.** Tracts are named by their census GEOID. The
  layer carries no neighborhood names, and none were added without a source.

## CI ledger gap, found 2026-10-04

The refresh workflow committed its ledger only when a run succeeded, so three
runs' transfers never reached `artifacts/ci/ledger.json`:

| Run | Transfers | Bytes | Why it was lost |
|---|---|---|---|
| 37072550722 | 1 | 3,012,266 | refused by the size check (the clipped-archive peers fault) |
| 37237706715 | 1 | 3,012,266 | gridMET refused connections |
| 37237839170 | 11 | 3,192,359 | push rejected by a concurrent push |

- **The fix.** The totals, read from each run's `ci_budget check` output,
  were added to the ledger as corrections (9,216,891 B). Corrections were
  used rather than invented per-URL entries.
- **The September 29 national map size** (3,012,266 B, seen in two of those
  runs) was added to `usdm_national_sizes.json`.
- **Going forward.** A failed run now commits its ledger and size record in
  a separate step, and the success path rebases before pushing.

## gridMET's revision reach outgrew the 240-day window, 2026-10-11

- **What happened.** The 2026-10-09 scheduled refresh failed its gate day.
  Denver 2026-02-03 re-read as 63 against 62 held. Alert issue #3 opened, as
  designed.
- **The measured reach** (`cofire/ship/gridmet_reach.py`,
  `artifacts/audit/gridmet_revision_reach.json`). 2026 days 1 to 120 were
  re-read for all five domains, 752,940 B, logged in the project ledger as a
  probe and not stored as a vintage. Revisions start at **2026-01-31 in every
  domain**, about 250 days before the newest day, with up to 21 ERC units of
  change. Changed cell-days: Denver 1,826, Upper South Platte 12,229, Dillon
  3,459, Larimer 11,553, Pueblo 9,864.
- **The reach is not a fixed lag.** On 2026-09-27 it was 2026-02-28. The front
  moved 48 days in three weeks.
- **New rule: a full year is provisional.** `WINDOW_DAYS = 365`. The gate day
  (window plus 7 days, about 2025-10-02 for an October 2026 refresh) now lies
  in the previous year's file, and that day must re-read exactly. The fourth
  quarter of 2025 re-read exactly in September.
- **What does not change.** Published issues stay pinned to their vintages,
  so no published forecast changes. The refresh still re-reads only the newest
  14 days, so older revised days keep their held values.

## Audits and tool downloads, 2026-10-11

- **npm audit.**
  - Before: 2 critical (`next` 14.2.35, `maplibre-gl` 4.7.1), 7 high, 2
    moderate.
  - Fixed by moving to Next 15.5.27 (React 19) and MapLibre 6.14.0, with
    overrides patching the nested `postcss` and `source-map-js`. MapLibre 6
    parses tiles in a module worker the bundler does not emit, so the worker
    is copied to `public/maplibre` on install (without it no forecast cell
    rendered).
  - After: 0 critical, 0 moderate, **5 high**, all in Tailwind 3's
    build-time file watcher (`braces` <= 3.0.3, through `chokidar` and
    `micromatch`). No 3.x release of `braces` fixes it; the fix is a Tailwind
    4 migration.
  - The exposure is build time only: the patterns are the project's own
    config, and none of it ships to a browser. See the Tailwind entry below.
- **pip-audit**, over the 145 locked packages (`uv export --frozen`).
  - One finding: `multidict` 6.9.0 (CVE-2026-104874), upgraded to 6.9.1.
  - After: 0 findings.
- **Tool and package downloads, recorded in the project ledger** with size
  and reason, under session `v1.2-tools`:

  | What | Bytes |
  |---|---|
  | npm packages for the upgrade, 34 for darwin-arm64, sized from each tarball's Content-Range | 94,804,032 |
  | pip-audit tool, measured as uv cache growth | 52,854,784 |
  | multidict 6.9.1 | 1,654,784 |

  - They are not data-source transfers, so a correction takes them out of
    the data budget's total; the entries stay as written. This follows the
    ledger's earlier CI-split correction.
  - **v1.2 data downloads: 1,020,885 B**, against the session's 40 MB cap:
    SNOTEL April 1 (267,945 B), the gridMET revision-reach probe (752,940 B)
    and one 1,497 B DWR probe.
- **Lighthouse** was run from the local npx cache; nothing was downloaded.


## v1.2 results, 2026-10-11 (preregistration sha256 7af6a4a3...)

The look counter read 3 before and after every stage; nothing was computed on
2026. Folds: held-out years 2012, 2013, 2020 to 2025, with the h-week embargo
and per-fold `erc_pct`. Configuration A on the folds reproduces the frozen
predictors exactly. There are 135 target and domain pairs, 131 of them
estimable.

**Every variant**, pooled over the folds (per-pair means). The paired test is
against configuration A; "qualify" applies the owner's adoption rule.

| Stage | Arm | Mean Brier | Mean reliability | Mean resolution | Paired CI > 0 (of estimable) | Qualify |
|---|---|---|---|---|---|---|
| 1 | A | 0.096246 | 0.00844 | 0.02785 | not selected, not tested |  |
| 1 | S1-ew@26 | 0.097214 | 0.00809 | 0.02641 | not selected, not tested |  |
| 1 | S1-ew@8 | 0.095410 | 0.00705 | 0.02714 | 0 of 131 | 0 |
| 1 | S1-online-a@0.05 | 0.095471 | 0.00759 | 0.02782 | 6 of 131 | 0 |
| 1 | S1-online-a@0.2 | 0.095678 | 0.00735 | 0.02734 | not selected, not tested |  |
| 1 | S1-online-a@0.5 | 0.098255 | 0.00979 | 0.02707 | not selected, not tested |  |
| 1 | S1-online-ab@0.05 | 0.096102 | 0.00800 | 0.02769 | 1 of 131 | 0 |
| 1 | S1-online-ab@0.2 | 0.102642 | 0.01301 | 0.02593 | not selected, not tested |  |
| 1 | S1-online-ab@0.5 | 0.112731 | 0.02173 | 0.02444 | not selected, not tested |  |
| 1 | S1-static-a | 0.096244 | 0.00844 | 0.02786 | 2 of 131 | 0 |
| 1 | S1-static-ab | 0.096101 | 0.00839 | 0.02790 | 4 of 131 | 1 |
| 2 | S2+S1-static-ab@0.1 | 0.117798 | 0.00621 | 0.00426 | 11 of 131 | 0 |
| 2 | S2+S1-static-ab@1.0 | 0.117856 | 0.00813 | 0.00591 | not selected, not tested |  |
| 2 | S2+S1-static-ab@10.0 | 0.118102 | 0.00834 | 0.00589 | not selected, not tested |  |
| 2 | S2+S1-static-ab@100.0 | 0.118136 | 0.00829 | 0.00581 | not selected, not tested |  |
| 2 | S2-offset@0.1 | 0.117901 | 0.00635 | 0.00426 | 12 of 131 | 0 |
| 2 | S2-offset@1.0 | 0.117963 | 0.00818 | 0.00580 | not selected, not tested |  |
| 2 | S2-offset@10.0 | 0.118227 | 0.00844 | 0.00584 | not selected, not tested |  |
| 2 | S2-offset@100.0 | 0.118265 | 0.00845 | 0.00579 | not selected, not tested |  |
| 3 | S3-drought@16 | 0.086385 | 0.01001 | 0.03824 | not selected, not tested |  |
| 3 | S3-drought@256 | 0.085262 | 0.00859 | 0.03756 | not selected, not tested |  |
| 3 | S3-drought@4 | 0.087542 | 0.01091 | 0.03810 | not selected, not tested |  |
| 3 | S3-drought@64 | 0.085481 | 0.00888 | 0.03787 | not selected, not tested |  |
| 3 | S3-fire@0.0 | 0.111767 | 0.00190 | 0.00763 | not selected, not tested |  |
| 3 | S3-fire@0.25 | 0.111741 | 0.00192 | 0.00766 | not selected, not tested |  |
| 3 | S3-fire@0.5 | 0.111744 | 0.00195 | 0.00767 | not selected, not tested |  |
| 3 | S3-fire@0.75 | 0.111776 | 0.00198 | 0.00767 | not selected, not tested |  |
| 3 | S3-fire@1.0 | 0.111837 | 0.00203 | 0.00766 | not selected, not tested |  |
| 3 | S3 (kappa 256 drought, w 0.25 fire) | 0.094088 | see S3 rows | see S3 rows | 18 of 131 | 0 |

### Stage 1: recalibration

- **Gate.** All eight online variants passed the delayed-feedback gate at
  h = 2, 4, 8, and each fails it with the delay shortened by one week or
  removed (`tests/test_v12_gate.py`).
- **Selected:** online learning rate 0.05 for both online families; EW
  half-life 8. Of the static variants, intercept and slope.
- **Online variants** lower the mean Brier most (EW 0.095410 against
  0.096246). None can ship before the unseal, and none qualifies once BH is
  applied.
- **The preregistered warm-start penalty was strong.** It held the static
  recalibrations near identity: intercepts within +/-0.01, slopes 0.93 to
  1.00.
- **One pair qualifies and is adopted:** Larimer `d_improve1_h4` with
  S1-static-ab.
  - Paired difference +0.000616 [+0.000252, +0.000944], p 0.0005; BH and Holm
    reject.
  - Reliability 0.01122 against 0.01130; BSS against configuration A
    +0.00097.
  - Below the 0.10 "surprisingly strong" threshold, so no rerun.
- **Base rate to per-cell.** 17 h4 and h8 pairs render the regional base rate
  for reliability today; **0** move to per-cell odds.

### Stage 2: level from slow climate state

- **Ridge weight selected:** 0.1.
- **S2-offset makes things worse:** mean Brier 0.117901 against 0.096246.
  Forcing each week's average to a climate-predicted rate, which varies
  little between years, removes configuration A's knowledge of the current
  drought state.
- **Base-rate cost recovered:** median **0.6%**, positive in 80 of 135 pairs.
- **Recalibrating on top** does not rescue it (0.117798).
- **Adopted:** 0.
- **Not included:** the precipitation deficit. Precipitation for 2007 to 2017
  is not on disk, and precipitation was not a source this session could
  fetch.
- **SWE feature.** Implemented as written ("percent of median ... April
  through October, and 0 otherwise").

### Stage 3: partial pooling

- **Selected:** drought kappa 256 effective weeks, the largest grid value;
  fire w = 0.25.
- **Pooled drought Brier** 0.085262 against configuration A's 0.088485.
  Mean reliability improves in all five domains:

  | Domain | A | S3 |
  |---|---|---|
  | Denver | 0.0118 | 0.0100 |
  | Dillon | 0.0098 | 0.0063 |
  | Larimer | 0.0074 | 0.0056 |
  | Pueblo | 0.0080 | 0.0059 |
  | Upper South Platte | 0.0051 | 0.0041 |

- **Fire** barely changes (0.111741 against 0.111767).
- **Paired test.** 18 pairs have a CI above zero, and **none survives BH**:
  the smallest p is 0.0029 against a first-rank threshold of about 0.00076
  across 131 tests. Adopted: 0.
- **Survivors.** The validation test with the stage-3 arm gives 23 against
  configuration A's 22: Pueblo `d_improve1_h2` and `d_improve1_h4` gained,
  Pueblo `f_gt90_h8` lost. No stage-3 arm is live, so the app's claims are
  unchanged. Estimable validation pairs are unchanged (83), as they must be.
- **Two corrections to the preregistration's own wording:**
  - Configuration A's Dirichlet prior is applied as 4 rows, not 4 weeks as
    its docstring says, so the remark that "kappa = 4 is configuration A's
    strength" was wrong. The binding conversion (weeks times cells) was used.
  - The selected kappa sits at the edge of the grid. More pooling might help;
    that is future work, not run.

### Stage 4: lag-aware intervals

- **Gate.** The fixed-step lagged reference PID passed at h = 2, 4, 8.
- **Result: 0 of 15** domain and horizon pairs pass every criterion, so no
  band is drawn. Passes per criterion:
  - minimum rolling 13-week coverage: 9;
  - conditional coverage: 7;
  - longest miss run: 0;
  - width ratio CI below 1: 3.
- **The miss-run bound fails everywhere** (runs 86 to 1,600 cell-weeks
  against 60). A stream ordered week then cell with 52 to 480 cells per week
  turns one bad week into a run that long. Recorded as future work; the bound
  stands.

### What went live

- **Only Larimer `d_improve1_h4`**, recalibrated (S1-static-ab), for issues
  from 2026-10-13. No published issue changes.
- **The live parameters** were fitted on the shipped configuration A's
  2022 to 2025 predictions (98,400 rows): a = 0.0279, b = 0.9562. They are in
  `artifacts/v12/live_arms.json` with a calibration-scope fit window, read
  through the strict loader.
- **Rendering** is unchanged: the pair already renders per-cell odds, and its
  pooled reliability 0.0112 is under 0.05.
- **Survivor recheck, leak-free.** The recalibration was fitted on
  training-year out-of-fold predictions only. The claim holds: +0.3336
  [+0.1901, +0.5119] against configuration A's +0.3266, and no other pair's
  status changes.
- **The other 134 pairs** stay on configuration A.

**Ideas logged as future work, not run:** a larger kappa grid; a miss-run
criterion counted in weeks rather than cell-weeks; online recalibration after
the unseal, when 2026 outcomes may be used.

## Basemap for the deployed build, 2026-10-12

- **Secrets scan, rerun over the full history** before the repository goes
  public. 142 commits, 110 MB of patch text: no key, token, private-key,
  credential or bearer matches; no tracked env, key, database or log files
  besides `.env.example` (directory names only, every revision); no local
  paths. The two personal addresses already noted remain the owner's call:
  `tech.mahi@gmail.com` in `app/lib/basemap.ts`, and the commit author
  address on 134 commits.
- **The `pmtiles` CLI**, by the owner's choice of Homebrew because no
  go-pmtiles release publishes checksums.
  - The bottle (pmtiles 1.31.2, arm64_tahoe) is 15,906,842 B, sha256
    `97a0329f0e88fbbac341495b5615b1d4086dc1401f60d68c5ac1a4971de70e96`. That
    matches the formula, and `brew` printed "Verifying checksum".
  - Installed binary: 54,309,250 B.
  - Recorded in the ledger as a tool download and corrected out of the data
    total, like the other tool downloads.
- **The data cap** was raised to 3.2 GB by the owner.
- **Allowlist.** `build.protomaps.com` is added, restricted to the dated
  daily builds (`/2026`, `/2027`). The CLI makes its own range requests, so
  the URL was checked with `safe_fetch`'s `check_url` and the transfer is
  recorded from the CLI's report.
- **The extract.** Daily build 2026-10-11, bounding box
  -106.377, 37.635, -103.954, 41.098 (all five areas plus 0.1 degree).
  - Dry runs: max zoom 10 gives 6.7 MB, 11 gives 12 MB, 12 gives 23 MB,
    13 gives 51 MB, 14 gives 112 MB. **Max zoom 13** is the largest under
    60 MB.
  - Archive: 51,261,167 B, sha256
    `b661b095ddda73c62b705e478a31deea66c7f3b745e2411e9361c79b7bb50fba`.
  - About 54 MB transferred; the CLI reports it rounded, and that is what the
    ledger records.
- **Kept out of git** (GitHub warns above 50 MB, and history keeps
  everything) as the release asset `basemap`. The site workflow downloads it
  and checks its sha256 before building.
- **Glyphs.** Noto Sans Regular, ranges 0-255 and 256-511 (OFL), 208,144 B
  with the license. Self-hosted, so the deployed map calls no third-party
  server. Blob hashes verified against GitHub.
- **Style.** Dark and low contrast from the ink tokens; place names in a
  muted light grey with a dark halo. The OSM and Protomaps credit sits top
  right, visible at 375 px and clear of the legend and controls.
  - It was hidden by CSS before, on the claim that the legend carried it,
    which it did not.
  - If the archive cannot be read, its layers hide and the plain background
    shows; the forecast cells still draw.
  - Local development keeps OSM.
  - `scripts/build_static.sh` no longer forces OSM, which the project's own
    tile policy rules out for a deployed build.
- **Local check of the static export** (Pages layout under `/cofire/`, with a
  range-capable test server):
  - every tile request answered **206**;
  - the basemap renders at zooms 7 to 14 in all five areas and both
    languages;
  - place labels show at each area's fitted zoom;
  - with the archive blocked, the fallback holds.
- **Lighthouse**, mobile, median of three, with gzip as Pages serves files:
  map 91/100/100, Place Card 90/100/100. Without compression the test server
  measured 73 and 74; the difference is the 1.07 MB MapLibre chunk served
  raw.
- **Not yet done:** the deployed checks (206 against the Pages URL, every
  area in both languages, Lighthouse, screenshots) and the alert test in the
  new repository. They wait until the repository is public with
  `PAGES_ENABLED=true`, a manual step for the owner.

## v1.3 Stages 1 to 3: what lies behind each number, 2026-10-15

- **Tables.** `cofire/v13/explain.py` writes, per domain, the tables behind
  every live probability, from the training rows the export fits on
  (2007 to 2021, asserted):
  - drought: the Markov row used for each category and month, with per-year
    destination counts;
  - fire: the damped logistic's coefficients, and illustrative per-year
    counts by dryness band and season;
  - the adopted v1.2 arm.

  They reproduce the published probabilities exactly: 29,986 checks on the
  newest issue, 0 mismatches (`tests/test_v13_explain.py`). They are
  committed under `artifacts/v13/explain/`, because the static site build has
  no data stores to recompute them; they change only if the model or an
  adoption does.
- **Frequency framing.** "In 100 weeks like this one, about N ..." with a
  10x10 icon array, N rounded exactly as the percentage beside it (a test
  walks every row in every area and range). Regional base rates say "in 100
  weeks at this time of year across this area".
  - The targets describe the category **exactly h weeks later**, so the
    sentences say "4 weeks later", not the brief's suggested "within 4
    weeks", which would describe a different event.
- **Weeks like this one.**
  - Drought: the training cell-weeks in the same state the live model
    conditions on (category with month, season or all year, whichever row the
    model uses), five most recent years plus all years. A test reproduces the
    odds from the counts and the prior.
  - Fire: the live model is a smooth curve over the dryness percentile, not a
    table, so similar weeks (same 10-point band and season) are shown as
    illustration and labeled as not matching the odds exactly.
- **Why did this change.** The week-over-week change splits into the cell's
  own state, the time of year, and any change of forecast method between the
  issues (the v1.2 arm starting).
  - The fire model has no calendar term, so its change is all state; a
    regional rate's change is all season.
  - A residue under 0.001 is the bundles' four-decimal rounding and goes to
    the state part.
  - The note shows only above 5 points. A test checks that the parts sum to
    the total for every cell and target.
- **The brief** gains one frequency line per drought category, with an icon
  array split into stayed, eased and worsened.

## v1.3 Stage 4: the demo film (first cut), and Stage 6: open data, 2026-10-15

### Two fixes found on the way

- **The site build failed on `f0f665b`.** `next/font/google` could not parse
  the font URLs Google Fonts returned. The three OFL families are now
  committed in `app/fonts/` (the same latin files, byte for byte) and loaded
  with `next/font/local`, so the build fetches nothing.
- **The deployed basemap drew rivers as wedges.** The Protomaps water layer
  carries rivers as lines; a fill over a line closes it into a polygon.
  Clear Creek and the North Fork of the South Platte crossed the map west of
  Denver as blue wedges. The fill now takes polygons only, and a line layer
  draws the rivers.

### The film

- **Built in code and rendered locally.** Remotion 4.0.531 (pinned, over two
  weeks old, lockfile committed).
  - It renders with the Chrome for Testing headless shell that Playwright
    had already installed, so no browser was downloaded.
  - WebGL is software-rendered ("swangle"), so rendering is CPU only.
  - The free license covers an individual (`film/LICENSES/REMOTION.md`).
  - No account, no cloud, no AI voice.
- **Three corrections to the brief, so the film stays true:**
  - 22 survivors, not eleven;
  - 2026 has been looked at three times, not once: the film says every look
    is counted and scoring opens at the unseal;
  - there is no address search: the magic moment picks Denver and taps a
    square.
- **Every number is traced at render time.** `src/trace.ts` hands out every
  number from `public/data/film.json`, and each entry names its source file
  and key. After each frame, `src/Guard.tsx` reads all the text on screen and
  fails the render on any run of digits not handed out by a field. It caught
  "sha256" typed into a label; that card now says "fingerprint". The
  narration and captions use `{field}` references and refuse typed digits.
- **The unseal date is now data.** `app/lib/seal.json` is read by the
  scoreboard, the film and (stage 7) the unseal script. Before this it was a
  constant in the scoreboard page.
- **Captures are the production build, frame-stepped.**
  - Playwright drives the static build, served locally with range requests
    by `scripts/serve_static.py`, with the clock fixed and every other request
    aborted.
  - MapLibre animates on the real clock, which a frame-stepped capture
    cannot follow. The fly-in therefore sets the camera on every frame (an
    eased path between the two cameras the app itself chose) and waits for
    the map to draw each one.
- **The maps in parts 1 and 2 are drawn by MapLibre inside Remotion**, with
  the app's own style and basemap. The drought progression comes from the
  40 bundles the app published: observed inputs, not outcomes, so nothing is
  computed against 2026.
- **The Roberts Tunnel is drawn schematically**, from Dillon Reservoir's
  basemap label point to the nearest Upper South Platte cell, and labeled so.
  The project's sources do not give the tunnel's path.
- **Sound:**
  - 11 Kenney CC0 sounds (1.25 MB, priced first);
  - a silent music placeholder with the ducking applied;
  - two-pass loudnorm, which measured -14.0 LUFS and -1.2 dBTP on the scratch
    mix;
  - scratch narration from macOS `say`, labeled on screen until the
    student's `audio/voice.wav` replaces it.
- **Timing.** After the animatic, the phone beat was cut from 3.9 to 2.5 s
  and everything after it moved 1.4 s earlier (2:51.0 to 2:49.6). Line 23
  ("January 12, 2027") was given a longer slot, because spoken dates run
  long.
- **Downloads this session:**
  - tools: 46.7 MB (npm, measured as cache growth; priced at 68.0 MB);
  - assets: 1.25 MB (Kenney) and 7 kB (CC0 text);
  - data: 0;
  - total: well under the 600 MB cap.
- **ffmpeg** was already installed from Homebrew (8.0.1, December 2025, with
  loudnorm and libass), so nothing was downloaded for it.

### Open data

- **Formats:**
  - every published issue as CSV and GeoJSON (gzipped, about 0.4 MB each);
  - the latest issue uncompressed, plus as compact JSON;
  - `index.json` as the endpoint, listing every file with its size and
    sha256, the fields and the license.
- **License:** CC BY 4.0, with the upstream credits from `facts.json`.
- **Fields are those the brief names:** issue, vintage, area, cell (and its
  centre), target, horizon, live probability, rendering state and reason.
  The probability is the bundle's exactly; a target the app does not show
  has no number. The vintage is the issue's pin in
  `artifacts/ship/issue_vintages.json`.
- **Size.** A whole issue uncompressed is 9.5 MB as CSV, so 40 issues would
  add about 380 MB to the site; gzipped, all of it adds 21 MB. Pages compresses
  the uncompressed latest files in transit.
- **The `/data` page** is the data dictionary in English and Spanish (draft,
  under the existing notice). Its field list comes from `index.json`, so the
  page and the files cannot disagree; a browser test checks both languages
  and that the CSV header matches.
- **`/data` was added to the list of routes with Spanish text**
  (`components/LangSwitch.tsx`). The reserved Spanish review notice itself,
  meaning its text and its reviewed flag, is untouched.
- **The API serves the same files** at `/open/{name}`. It builds them once
  into a gitignored cache, including when serving the demo fixture, which
  is never written to.

## v1.3 Stage 5: reviewer legibility, 2026-10-15

- **`research/` holds what does not ship:**
  - the v1.2 stage runners and their scoring (`stage1` to `stage4`,
    `snotel`, `preds`, `evaluate`, `gate`);
  - four one-off diagnostics (`sensitivity`, `pid_audit`, `gridmet_reach`,
    `vintage_migration`).

  `research/README.md` says, for each, why it does not ship. The one
  adopted v1.2 arm still ships through `cofire/v12/live.py` and `recal.py`.
- **What "shipped" means:**
  - every module reachable by import from the product's entry points: the
    API, the refresh, the export, the site build, the open data, the forecast
    record and the facts;
  - found by `tests/test_shipped_path.py`, which also fails if any `cofire/`
    module imports `research`, or if loading the entry points loads it.
- **`cofire/model/` was not touched.** Its own non-shipping arms (LightGBM,
  the physics-informed ConvLSTM, the ensemble, SubX, the ablations) stay where
  they are. Moving any of them would change the configuration hash, and the
  frozen-model test would rightly fail. The README says so.
- **Documentation and types:**
  - 96 docstrings were added on the shipped path, with no code changed; a
    test requires one on every public function and class there;
  - mypy strict now also covers `cofire/v12`, `cofire/v13`, `cofire/api` and
    `research` (three typing fixes in the API);
  - CI runs the same scope.
- **The architecture diagram** is defined once in `scripts/architecture.py`,
  which writes both the README's Mermaid block and `docs/architecture.svg`.
  Mermaid's own renderer is not on the allowed-tools list. CI checks that
  both are current.
- **The README opens with "For reviewers":** a summary, the one-command run,
  where things live, and links to the preregistrations, corrections and film.

## v1.3 Stage 7: the executable unseal, 2026-10-15

- **The unseal is written down before the date, as the owner decided.**
  `docs/PREREGISTRATION_UNSEAL.md` is new. It fixes what is scored, and it
  mirrors look 3 and the scoreboard's promise:
  - every published forecast, verified by sha256, scored as published;
  - only target weeks on or before 2026-12-29 count;
  - Brier score, reliability and resolution terms, and a reliability
    diagram;
  - the pass criterion: reliability at most 0.05 where at least 100
    cell-weeks are scored, for targets shown as a per-cell probability;
  - regional rates are reported but not judged;
  - dryness errors (MAE, RMSE, bias) are reported without a criterion;
  - no skill claim, and no refit.
- **This preregistration was drafted by the AI agent.** The owner should read
  it, and change it if needed, before 2027-01-12. Any change must update the
  pinned hash in the script, and the tests fail until it does.
- **`scripts/unseal_2026.py` checks seven preconditions before reading
  anything from 2026:**
  - the date, from `app/lib/seal.json`;
  - `COFIRE_ALLOW_LOOK=4`;
  - `cofire/model/` matches `FREEZE_COMMIT`;
  - the configuration hash;
  - both preregistrations' hashes;
  - the look counter at 3;
  - a new output directory and a clean tree.

  It names every failure at once. It writes once, into a new directory,
  then records look 4 through the frozen `record_look`.
- **Tests** (`tests/test_unseal_2026.py`, 15):
  - each refusal is exercised with a mocked clock and mocked repository
    checks;
  - the readers of published forecasts and of 2026 outcomes are traps, so a
    test fails if anything is read early;
  - the scoring functions run on synthetic data only.
- **It was not run.** `artifacts/unseal_2026/` does not exist.

## v1.3 Stage 8: monitoring, accessibility, performance, 2026-10-15

### Monitoring

- **The daily smoke run** is in `.github/workflows/smoke.yml`, 13:17 UTC. It
  runs every route in both languages, a Place Card from the latest issue, a
  206 on the basemap and the open data index (`app/e2e/static/smoke.spec.ts`).
  - Until `PAGES_ENABLED` is `true` it builds the static site with the
    verified basemap and serves it locally (`scripts/serve_static.py`).
  - After that it checks the deployed address.
  - A failure opens an issue, or comments on the open one, the same way the
    refresh's alert does.
  - `force_fail` tests the alert.
- **The local static server** is now `scripts/serve_static.py`, used by the
  film, CI and Lighthouse. It was the film's.

### Accessibility

- **axe on every route in both languages**, at desktop and phone sizes, runs
  in a new CI job (`a11y`) against the production static build, with
  WCAG 2.1 A and AA rules (`app/e2e/static/axe.spec.ts`).
  `@axe-core/playwright` 4.13.0 is pinned and recorded in the ledger.
- **Before the fixes:**
  - 15 of 20 desktop routes had serious violations, all color contrast,
    from one token;
  - on phones there were also four horizontally scrolling tables that could
    not be reached by keyboard, and a definition list with wrapped terms.
- **After:** 0 serious or critical violations on all 40 route, language and
  size combinations.
- **The fixes:**
  - ochre darkened from #9a7420 to #7d5e14, the same hue: ochre text on
    paper rises from 3.8 to 5.4, and on ochre-soft from 3.4 to 4.8;
  - the segmented controls' sub-labels go from 75% to 90% opacity;
  - the Hindcast replay button uses paper text;
  - each scrolling table is a labeled, focusable region;
  - the timeline legend's swatch moved inside its term.
- **The Spanish review notice is unchanged.** It shares the ochre token, so
  it is now darker too, but its text and its reviewed flag were not edited.
- **The test checks the settled page.** It waits for finite animations to
  end, because a fade caught halfway is not the page a reader sees.

### Performance

Lighthouse mobile, median of three, against the static build served with
gzip (`scripts/lighthouse_static.sh`; `artifacts/v13/lighthouse/`):

| Page | Before | After | LCP before to after |
|---|---|---|---|
| Map | 90 | 94 | 3.6 s to 3.1 s |
| Place Card | 90 | 94 | 3.6 s to 3.1 s |
| Brief | 91 | 94 | 3.5 s to 3.1 s |

Accessibility and best practices are 100 on all three.

- **What moved the scores:**
  - MapLibre loads with `next/dynamic`, so the map page's first-load
    script fell from 505 kB to 148 kB;
  - the Motion animation library left the shared controls (`ui/Animated`
    holds the two animated ones, and the disclosure uses a transform-only
    CSS slide), so the map and the brief no longer load it;
  - the schemas and their validator load with the first fetch, not with
    the page.
- **Tried and reverted:**
  - not preloading the serif (first paint got worse);
  - inlining the CSS (the map dropped to 92).
- **Not reached: 95.**
  - Removing every web font as an experiment did not move the simulated
    LCP at all. What remains before first paint is the framework's own
    script (about 100 kB) and the two translation tables.
  - Loading Spanish only when asked for would mean moving the reserved
    review flag out of `es.ts`, so it was left for the owner to decide.

## The demo film: second pass on the second half, 2026-10-16

The owner watched the first cut. The opening worked; from the trust section
on, several shots were "not properly done". They were rebuilt, not patched
(`film/REVIEW.md`, "Second pass", has the full list).
- **Held-out year as one diagram.** The freeze card and the look counter
  became a single bar of the years.
  - Validation and calibration are drawn from `facts.json`
    (`split.validate`, `split.calibrate`), traced like every other number.
  - Two shots of cards said less than one picture of what is held out
    and why.
- **The leak as a picture of the mistake.** It shows an arc from the
  forecast week back to today, then strikes it out. Before, it was two
  rows of labels. The claim is unchanged: outcomes are known only 2 to 8
  weeks after a forecast is made (the horizons, read from the bundle).
- **Ending on the map.** The film opens on the live map and now closes on
  it, pulling back to all five areas, instead of on a page capture. This
  needed no new capture and no new number.
- **Map edges.** The opening and finale fade the map at the edge of the
  bundled tiles. The fade is computed from the zoom the tiles are drawn
  at. Masking at the extract's nominal bounds was tried first; it hid the
  Pueblo area.
- **Nothing outside the film changed.** The app, the model and the data
  are unchanged. Every on-screen number is still checked against
  `public/data/film.json` on every frame.
