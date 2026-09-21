# STATUS: No-go (point forecast) — uncertainty layer now honest and shipping

Git `a3f212d083122dcf5b6d62efe2a574d7beb4c67b`. Dev subset: **Pueblo County** (`COFIRE_SUBSET_NAME=pueblo`),
moved from Larimer this session. Displayed resolution 4000 m. **2026 hindcast remains sealed at 2
looks** on config `0957e415fa7f3fad` — nothing in v0.6 evaluated on 2026.

## Phase 4 pre-registration (v1.0, recorded before the first PID run)

`docs/PREREGISTRATION_V1.md`, sha256 `83c712fbce88bfa3b9acc0d17122167c39cdbfc991a32fbbc7d96097c9e8568f`.

Six arms fixed in advance: split conformal, ACI, PID-P, PID-PI, PID-full, CQR.
Target coverage 0.90, both domains reported separately, horizons 2/4/8, PID
gains taken from the reference construction and not searched. The adoption rule
requires coverage deviation to improve by at least 0.01 *and* interval width to
grow no more than 5%, on both domains, or the result is recorded as no
improvement. The recorded prior is that PID does not help much here.


## Pool outcome: all six variants rejected, on both domains

The multi-regime calibration experiment was pre-registered and hashed before it ran
(`docs/PREREGISTRATION_CALIBRATION.md`, sha256 `6a69e9a2076f79421611e0852742b57eb8fedece0225e93aa75bf370121e0dd1`),
with the variant list, covariates, width cap and acceptance criteria fixed in advance.

| domain | best variant | best coverage | baseline | improvement | residual gap to 0.90 |
| --- | --- | --- | --- | --- | --- |
| Larimer | base / c(k=2) / c(k=3) (tied) | 0.409 | 0.409 | **+0.000** | **49 points** |
| Pueblo | base (single-year) | 0.331 | 0.331 | **+0.000** | **57 points** |

Not one variant met even the provisional bar. On Pueblo every pooling variant is *worse* than the
single-year baseline it was meant to improve. All six are reported with their numbers in
`artifacts/uncertainty/multiregime.md`; none was tuned toward 0.90 and none was added after results
were seen.

**Why.** Every held-out year carries the same **~2.4x residual inflation**, and a leakage audit
ruled out contamination on all three checks (`artifacts/uncertainty/leak_check.md`). Measured under
the original splits at ERC h=4, absolute residual p90:

| year | 2018 | 2019 | 2020 | 2021 | 2022 | **2023** | **2024** | **2025** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| p90 | 20.59 | 24.94 | 25.06 | 23.77 | 26.38 | **59.16** | **60.59** | **62.66** |

Training years sit at 20 to 26. Held-out 2023, 2024 and 2025 sit at 59 to 63. This is an **in-sample
versus out-of-sample** gap, not a seen-year versus unseen-year one, and a leak would make the
held-out residuals *small*, not large.

That is precisely why pool construction cannot help. **The inflation is constant across pool years,
so no reweighting of those years can recover it.** Variants (b), (c) and (d) all reweight, select or
rescale by regime, and regime does not predict the quantity they need
(`corr(usdm_mean, residual_p90) = 0.487`). Adding ACI does not rescue it either: the best pool
reaches 0.52 to 0.60 and beats the baseline on only 2 of 4 folds.

**What the second domain proved.** On Larimer, 2026 sits 3.7 pool SD past the record maximum, which
invites the explanation "no analog in the record". On Pueblo that explanation **fails**: 2018 (mean
USDM 2.058) is drier than 2026 (1.109), so 2026 falls *inside* the pool range and passes the regime
gate outright — and the intervals are still not calibrated (0.331). Having an analog year is **not
sufficient**. Only running both domains could distinguish "no analog" from "unseen-year penalty",
and it is the latter.

## Three-state uncertainty status: shipping

Computed from diagnostics in `cofire/model/uncertainty/status.py`, never hand-set, with **two
independent gates** that must both pass:

| state | condition | behaviour |
| --- | --- | --- |
| **calibrated** | regime inside pool range **and** pool coverage >= 0.60 | interval shown |
| **extrapolating** | regime exceeds pool max by <= 2 pool SD | interval widened (clipped to the pre-registered [0.5, 3.0]) + visible caveat |
| **uncalibrated** | pool coverage < 0.60 **or** regime exceeds pool by > 2 pool SD | **interval suppressed**; point forecast + Why drivers still shown |

Shipped in `/uncertainty/status`, an `uncertainty` block on `/forecast`, the Place Card (interval
replaced by an explanation) and the map legend (status chip). Verified in a real browser: the legend
renders "UNCALIBRATED · intervals hidden" and `/forecast` returns `show_interval: false`. 18 tests
cover the classifier and the API contract, including that the status never becomes less cautious as
drought worsens.

**Current state on both domains: `uncalibrated`** — for different reasons. Larimer fails both gates;
Pueblo passes the regime gate and fails the coverage floor (0.331 < 0.60). The app therefore hides
intervals today. That is the honest behaviour and the intended outcome of the feature, not a defect.

## Subset move: fire evaluation unblocked

Pueblo County contains **2 in-domain 2026 perimeters totalling 109,408 acres**, including **Aspen
Acres at 102,003 acres — the largest Colorado perimeter of 2026**. Larimer contained **0**, which
left the fire evaluation empty from v0.2 through v0.5. 484 cells against Larimer's 494, so runtimes
stay comparable.

Moving the subset exposed **two silent cache-scoping bugs**: the raw gridMET extracts and the raw
elevation GeoTIFF are bbox-clipped *at download time* but were cached at subset-agnostic paths, so
the first Pueblo fetch re-served **Larimer geography under the Pueblo name** (identical ERC across
all 9 years). Caught by checking that the new domain's weather actually differed rather than
trusting the fetch log. All paths are now subset-scoped; Larimer's data is preserved byte-identical
at the legacy paths (verified: 2021 mean USDM still 0.916).

## Domain comparison: skill and coverage do not differ materially

Both domains were re-run on identical folds and methods so the move is not confounded with a method
change. ERC-percentile MAE at h=4 (raw, no ratio): Larimer 30.25 vs persistence 30.22; Pueblo 30.00
vs 28.82. Median LODO skill on ERC: Larimer +1.3% (level) / +0.1% (delta), Pueblo −4.5% / −3.7%.
Static conformal coverage: Larimer 0.409, Pueblo 0.331. **The No-go and the calibration failure both
transfer.**

One reporting caveat: Pueblo's *mean* USDM skill reads −220%, which overstates it. Pueblo 2024/2025
are nearly drought-free (mean USDM 0.017/0.065), so persistence MAE falls to 0.013 and the ratio
explodes (−562% on one fold). The median, −94.6%, is the honest summary — the same denominator trap
recorded for Larimer 2023 in the v0.3 sanity gates. Drought loses decisively on both domains either
way.

## Claim reframed

README, the new `docs/DESIGN.md`, and the About screen now state: COFIRE forecasts drought and
fire-spread conditions, states how uncertain each forecast is, says when that uncertainty itself
cannot be trusted, and turns the result into a decision. The copy lint fails the build on superiority
phrases anywhere in `app/` and `docs/`; `artifacts/` is deliberately not scanned so the persistence
comparison can still be reported as the negative result it is. The lint immediately caught a
surviving superiority claim in the About screen.

The persistence gap is settled and no longer being pursued: ERC delta is indistinguishable from level
and from persistence; drought loses decisively under both parameterisations.

## Still deferred

- **Statewide**: not run. Staged planner (`make statewide`) reports 7.55 h with `train_pi` the only
  stop-rule breach, split into 7 tile-block chunks.
- **Look 3**: not taken. `docs/PREREGISTRATION.md` binds it and its trigger — delta closing the
  persistence gap — remains unmet.
- **Demo freeze**: still blocked behind statewide.
