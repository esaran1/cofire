# Sanity gates

Git `a3f212d083122dcf5b6d62efe2a574d7beb4c67b`. Hindcast 2026 was not scored.

Overall: **PASS**.

## label_sanity: PASS

Published Colorado drought shape (statewide, not Larimer-specific): 2012, 2018, 2021 dry; 2019, 2023 wet. Larimer fetch starts 2018 (2012 absent). 2018 mean USDM 0.147 vs 2019 0.024 (dry>wet). 2021 mean USDM 0.916 vs 2023 0.006 (dry>wet). 2012 not in this cube (outside Larimer data window). Not a fail.

| year | n | mean USDM | % D1+ | % D2+ |
| --- | --- | --- | --- | --- |
| 2018 | 24960 | 0.147 | 0.129 | 0.018 |
| 2019 | 25440 | 0.024 | 0.024 | 0.000 |
| 2020 | 24960 | 0.901 | 0.408 | 0.341 |
| 2021 | 24960 | 0.916 | 0.530 | 0.278 |
| 2022 | 24960 | 0.363 | 0.307 | 0.055 |
| 2023 | 24960 | 0.006 | 0.006 | 0.000 |
| 2024 | 25440 | 0.679 | 0.415 | 0.215 |
| 2025 | 24960 | 0.648 | 0.442 | 0.177 |
| 2026 | 17760 | 2.231 | 1.000 | 0.805 |

## grid_alignment: PASS

mean agreement 1.0000 over 10 polygons (pass > 0.98). 2021-12-28 DM=1 n=316 agr=1.000; 2026-02-24 DM=2 n=403 agr=1.000; 2025-12-30 DM=1 n=299 agr=1.000; 2022-08-02 DM=0 n=68 agr=1.000; 2026-09-08 DM=2 n=266 agr=1.000; 2026-05-05 DM=3 n=265 agr=1.000; 2018-10-23 DM=0 n=264 agr=1.000; 2025-10-14 DM=0 n=120 agr=1.000; 2022-05-17 DM=0 n=340 agr=1.000; 2022-08-23 DM=0 n=93 agr=1.000

## future_data: PASS

checked 160 lag/roll values, mismatches=0. 

## baseline_floor: PASS

drought h=2: pers MAE=0.020 clim=0.456 random=0.026 ERC-percentile h=2: pers MAE=31.909 random=33.380 drought h=4: pers MAE=0.036 clim=0.450 random=0.041 ERC-percentile h=4: pers MAE=33.233 random=33.649 drought h=8: pers MAE=0.057 clim=0.444 random=0.059 ERC-percentile h=8: pers MAE=39.327 random=32.964 ERC persistence at 8 weeks is not required to beat a constant mean; weather memory is days to a couple of weeks. Drought climatology vs random on this valid year is informational (valid D0 rate=0.994); 2023 is wetter than train, so the D0 mode wins MAE. Not a hard fail. raw ERC cell-woy climatology MAE=10.085 vs constant train-mean MAE=11.719. PASS cell-woy climatology beats a constant mean on raw ERC. Models beating persistence at 2 weeks is not required; failing to beat it at 8 weeks is a later model-quality issue, not this gate.

## autocorrelation: PASS

Weekly domain-mean AR(1): USDM rho=0.977 n=261 n_eff=3.0; ERC rho=0.492 n=261 n_eff=88.9. Raw rows=125280 cells=480. Headline CIs must use week-block bootstrap; do not treat cell-weeks as independent.

## shuffle_test: PASS

shuffled LightGBM ERC h=4 R²=-0.213 MAE=33.367 vs persistence MAE=33.233. Pass if R² < 0.15 and MAE is not substantially better than persistence.
