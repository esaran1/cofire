# Decisions (v0 + v0.2)

- Next.js lives at repo-root `app/`; Python packages are `cofire.model` and `cofire.api` (matches `mypy --strict cofire/model`).
- Dev-subset splits (2019–2026, not 2004–2021): train 2019–2022, validate 2023, calibrate 2024–2025, hindcast 2026. Fetch 2018 as a 365-day warmup for SPI/rolling windows.
- Week index is USDM Tuesday (W-TUE, label right). Issue date = that Tuesday; features may use data through that date inclusive.
- USDM ordinal: shapefile `DM` 0–4 (D0–D4) unchanged; unmapped cells (None) → 0, so None and D0 share 0 as specified.
- gridMET via the Climatology Lab yearly NetCDF4 file server (`www.northwestknowledge.net/metdata/data`), spatially subset with HDF5 byte-range reads so CONUS files are never stored. THREDDS NCSS (port 8080) is documented as a fallback but was unreachable from this environment.
- USDM yearly `YYYY_USDM_M.zip` contains nested weekly zips (`USDM_YYYYMMDD_M.zip`), not loose shapefiles. Rasterize opens the inner zip per Tuesday.
- "Replay May 1" uses issue date 2026-05-05 (first USDM Tuesday in May 2026) so 4w/8w land in June.
- Fire overlay: NIFC 2026 CO perimeters > 1000 acres. If none intersect Larimer, the map says so; the fire table still lists statewide qualifying fires.
- Conformal quantile `qhat` is frozen on the calibrate split; only ACI alpha updates online. Hindcast coverage is reported, never used to retune `qhat`.
- Fire-spread condition index = mean(ERC percentile, BI percentile), post hoc, not a third trained target.
- Observation feature weights are documented constants; the UI nudge is a cached model delta from bumping a count by 1, never an animation.
- Identity is an anonymous `device_id` in localStorage; no accounts.
- Tile demo uses pre-rendered PNG overlays plus COGs; rio-tiler serves COG tiles when present.
- Optional SMAP/VIIRS/HRRR/RAWS/NFMD are skipped unless a key is present and the fetch succeeds.
- OpenFreeMap dark style for the basemap (no API key); Carto dark raster tiles as fallback.
- `DATABASE_URL` (or `COFIRE_DATABASE_URL`) selects SQLite by default, Postgres when set.
- If TIGER is unreachable, Larimer/Colorado bounding boxes fall back to Census-published extents hard-coded as constants (not invented geometry).
- ERC NCSS variable is `energy_release_component-g`; BI is `burning_index_g` (gridMET 2024 catalog).
- SNOTEL station list is filtered client-side to `stateCode=CO` and `networkCode=SNTL` because the AWDB list endpoint ignores network filters.
- Percent-of-median SWE uses training-window medians by station and day-of-year (leakage rule), not a 1991–2020 climate normal.
- D4 is kept as 4 (already the top of 0–4). P(category ≥ 2) = D2 or worse; P(category ≥ 3) = D3 or worse.
- `make demo` forces `COFIRE_DEV_SUBSET=1`. Statewide is an explicit `COFIRE_DEV_SUBSET=0`.
- Git SHA in metrics is `"uncommitted"` when HEAD is missing.
- CI uses committed tiny forecast fixtures; no network in pytest/Playwright.
- PI-ConvLSTM tiles are 32×32 with 8-cell overlap (stride 24). Larimer (~16×30) is padded to one 32×32 tile; loss is masked to valid cells.
- Hydro coefficient `k` is the 99th percentile of week-over-week `(-fm1000_anom) / pet` on the training split, positives only. Not tuned on val/hindcast.
- Fuel bound `f(vpd, precip_28d)` is OLS on the training split with signs clipped to be monotone (df/dVPD ≤ 0, df/dprecip ≥ 0). Not retuned later.
- λ_hydro = λ_fuel = 0.1 a priori. Three reported configs: (0,0), (0.1,0), (0.1,0.1). No λ search on val or hindcast.
- Bootstrap intervals are residual bootstrap (300 draws of calibrate-split residuals added to the point forecast), the same residual pool for both arms so the comparison is not confounded by retraining cost.
- Shipping arm = lowest validation ERC-percentile MAE, ties broken by drought MAE. Named in About and metrics.md.
- Why bars = grouped TreeSHAP of the LightGBM ERC-percentile model at the selected horizon, even if ConvLSTM ships, labeled as LightGBM attribution.
- HLS / Sentinel-2 10–30 m downscaling is `COFIRE_ENABLE_HLS=0` by default; UI legend always prints the displayed resolution (4000 m unless the flag is on and a downscaled layer actually loaded).
- Hindcast 2026 is a locked holdout. `make calibrate` fits qhat/bootstrap on 2024–2025 only. `hindcast.py` is the first look at 2026 per config and appends `artifacts/hindcast/run_log.json` (git SHA, config hash, timestamp). Repeated peeks are visible. A change made after seeing hindcast numbers must be logged as **post-hindcast change**.
- Yearly gridMET weekly cubes overlap by one Tuesday at each year boundary. `cubes_to_frame` drops duplicate (time) keeping the later file before lags/rolls, otherwise shift() leaks a same-week duplicate into lag-1.
- Baseline-floor gate: drought persistence must beat (or tie) random at 2/4/8 weeks. ERC persistence must beat random at 2 weeks only; 8-week ERC persistence losing to a constant mean is expected. Drought climatology vs random is not a hard fail on the 2023 Larimer split because that year is almost all D0 so the train-mode random wins MAE. The climatology implementation is checked on raw ERC cell-woy means vs a constant train mean.
- LightGBM and PyTorch in one process: pin `OMP_NUM_THREADS=1` (and LightGBM `num_threads=1`, `torch.set_num_threads(1)`). Unbounded OpenMP after LightGBM hung the PI-ConvLSTM fit at ~0% CPU.
- **post-hindcast change** (scoring only, hyperparameters frozen): `merge_pred` dropped incoming baseline `*_hat` columns when the truth parquet already had them, so hindcast skill vs persistence was identically 0 and the persistence row was the shipping arm. Incoming pred now wins. Re-reported hindcast skill/CIs are **contaminated** (second look; `run_log.json` look_index increments). Point MAE from `evaluate_arm` on stored hats was already correct. NIFC `attr_FireDiscoveryDateTime` is epoch-ms; parsing without `unit="ms"` produced 1970-01-01. Parser fixed; fires.md re-emitted and is also contaminated.
- Statewide (`COFIRE_DEV_SUBSET=0`) was requested but **not started**: STATUS is No-go, and the standing rule is that statewide runs only on Go or Partial. The blocker is not compute, it is that no trained arm beats persistence on the 2026 hindcast at 4 or 8 weeks for either target. Running statewide on these weights would burn hours of CPU to widen a forecast that loses to "next month looks like this month", and the demo-data freeze would then bake those numbers into the judge-facing fixture. Deferred pending an explicit override or a model that clears the bar. The `logs/statewide.log` + per-stage checkpoint/resume harness is therefore also deferred, since it has nothing to run.
- UI reads real artifacts, not placeholders. `/meta` now returns `manifest_hash`, `git_sha`, `status` (parsed from STATUS.md), `shipping_arm_basis`, and `hindcast_looks`; `/hindcast/summary` returns parsed overall-stratum coverage rows plus `look_index`/`contaminated`; `/hindcast/fires` returns `n_in_domain` and the nearest-cell caveat. The Hindcast screen renders the contamination banner and the 0-in-domain warning; About renders the No-go verdict, MANIFEST hash, and look count; the map legend prints shipping resolution and issue date. Honesty facts (contamination, 0 in-domain fires, conformal collapse to 0.485) are surfaced in the UI rather than left in artifacts/ where only a reader of the repo would find them.

## v0.5 (diagnose the No-go)

- **Conformal collapse was a bug, reproduced for free on LODO.** Two defects in `conformal.py`, both
  narrowing intervals, neither requiring a shifted stream. (1) `aci_update` passed the *coverage*
  target (0.90) where ACI needs the *miss-rate* target (0.10), making the only stationary point a 90%
  miss rate; on a stationary synthetic stream the old code converged to 0.26 coverage. (2)
  `interval()` rescaled a frozen 0.90 `qhat` by `(0.10/alpha)`, which is not the quantile ratio
  (−51% too narrow at alpha=0.5). Fixed: the update uses `1 - target`, and `CellState` now stores the
  calibrate-split residual pool so `interval()` re-quantiles at the current alpha. The pool is fit on
  calibrate only and never refit on a holdout, so split conformal's guarantee is preserved.
  LODO 2020 h=4 coverage went 0.266 → 0.526. Ten regression tests in `tests/test_conformal_aci.py`;
  three of them fail on the old code.
- **The ACI learning rate is not the bottleneck; the pre-registered hypothesis is refuted.** Sweeping
  {0.01, 0.05, 0.1, 0.25} against injected step changes, no learning rate recovers coverage under a
  severe shift — alpha saturates at the 0.01 floor in every case, and 0.25 is worse (overshoot).
  lr stays at 0.01.
- **A second, non-bug limit sits behind the bug.** After the fix, LODO coverage is still only
  0.52–0.67. Test-year |residuals| are ~2.5x calibration-year at p90, and *static* split conformal
  with no ACI at all gives 0.348 on LODO 2020. A single-year calibration pool cannot cover a harder
  year. The remedy is a multi-regime calibration pool or a drought-conditioned score, not tuning;
  pre-registered, not applied.
- **LODO years are 2020, 2021, 2024, 2025, not the 2002/2012/2018/2020 in the brief.** 2002 and 2012
  are not in the feature store (fetch warmup starts 2018), and 2018 is wet (mean USDM 0.147), so the
  four driest available years stand in. They are weak analogs for 2026: the driest available is 2021
  at mean USDM 0.916 against 2026's 2.231. No year in the record resembles 2026.
- **Delta parameterisation does not close the persistence gap.** On ERC the delta-minus-level gain is
  +0.6pp with CI [−0.6, +2.1] (includes 0), and delta's absolute skill is −2.0% with CI [−10.6, +6.5]
  — indistinguishable from persistence. On USDM delta genuinely helps (+7.9pp, CI [+3.1, +14.2],
  significant, better in 11/12 folds) but absolute skill is −23.9%, CI [−35.7, −11.8], still
  decisively worse than persistence. Both parameterisations are kept as a config switch; the level
  remains the shipped one because delta's ERC gain is not distinguishable from zero.
- Clip-binding on the delta reconstruction (LODO 2021): USDM 9.7%/5.5%/4.5% at h=2/4/8, essentially
  all at the lower bound; ERC 0.00%/0.00%/0.11%. Sample weighting is implemented
  (`lodo.severe_week_weights`) but left at uniform, since it was not shown to help.
- **Statewide profiling overturns the v0.4 estimate.** LightGBM is ~3% of train time (3.58 s per fit;
  all six ~21 s of 745.67 s), so `n_jobs` tuning is not the lever: thread scaling saturates at 1.66x
  by 4 threads and regresses at 8 on this 4-performance-core box. Tree fit time scales as
  **rows^0.406**, so 50x rows costs 4.9x, not 50x. The ConvLSTM already tiles (32x32, batch 4), and
  measured tile memory is **flat** in cells across the Larimer range — the v0.4 "superlinear memory"
  claim was an assumption and is not supported. What scales is tiles per timestep, 1 → 30 statewide.
  Revised train ETA **~6.1 h** (was 10.4 h); full staged plan 7.55 h. `make statewide` is a dry-run
  planner that flags `train_pi` as the only stop-rule breach and recommends 7 tile-block chunks at
  51.7 min each. Not launched; `make statewide-run` prints the verdict and refuses to be implicit.
- **LODO and statewide both checkpoint per stage.** An early LODO run deadlocked in the second
  LightGBM fit of a single process (0% CPU, `_pthread_join`/`__ulock_wait`, the documented OpenMP
  pattern) and lost every completed fold, because results were only written at the end. Both runners
  now write a per-fold/per-stage checkpoint and skip completed work on rerun; folds run in separate
  processes so one deadlock cannot take the rest down.
- **Dev-subset move to southern Colorado deferred** to its own session (user decision). It needs a
  fresh bbox fetch and invalidates every Larimer-keyed artifact, and its payoff is fire evaluation,
  not the persistence gap.
- `docs/PREREGISTRATION.md` written **before** any further look. The 2026 holdout remains sealed at
  **2 looks**; nothing in v0.5 evaluated on 2026. Look 3 is explicitly *not* taken: its trigger
  requires delta to close the gap on validation and LODO, which it does not.

## v0.6 (multi-regime calibration, honestly)

- **Dev subset moved from Larimer to Pueblo County** (`COFIRE_SUBSET_NAME`, default `pueblo`).
  Pueblo is the Larimer-sized southern domain with the most in-domain 2026 perimeter area:
  **2 perimeters, 109,408 acres**, including **Aspen Acres at 102,003 acres — the largest Colorado
  perimeter of 2026**. Larimer had **0**, which left the fire evaluation empty from v0.2 through
  v0.5. Cell count 484 against Larimer's 494, so runtimes stay comparable. Pueblo+El Paso would add
  only 6% more perimeter area for 77% more cells and was rejected on that trade.
- **Two silent cache bugs found while moving the subset.** `processed_dir`, the raw gridMET cache
  (`_year_var_path`) and the raw elevation GeoTIFF were all **unscoped across subsets**, and the raw
  files are bbox-clipped *at download time*. The first Pueblo fetch therefore re-served Larimer
  geography under the Pueblo name: identical ERC values across all 9 years, with only USDM (clipped
  at processing time) differing. Caught by checking that the new domain's weather actually differed
  from the old one's. All three are now subset-scoped (`data/processed_pueblo/`,
  `data/raw/gridmet_pueblo/`, `3dep_pueblo.tif`) and Larimer's data is preserved unchanged at the
  legacy paths so v0.5 artifacts stay reproducible. **Any future subset must re-fetch, not reuse.**
- **The multi-regime calibration experiment was pre-registered before running**:
  `docs/PREREGISTRATION_CALIBRATION.md`, sha256
  `6a69e9a2076f79421611e0852742b57eb8fedece0225e93aa75bf370121e0dd1`. Six variants (base, a, b,
  c(k=2), c(k=3), d), covariates `usdm`/`spi_90` named up front, width cap 1.5x baseline, acceptance
  at mean coverage >= 0.85 and worst fold >= 0.80.
- **All six variants REJECTED.** Best mean LODO coverage at h=4 is **0.409** against a 0.90 target,
  **identical to the single-year baseline** — pooling bought nothing. Residual gap **49 points**. No
  variant reached even the provisional bar. Reported in full, failures included, in
  `artifacts/uncertainty/multiregime.md`.
- **Why it fails, and why no pool construction can fix it.** Residual magnitude does not track
  drought severity — it tracks whether the model *saw the year in training*. In the fold-2020 model,
  2020 (held out, mean USDM 0.901) has residual p90 = 56.74 while 2021 (in training, mean USDM
  0.916, essentially identical severity) has 22.71. Variants (b), (c) and (d) all reweight, select or
  rescale by regime, and regime does not predict the quantity they need. `corr(usdm_mean,
  resid_p90) = 0.487` across pool years, too weak to drive variant (d)'s rescaling. Adding ACI does
  not rescue it: best pool + ACI reaches 0.52–0.60 and beats the baseline on only 2 of 4 folds.
- **Three-state uncertainty status shipped** (`cofire/model/uncertainty/status.py`), computed from
  diagnostics, never hand-set: `calibrated` / `extrapolating` / `uncalibrated`. Thresholds are
  constants in the module: coverage floor 0.60, extrapolation limit 2 pool SD, widen factor clipped
  to the pre-registered [0.5, 3.0]. Surfaced on the Place Card (interval suppressed when
  uncalibrated) and in the map legend, plus `/uncertainty/status` and an `uncertainty` block on
  `/forecast`. **On the current pool the status is `uncalibrated`** (measured coverage 0.409 < 0.60),
  so the app hides intervals — which is the honest behaviour, not a bug. 2026 would also be
  uncalibrated on the regime test alone: mean USDM 2.231 against a pool maximum of 0.916, **3.7 pool
  SD** past it.
- **Claim reframed across README, docs/DESIGN.md (new), and the About screen**: COFIRE forecasts
  drought and fire-spread conditions, states how uncertain each forecast is, says when that
  uncertainty itself cannot be trusted, and turns the result into a decision. Copy lint extended to
  fail on superiority phrases anywhere in `app/` and `docs/`; `artifacts/` is deliberately not
  scanned so the persistence comparison can still be reported as the negative result it is. The
  pre-registration docs are exempt from the superiority list because they must state the hypothesis
  being tested. The lint immediately caught a surviving "beats persistence" in the About screen and
  a self-referential violation in DESIGN.md; both fixed.
- **Future experiments, logged rather than run** (the variant list was closed before results):
  conditioning the conformal score on a *predicted-difficulty* covariate rather than a regime
  covariate, since difficulty (not severity) is what drives residual inflation; and a cross-year
  jackknife+ that explicitly models the held-out-year penalty. Neither was added mid-experiment.
- **Domain comparison run on identical folds** so the subset move is not confounded with method
  change. ERC h=4 raw MAE: Larimer 30.25 vs persistence 30.22, Pueblo 30.00 vs 28.82. Median ERC
  skill Larimer +1.3%/+0.1% (level/delta), Pueblo -4.5%/-3.7%. Conformal coverage 0.409 vs 0.331.
  Skill and coverage do not differ materially between domains; both the No-go and the calibration
  failure transfer. **Pueblo USDM mean skill (-220%) is reported as a median (-94.6%)** because
  Pueblo 2024/2025 are nearly drought-free (mean USDM 0.017/0.065), so persistence MAE drops to
  0.013 and the skill ratio explodes -- the same denominator trap recorded for Larimer 2023 in the
  v0.3 sanity gates. Conclusion unchanged under either statistic.
- **Map rendering fixes (v0.6, found while demoing the UI).** Two pre-existing bugs, both in
  `app/components/MapView.tsx`, neither introduced by the v0.4-v0.6 work. (1) The map container
  rendered at height 0 under `h-[100dvh]` + `absolute inset-0`, so MapLibre initialised against a
  zero-size element and drew nothing; fixed with an explicit `h-full w-full` plus a `ResizeObserver`
  calling `map.resize()` when the element gets real bounds. (2) CARTO now serves "API KEY REQUIRED"
  watermark tiles on every raster style, including `rastertiles/dark_nolabels`, and returns **HTTP
  200** while doing it, so a status-code check does not catch it -- only looking at the rendered
  image does. Switched to `tile.openstreetmap.org`, which is genuinely keyless, preserving the
  zero-API-key requirement for the core pipeline.

## v0.7

- **Basemap policy and fallback.** CARTO now serves "API KEY REQUIRED" watermark tiles on every
  raster style **at HTTP 200**, so a status-code check cannot detect it; only the rendered image
  can. Switched to OSM, then made the choice durable: the OSM Foundation tile servers are donated
  bandwidth whose usage policy requires a descriptive identifying User-Agent and discourages
  app-embedded and bulk usage. That is acceptable for a single-laptop demo and **not** acceptable for
  a deployed build. `app/lib/basemap.ts` now abstracts the source behind `NEXT_PUBLIC_BASEMAP`
  (`osm` | `selfhost` | auto), defaulting to **OSM in dev and self-hosted PMTiles in a production
  build**. `scripts/fetch_tiles.sh` builds a keyless Colorado PMTiles extract into
  `app/public/tiles/`. Keyless holds in both modes; a missing archive degrades to a plain background
  with the forecast layer still rendering, rather than a blank map. `TILE_UA` records the identifying
  User-Agent string. Logged so "we were depending on donated bandwidth" is never a demo-day surprise.
- **Leakage diagnostic: clean on all three checks**, but the v0.6 *wording* was imprecise and is
  corrected. (1) Early stopping uses the 2023 validation split only (`valid/calibrate overlap =
  False`); LODO and multiregime pass no early-stopping set at all. (2) `fit_training_stats` filters
  `time <= train_end` (2022-12-31) before fitting SPI/SPEI gammas, ERC/BI percentiles and
  normalisation moments; empirically, 0 of 95 features shift missingness by >30pp train->cal, and
  `erc_pct` spans [20,100] on train but [0,100] on calibrate, which is the signature of a
  *train-fitted* transform applied to later data. (3) ConvLSTM windows are built per split, so no
  8-step window straddles a boundary (measured: every split's times sit inside its own bounds).
  **Correction:** the v0.6 claim "residual magnitude tracks whether the model saw the year" came
  from a LODO fold, where the held-out year genuinely is absent from that fold's training set. Under
  the *original* splits, 2024-25 is already out of sample, and the measured gap is
  **in-sample vs out-of-sample**: training years sit at residual p90 20-26 while held-out 2023, 2024
  and 2025 all sit at 59.16 / 60.59 / 62.66 -- a uniform ~2.4x. A leak would make calibration
  residuals *small*, not large. No v0.5/v0.6 number changes; only the interpretation. This also
  explains the calibration null result better: the inflation is **constant across pool years**, so no
  reweighting across them can recover it. See `artifacts/uncertainty/leak_check.md`.
- **Larimer artifacts archived** to `artifacts/archive/larimer/` before the Pueblo re-export, so the
  v0.6 two-domain comparison stays reproducible. `forecast_index.json` (187 MB, 93,600 cells) was
  replaced by a slim `forecast_index.meta.json` because it is regenerable and too large to commit;
  metrics, sanity, uncertainty and hindcast outputs are kept in full (1.1 MB total).
- **Pueblo re-export: look counter asserted unchanged at 2.** `COFIRE_SUBSET_NAME=pueblo make train
  calibrate export` is a scoring-and-export run and takes no 2026 look; asserted before and after
  (`before=2 after=2`). In-domain 2026 perimeters went **0 -> 2 (109,408 acres**, including Aspen
  Acres at 102,003, the largest Colorado perimeter of 2026), so the Hindcast fire table is no longer
  empty. The `in_domain` flags were recomputed as a pure geometric bbox test on the already-scored
  `fires.json`, which uses no 2026 predictions and so costs no look.
- **Export now rejects out-of-domain prediction frames.** The first Pueblo export produced a
  **two-domain index** (18,240 Larimer cells mixed with 67,824 Pueblo cells, latest issue still
  Larimer) because `export.py` prefers `{arm}_hindcast_intervals.parquet`, which is written only by
  `hindcast.py` and therefore could not be regenerated without spending a look. Export now drops any
  frame with <50% of rows inside the active bbox and logs a warning naming the stage to re-run.
  Consequence, stated plainly: the Pueblo export covers **2023-01-03 to 2025-12-30** (valid +
  calibrate) and contains **no 2026 issues**, because producing them requires a hindcast look. That
  is the correct trade.
- **Map camera is derived from the exported grid**, not hardcoded. `/meta` returns `center`/`zoom`
  computed from the cell extent, so moving the dev subset no longer leaves the camera pointed at the
  previous domain. Caught only by looking at the rendered map: the cells were Pueblo while the view
  was still Fort Collins.
- **Landing figures are generated, never hand-written.** `cofire/model/site_facts.py` writes
  `app/lib/facts.json` from artifacts, and the landing page reads only from it, so a stale or
  flattering number cannot survive a re-run. `make facts` regenerates.
- **Copy lint now also bans em-dash and en-dash in `app/`** (UI copy only; docs and artifacts are
  prose for readers). It immediately caught 8 files carrying them, including ones written earlier in
  this project.
- **Hero imagery is real, local and licensed.** Picsum seeds return unrelated photos (a bridge, a
  city skyline) regardless of the seed text, which is only visible by looking at the render. Replaced
  with a public Wikimedia Commons photo of the **High Park Fire above Poudre Canyon** (CC BY 2.0),
  downloaded into `app/public/img/` so `make demo` works offline with no external image fetch.

## v0.8

- **Option A taken for the stale issue date: scoring-free 2026 forecasts. This is not a look, and
  here is why.** A look means reading realized holdout outcomes and learning from them. In this
  codebase that is exactly two things: `attach_intervals(..., update_aci=True)`, which calls
  `cal.observe(y, lo, hi)`, tests `lo <= y <= hi` against the **realized** value and feeds the
  hit/miss into alpha; and the scoring calls (`write_comparison`, `_score_fires`,
  `_append_hindcast_metrics`, the coverage plot) which compute MAE, coverage and skill against
  realized values. `cofire/model/forecast_issues.py` does none of it. It reads the forecasts
  `train.py` already produced by a forward pass on issue-time features, drops the realized-outcome
  columns from the frame entirely, and attaches intervals with `update_aci=False` so width comes
  solely from the **calibrate-split** residual pool frozen in `make calibrate`. Verified empirically
  before implementing: with ACI off, alpha is constant at 0.10 across every 2026 row and the
  calibrator's state is identical before and after. Nothing is compared, so nothing is learned.
  Guardrails in code, not comments: realized columns are dropped and re-asserted absent; the
  calibrator's alpha map is compared before and after and must match; `assert_scoring_not_invoked()`
  fails if `cofire.model.hindcast` is in `sys.modules`; and the look counter is read before and
  after and asserted equal. Measured: **looks before 2, after 2**, 16,416 rows, 38 issues, 432 cells.
  The forecast index now runs to **2026-09-22**. Option B was not needed and no look was spent.
- **Export prefers the scoring-free forecasts** (`{arm}_forecast_issues.parquet`) over the scored
  `{arm}_hindcast_intervals.parquet`, falling back only if that stage has not run. This also
  resolves the v0.7 stale-domain drop: nothing is discarded now, because the preferred file is
  regenerated per subset without a look.
- **Calibration wording corrected everywhere** to the v0.7 leak-check finding, which is the sharper
  and more defensible claim: held-out years carry a **uniform ~2.4x residual inflation** (p90 59.16 /
  60.59 / 62.66 on 2023 / 2024 / 2025 against 20-26 on training years), a leak was ruled out on three
  checks, and because the inflation is **constant across pool years, no reweighting of those years
  can recover it**. That is why all six pre-registered pool variants returned +0.000 improvement.
- **Polish pass on `/beat`, `/observe`, `/ember`** against a shared control layer
  (`app/components/ui/Controls.tsx`): one radius scale, one accent per target (fire for
  fire-spread, drought for USDM), mono tabular numerals everywhere, and composed loading /
  empty / error / offline states. No ad hoc values in route files. Interactions verified against
  live server values in a real browser, not asserted: `/beat` reveals the model only after submit
  (0.9 drought, 39 fire-spread index); `/observe` shows the server-computed delta (+0.05 / +1.2)
  with its documented source; `/ember` score ring animates 0% -> 10% on a real state change and is
  otherwise still.
- **Place Card crash found by clicking the real map.** `WhyBars` called `.toFixed()` on
  `why[].value`, which is `null` whenever the SHAP cache misses and the API falls back to a
  feature-z explanation. Every such cell crashed the whole Place Card with
  `Cannot read properties of null`. This was invisible to HTTP checks (the endpoint returns 200
  with a valid payload) and to typechecking (the type said `number`). Fixed: the type now admits
  `null` and the bar renders without a magnitude. This is the fourth render-only failure this
  project has produced, which is why visual verification is a standing rule rather than a
  preference.
- **`make web` clears `.next` before starting the dev server.** `next build` and `next dev` share
  the `.next` directory and write incompatible layouts into it. Running a production build while the
  dev server was up left the dev server serving a manifest whose chunks no longer existed, so every
  route returned **200 for the HTML but 404 for `layout.css`, `main-app.js` and
  `app-pages-internals.js`** - the site loaded with no styles and no client JavaScript, and the map
  never initialised. This bit twice and is invisible to `tsc`, to the copy lint and to an HTTP status
  check on the route itself, because the document is fine and only its assets are missing. Clearing
  `.next` on dev start makes the failure impossible rather than merely unlikely; `make web-build`
  does the same before a production build.
