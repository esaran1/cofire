# Leave-one-drought-year-out (LODO)

In-sample shift test. For each year, the model is retrained with that year removed and evaluated on it. No fold ever trains or evaluates on 2026. Skill is versus persistence on the **level**, so the two parameterisations are directly comparable.

Years: 2020, 2021, 2024, 2025. 2002 and 2012 are not in the feature store (fetch warmup starts 2018), so these are the driest available years. They are weaker analogs for 2026 than the spec assumed: the driest here is 2021 at mean USDM 0.916, against 2026's 2.231.

## erc_pct

| year | h | param | model MAE | persistence MAE | skill |
| --- | --- | --- | --- | --- | --- |
| 2020 | 2 | delta | 28.150 | 22.941 | -22.7% |
| 2020 | 2 | level | 29.397 | 22.941 | -28.1% |
| 2020 | 4 | delta | 29.553 | 26.292 | -12.4% |
| 2020 | 4 | level | 31.028 | 26.292 | -18.0% |
| 2020 | 8 | delta | 31.641 | 25.367 | -24.7% |
| 2020 | 8 | level | 32.032 | 25.367 | -26.3% |
| 2021 | 2 | delta | 24.334 | 25.790 | +5.6% |
| 2021 | 2 | level | 24.360 | 25.790 | +5.5% |
| 2021 | 4 | delta | 28.624 | 26.299 | -8.8% |
| 2021 | 4 | level | 28.134 | 26.299 | -7.0% |
| 2021 | 8 | delta | 29.434 | 27.896 | -5.5% |
| 2021 | 8 | level | 28.722 | 27.896 | -3.0% |
| 2024 | 2 | delta | 30.120 | 35.262 | +14.6% |
| 2024 | 2 | level | 29.727 | 35.262 | +15.7% |
| 2024 | 4 | delta | 29.780 | 33.724 | +11.7% |
| 2024 | 4 | level | 29.824 | 33.724 | +11.6% |
| 2024 | 8 | delta | 30.292 | 35.705 | +15.2% |
| 2024 | 8 | level | 30.151 | 35.705 | +15.6% |
| 2025 | 2 | delta | 31.572 | 25.885 | -22.0% |
| 2025 | 2 | level | 31.531 | 25.885 | -21.8% |
| 2025 | 4 | delta | 32.165 | 34.555 | +6.9% |
| 2025 | 4 | level | 32.035 | 34.555 | +7.3% |
| 2025 | 8 | delta | 34.262 | 41.787 | +18.0% |
| 2025 | 8 | level | 34.757 | 41.787 | +16.8% |

Mean skill across folds and horizons:

- **delta**: -2.0%
- **level**: -2.6%

## usdm

| year | h | param | model MAE | persistence MAE | skill |
| --- | --- | --- | --- | --- | --- |
| 2020 | 2 | delta | 0.207 | 0.148 | -39.7% |
| 2020 | 2 | level | 0.262 | 0.148 | -76.4% |
| 2020 | 4 | delta | 0.344 | 0.255 | -35.0% |
| 2020 | 4 | level | 0.387 | 0.255 | -52.0% |
| 2020 | 8 | delta | 0.619 | 0.414 | -49.4% |
| 2020 | 8 | level | 0.662 | 0.414 | -59.8% |
| 2021 | 2 | delta | 0.255 | 0.177 | -43.8% |
| 2021 | 2 | level | 0.271 | 0.177 | -53.1% |
| 2021 | 4 | delta | 0.381 | 0.358 | -6.7% |
| 2021 | 4 | level | 0.383 | 0.358 | -7.2% |
| 2021 | 8 | delta | 0.539 | 0.673 | +20.0% |
| 2021 | 8 | level | 0.537 | 0.673 | +20.2% |
| 2024 | 2 | delta | 0.276 | 0.230 | -19.9% |
| 2024 | 2 | level | 0.291 | 0.230 | -26.6% |
| 2024 | 4 | delta | 0.448 | 0.399 | -12.2% |
| 2024 | 4 | level | 0.454 | 0.399 | -13.9% |
| 2024 | 8 | delta | 0.607 | 0.581 | -4.3% |
| 2024 | 8 | level | 0.610 | 0.581 | -5.0% |
| 2025 | 2 | delta | 0.312 | 0.202 | -54.1% |
| 2025 | 2 | level | 0.327 | 0.202 | -61.7% |
| 2025 | 4 | delta | 0.498 | 0.375 | -32.6% |
| 2025 | 4 | level | 0.510 | 0.375 | -36.0% |
| 2025 | 8 | delta | 0.724 | 0.663 | -9.2% |
| 2025 | 8 | level | 0.730 | 0.663 | -10.1% |

Mean skill across folds and horizons:

- **delta**: -23.9%
- **level**: -31.8%

## Conformal coverage on held-out years (target 0.90)

| year | h=2 | h=4 | h=8 |
| --- | --- | --- | --- |
| 2020 | 0.586 | 0.526 | 0.519 |
| 2021 | 0.669 | 0.593 | 0.594 |
| 2024 | 0.607 | 0.586 | 0.575 |
| 2025 | 0.608 | 0.563 | 0.513 |


## Domain comparison: Larimer vs Pueblo (v0.6)

The dev subset moved to Pueblo County. Both domains were re-run on identical folds and methods, so
the domain change is not confounded with any method change.

ERC-percentile MAE at h=4, level parameterisation — raw MAE, no skill ratio:

| domain | model | persistence |
| --- | --- | --- |
| Larimer | 30.25 | 30.22 |
| Pueblo | 30.00 | 28.82 |

Median skill across all folds and horizons (median, because two Pueblo folds have near-zero
persistence MAE and blow up the mean ratio — see below):

| target | domain | level | delta |
| --- | --- | --- | --- |
| ERC percentile | Larimer | +1.3% | +0.1% |
| ERC percentile | Pueblo | −4.5% | −3.7% |
| USDM | Larimer | −31.3% | −26.2% |
| USDM | Pueblo | −94.6% | −74.1% |

**Skill does not differ materially between domains on the ERC target.** Both sit within a few points
of zero, and the raw MAEs are within 1.2 points of persistence on both. The No-go transfers.

**A reporting caveat on the Pueblo USDM figures.** The *mean* skill on Pueblo USDM is −220%, which
overstates the failure. Pueblo 2024 and 2025 are almost drought-free (mean USDM 0.017 and 0.065), so
persistence MAE is 0.013–0.131 and the skill ratio explodes: the 2024 folds alone score −562%,
−529% and −861%. This is the same denominator trap documented for Larimer 2023 (99.4% D0) in the
v0.3 sanity gates. The median (−94.6%) is the honest summary, and the conclusion is unchanged either
way: drought loses decisively to persistence on both domains.

Coverage also does not differ materially: static split-conformal LODO coverage is 0.409 on Larimer
and 0.331 on Pueblo, both far below the 0.90 target, with all six pool variants rejected on both.
See `artifacts/uncertainty/multiregime.md`.
