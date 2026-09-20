# Multi-regime calibration pools

Pre-registered in `docs/PREREGISTRATION_CALIBRATION.md` (sha256
`6a69e9a2076f79421611e0852742b57eb8fedece0225e93aa75bf370121e0dd1`), frozen **before** any variant
ran. The variant list is closed. **Every variant is reported, including the ones that fail.**
Nothing here evaluates on 2026.

Coverage is **static split conformal** (no ACI), which isolates the pool's contribution from the
online update. Target 0.90. Both dev subsets are reported separately so the domain change is never
confounded with the method change.

## Domain: larimer (h = 4 weeks)

| variant | mean coverage | worst fold | mean width | verdict |
| --- | --- | --- | --- | --- |
| base | 0.409 | 0.348 | 48.1 | **REJECT** |
| a | 0.403 | 0.361 | 47.2 | **REJECT** |
| b | 0.403 | 0.363 | 47.3 | **REJECT** |
| c(k=2) | 0.409 | 0.380 | 48.1 | **REJECT** |
| c(k=3) | 0.409 | 0.369 | 48.1 | **REJECT** |
| d | 0.404 | 0.365 | 47.3 | **REJECT** |

Per-fold coverage:

| variant | 2020 | 2021 | 2024 | 2025 |
| --- | --- | --- | --- | --- |
| base | 0.348 | 0.447 | 0.420 | 0.420 |
| a | 0.361 | 0.452 | 0.421 | 0.379 |
| b | 0.363 | 0.457 | 0.415 | 0.378 |
| c(k=2) | 0.380 | 0.443 | 0.415 | 0.397 |
| c(k=3) | 0.369 | 0.464 | 0.416 | 0.389 |
| d | 0.365 | 0.454 | 0.417 | 0.378 |

Coverage against the 0.90 target (each block = 0.02):

```
base     0.409 |####################
a        0.403 |####################
b        0.403 |####################
c(k=2)   0.409 |####################
c(k=3)   0.409 |####################
d        0.404 |####################
TARGET   0.900 |#############################################
```

Mean interval width (cap = 1.5x base = 72.1; ERC percentile is bounded 0-100):

```
base      48.1 |========================
a         47.2 |========================
b         47.3 |========================
c(k=2)    48.1 |========================
c(k=3)    48.1 |========================
d         47.3 |========================
```
best = 0.409, base = 0.409, improvement = +0.001, residual gap to 0.90 = **0.491**

## Domain: pueblo (h = 4 weeks)

| variant | mean coverage | worst fold | mean width | verdict |
| --- | --- | --- | --- | --- |
| base | 0.331 | 0.249 | 39.5 | **REJECT** |
| a | 0.303 | 0.228 | 36.3 | **REJECT** |
| b | 0.287 | 0.211 | 34.6 | **REJECT** |
| c(k=2) | 0.301 | 0.215 | 36.2 | **REJECT** |
| c(k=3) | 0.303 | 0.218 | 36.3 | **REJECT** |
| d | 0.310 | 0.189 | 37.3 | **REJECT** |

Per-fold coverage:

| variant | 2020 | 2021 | 2024 | 2025 |
| --- | --- | --- | --- | --- |
| base | 0.249 | 0.391 | 0.335 | 0.350 |
| a | 0.228 | 0.352 | 0.302 | 0.329 |
| b | 0.211 | 0.328 | 0.288 | 0.319 |
| c(k=2) | 0.215 | 0.345 | 0.317 | 0.328 |
| c(k=3) | 0.218 | 0.354 | 0.311 | 0.328 |
| d | 0.189 | 0.350 | 0.341 | 0.361 |

Coverage against the 0.90 target (each block = 0.02):

```
base     0.331 |#################
a        0.303 |###############
b        0.287 |##############
c(k=2)   0.301 |###############
c(k=3)   0.303 |###############
d        0.310 |################
TARGET   0.900 |#############################################
```

Mean interval width (cap = 1.5x base = 59.2; ERC percentile is bounded 0-100):

```
base      39.5 |====================
a         36.3 |==================
b         34.6 |=================
c(k=2)    36.2 |==================
c(k=3)    36.3 |==================
d         37.3 |===================
```
best = 0.331, base = 0.331, improvement = +0.000, residual gap to 0.90 = **0.569**

## Why every variant fails on both domains

> **Corrected in v0.7** (see `artifacts/uncertainty/leak_check.md`): the mechanism below is stated
> for the LODO folds, where the held-out year genuinely is absent from that fold's training set.
> Under the *original* splits the gap is **in-sample versus out-of-sample**, not seen-year versus
> unseen-year: held-out 2023, 2024 and 2025 all carry the same ~2.4x residual p90 inflation
> (59.16 / 60.59 / 62.66 against 20-26 on training years). A leakage audit found no leak. The
> numbers below are unaffected; only the wording is corrected. It also explains the null result more
> cleanly -- the inflation is *constant across pool years*, so no reweighting across them can
> recover it.

The pre-registered expectation was that pooling would improve coverage materially without reaching
0.90. The measured result is stronger and more negative: **pooling does not improve coverage at all
on either domain**, and on Pueblo every pooling variant is *worse* than the single-year baseline.

| domain | best variant | best mean coverage | baseline | improvement | residual gap |
| --- | --- | --- | --- | --- | --- |
| larimer | base / c(k=2) / c(k=3) (tied) | 0.409 | 0.409 | **+0.000** | 49 points |
| pueblo | base | 0.331 | 0.331 | **+0.000** | 57 points |

The diagnostic that explains it, from the Larimer fold-2020 model at h=4:

| year | mean USDM | residual p90 |
| --- | --- | --- |
| 2018 | 0.147 | 21.15 |
| 2019 | 0.024 | 23.32 |
| **2020 (held out)** | **0.901** | **56.74** |
| 2021 | 0.916 | 22.71 |
| 2022 | 0.363 | 22.74 |
| 2023 | 0.006 | 24.39 |
| 2024 | 0.679 | 26.69 |
| 2025 | 0.648 | 22.49 |

2020 and 2021 have **essentially identical drought severity** (0.901 vs 0.916), yet 2020's residuals
are 2.5x larger. The difference is not the weather: 2020 was *held out of training* and 2021 was
not. **Residual magnitude tracks whether the model saw the year, not how dry the year was.**

That is fatal to the whole family of pool-construction fixes. Variants (b), (c) and (d) all
reweight, select or rescale years **by regime**, and regime does not predict the quantity they need.
`corr(usdm_mean, residual_p90) = 0.487` across pool years — too weak to drive variant (d)'s
rescaling, so its ratio stays near 1.

Pueblo makes the failure mode plainer. Its record spans a much wider severity range (mean USDM 0.017
to 2.058, against Larimer's 0.006 to 0.916), so pooling mixes genuinely wet years into the pool.
Those years have *smaller* residuals, which pulls the quantile **down** and narrows the interval —
the opposite of what is needed. Variant (b), which weights by severity, is the worst performer on
Pueblo (0.287) precisely because the weighting is not strong enough to overcome the added wet mass.
Variant (d) posts the single worst fold of the whole experiment (0.189 on Pueblo 2020), because its
regime fit points the wrong way on a severe held-out year.

Adding ACI does not rescue it. With the online update running — the configuration the product would
ship — the best Larimer pool reaches 0.52–0.60 across folds against 0.90, and beats the single-year
baseline on only 2 of 4 folds:

| fold | base + ACI | c(k=3) + ACI |
| --- | --- | --- |
| 2020 | 0.524 | 0.558 |
| 2021 | 0.600 | 0.602 |
| 2024 | 0.589 | 0.560 |
| 2025 | 0.562 | 0.518 |

## What the record can and cannot support

This record cannot support a calibrated 90% interval for a year the model has not trained on. The
binding constraint is not pool construction, learning rate, or the conformal score: leave-one-year-out
residuals for an unseen year run ~2.5x those of years in training, and **nothing computable from the
remaining years predicts that inflation**. Every variant on the pre-registered list was tested on
both domains and every one was rejected against a criterion fixed in advance, so the honest
conclusion is that the multi-regime pool is not the missing piece.

The domain move sharpens one point that Larimer alone would have got wrong. On Larimer, 2026 sits
3.7 pool standard deviations past the record maximum, which invites the explanation "there is no
analog in the record". On **Pueblo that explanation fails**: 2018 (mean USDM 2.058) is *drier* than
2026 (1.109), so 2026 falls **inside** the pool's regime range and passes the regime gate outright.
The intervals are still not calibrated — measured coverage 0.331. Having an analog year in the pool
is **not sufficient**. The problem is the unseen-year residual penalty, not the absence of a
comparable regime, and only the second domain could distinguish the two.

What the record *does* support is saying so. The product ships the measured coverage as a
three-state status with two independent gates — a regime gate and a coverage-floor gate — and
suppresses the interval when either fails, rather than showing a number that looks like knowledge.
On both domains the status is currently `uncalibrated`, for different reasons: Larimer fails the
regime gate *and* the coverage gate, Pueblo passes the regime gate and fails the coverage gate. No
variant was tuned toward 0.90, and none was added after results were seen.
