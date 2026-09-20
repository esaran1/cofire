# COFIRE metrics

These models forecast **drought severity** and **conditions that allow fires to spread** (ERC percentile / fire-spread condition index). They do not forecast ignitions.

Shipping arm: **ensemble** (best validation ERC-percentile MAE).
Git: `a3f212d083122dcf5b6d62efe2a574d7beb4c67b`  MANIFEST: `f7fe6fe3db552f0f6bc10df7ce16a5197c86dc2aed7b599797e6f96588ace6b9`
Displayed resolution: 4000 m (gridMET native 4 km unless HLS is on and loaded).

Hyperparameters were frozen on the validation split. Hindcast 2026 is scored only in hindcast.py.

## Effective sample size

Training-window weekly domain-mean AR(1): USDM rho=0.9771398415734813 n_weeks=261 n_eff=3.0177437244767726; ERC rho=0.4920411736602018 n_weeks=261 n_eff=88.85629700784689. Headline intervals use week-block bootstrap, not cell-weeks as independent samples.

## Validation sentences

### lightgbm

The 2-week drought MAE for lightgbm is 0.10 categories versus 0.02 for persistence, a -386% skill (worse than persistence), CI [-2139%, -179%].
Drought h=2 exact-category accuracy 0.9764423076923077; Brier P(cat>=2)=0.0031916348616815213 ECE=0.0007378382461119752; Brier P(cat>=3)=6.36127938979522e-11 ECE=5.1610033681860565e-06.
The 2-week ERC-percentile MAE for lightgbm is 30.37 versus 31.91 for persistence, a 5% skill improvement, CI [-11%, 19%].
Fire-condition (ERC percentile) h=2 R²=0.014504592674142947.
The 4-week drought MAE for lightgbm is 0.14 categories versus 0.04 for persistence, a -301% skill (worse than persistence), CI [-1043%, -153%].
Drought h=4 exact-category accuracy 0.9545272435897436; Brier P(cat>=2)=0.00665482441828824 ECE=0.0014272241939546296; Brier P(cat>=3)=1.8924676765583611e-10 ECE=6.382848827148242e-06.
The 4-week ERC-percentile MAE for lightgbm is 32.00 versus 33.23 for persistence, a 4% skill improvement, CI [-19%, 20%].
Fire-condition (ERC percentile) h=4 R²=-0.09257131550956754.
The 8-week drought MAE for lightgbm is 0.16 categories versus 0.06 for persistence, a -173% skill (worse than persistence), CI [-411%, -92%].
Drought h=8 exact-category accuracy 0.9285657051282051; Brier P(cat>=2)=0.00906479265479904 ECE=0.004417516515047758; Brier P(cat>=3)=5.884584690945611e-09 ECE=2.845183848410584e-05.
The 8-week ERC-percentile MAE for lightgbm is 31.37 versus 39.33 for persistence, a 20% skill improvement, CI [4%, 32%].
Fire-condition (ERC percentile) h=8 R²=-0.15511039088086487.

### pi_convlstm_none

The 2-week drought MAE for pi_convlstm_none is 0.34 categories versus 0.02 for persistence, a -2511% skill (worse than persistence), CI [-10732%, -1149%].
Drought h=2 exact-category accuracy 0.9828125; Brier P(cat>=2)=0.015368389303109036 ECE=0.12396930790344027; Brier P(cat>=3)=0.0019350371377202262 ECE=0.0439890570176596.
The 2-week ERC-percentile MAE for pi_convlstm_none is 31.28 versus 31.91 for persistence, a 2% skill improvement, CI [-18%, 19%].
Fire-condition (ERC percentile) h=2 R²=-0.1191217146341137.
The 4-week drought MAE for pi_convlstm_none is 0.35 categories versus 0.04 for persistence, a -863% skill (worse than persistence), CI [-3312%, -378%].
Drought h=4 exact-category accuracy 0.9661931818181818; Brier P(cat>=2)=0.020213304404208553 ECE=0.11990231947098491; Brier P(cat>=3)=0.002049989907731509 ECE=0.045276814233688074.
The 4-week ERC-percentile MAE for pi_convlstm_none is 31.10 versus 33.23 for persistence, a 1% skill improvement, CI [-28%, 21%].
Fire-condition (ERC percentile) h=4 R²=-0.0967012788008852.
The 8-week drought MAE for pi_convlstm_none is 0.36 categories versus 0.06 for persistence, a -463% skill (worse than persistence), CI [-1137%, -240%].
Drought h=8 exact-category accuracy 0.9448863636363637; Brier P(cat>=2)=0.023807608345535112 ECE=0.11658553968494137; Brier P(cat>=3)=0.0022844643741600904 ECE=0.047796070692482207.
The 8-week ERC-percentile MAE for pi_convlstm_none is 30.13 versus 39.33 for persistence, a 22% skill improvement, CI [7%, 37%].
Fire-condition (ERC percentile) h=8 R²=-0.07401250256872527.

### pi_convlstm_hydro

The 2-week drought MAE for pi_convlstm_hydro is 0.34 categories versus 0.02 for persistence, a -2528% skill (worse than persistence), CI [-10806%, -1157%].
Drought h=2 exact-category accuracy 0.9828125; Brier P(cat>=2)=0.016098594501699346 ECE=0.12688023683502142; Brier P(cat>=3)=0.0018943817783520355 ECE=0.04352449629364084.
The 2-week ERC-percentile MAE for pi_convlstm_hydro is 31.39 versus 31.91 for persistence, a 2% skill improvement, CI [-18%, 19%].
Fire-condition (ERC percentile) h=2 R²=-0.13249068672241493.
The 4-week drought MAE for pi_convlstm_hydro is 0.35 categories versus 0.04 for persistence, a -867% skill (worse than persistence), CI [-3327%, -380%].
Drought h=4 exact-category accuracy 0.9661931818181818; Brier P(cat>=2)=0.020317763918103415 ECE=0.12033714158672161; Brier P(cat>=3)=0.002216749743191182 ECE=0.04708237188504868.
The 4-week ERC-percentile MAE for pi_convlstm_hydro is 31.16 versus 33.23 for persistence, a 0% skill improvement, CI [-29%, 21%].
Fire-condition (ERC percentile) h=4 R²=-0.10570009299599303.
The 8-week drought MAE for pi_convlstm_hydro is 0.36 categories versus 0.06 for persistence, a -465% skill (worse than persistence), CI [-1140%, -241%].
Drought h=8 exact-category accuracy 0.9448863636363637; Brier P(cat>=2)=0.02376959797227074 ECE=0.11642243084779968; Brier P(cat>=3)=0.0022488567087660034 ECE=0.04742211201492782.
The 8-week ERC-percentile MAE for pi_convlstm_hydro is 30.13 versus 39.33 for persistence, a 22% skill improvement, CI [7%, 37%].
Fire-condition (ERC percentile) h=8 R²=-0.0734769779303075.

### pi_convlstm_both

The 2-week drought MAE for pi_convlstm_both is 0.34 categories versus 0.02 for persistence, a -2528% skill (worse than persistence), CI [-10806%, -1157%].
Drought h=2 exact-category accuracy 0.9828125; Brier P(cat>=2)=0.016098345003740352 ECE=0.12687925362860727; Brier P(cat>=3)=0.0018943791049193714 ECE=0.04352446558204423.
The 2-week ERC-percentile MAE for pi_convlstm_both is 31.39 versus 31.91 for persistence, a 2% skill improvement, CI [-18%, 19%].
Fire-condition (ERC percentile) h=2 R²=-0.1324881377978373.
The 4-week drought MAE for pi_convlstm_both is 0.35 categories versus 0.04 for persistence, a -867% skill (worse than persistence), CI [-3327%, -380%].
Drought h=4 exact-category accuracy 0.9661931818181818; Brier P(cat>=2)=0.020317637207940383 ECE=0.12033661467615854; Brier P(cat>=3)=0.002216716121513539 ECE=0.04708201483220116.
The 4-week ERC-percentile MAE for pi_convlstm_both is 31.16 versus 33.23 for persistence, a 0% skill improvement, CI [-29%, 21%].
Fire-condition (ERC percentile) h=4 R²=-0.10569797203940312.
The 8-week drought MAE for pi_convlstm_both is 0.36 categories versus 0.06 for persistence, a -465% skill (worse than persistence), CI [-1140%, -241%].
Drought h=8 exact-category accuracy 0.9448863636363637; Brier P(cat>=2)=0.023769590597944017 ECE=0.11642239906782792; Brier P(cat>=3)=0.0022488834267313865 ECE=0.04742239371795828.
The 8-week ERC-percentile MAE for pi_convlstm_both is 30.13 versus 39.33 for persistence, a 22% skill improvement, CI [7%, 37%].
Fire-condition (ERC percentile) h=8 R²=-0.07347526824674344.

### ensemble

The 2-week drought MAE for ensemble is 0.20 categories versus 0.02 for persistence, a -925% skill (worse than persistence), CI [-5765%, -442%].
Drought h=2 exact-category accuracy 0.9813701923076923; Brier P(cat>=2)=0.0068119140878480635 ECE=0.05262232183077703; Brier P(cat>=3)=0.00041151588111505716 ECE=0.018661097612930232.
The 2-week ERC-percentile MAE for ensemble is 29.58 versus 31.91 for persistence, a 7% skill improvement, CI [-9%, 22%].
Fire-condition (ERC percentile) h=2 R²=0.07618850944889277.
The 4-week drought MAE for ensemble is 0.23 categories versus 0.04 for persistence, a -538% skill (worse than persistence), CI [-2277%, -265%].
Drought h=4 exact-category accuracy 0.9603766025641025; Brier P(cat>=2)=0.00978505909303701 ECE=0.050371346292921726; Brier P(cat>=3)=0.0004815529627779934 ECE=0.020186855441495784.
The 4-week ERC-percentile MAE for ensemble is 30.01 versus 33.23 for persistence, a 10% skill improvement, CI [-15%, 26%].
Fire-condition (ERC percentile) h=4 R²=0.050429659182359976.
The 8-week drought MAE for ensemble is 0.24 categories versus 0.06 for persistence, a -317% skill (worse than persistence), CI [-776%, -171%].
Drought h=8 exact-category accuracy 0.9457932692307692; Brier P(cat>=2)=0.011978164858880301 ECE=0.052804037566682976; Brier P(cat>=3)=0.000489013429093148 ECE=0.02034475247042409.
The 8-week ERC-percentile MAE for ensemble is 29.02 versus 39.33 for persistence, a 26% skill improvement, CI [13%, 37%].
Fire-condition (ERC percentile) h=8 R²=0.03582988139904486.

## Validation table

| arm | ERC h=4 MAE | drought h=4 MAE | drought h=4 exact acc |
| --- | --- | --- | --- |
| lightgbm | 32.0010432284137 | 0.14284844906397304 | 0.9545272435897436 |
| pi_convlstm_none | 31.10427767760826 | 0.3452484488741241 | 0.9661931818181818 |
| pi_convlstm_hydro | 31.164296155806746 | 0.346668058257042 | 0.9661931818181818 |
| pi_convlstm_both | 31.164282257358234 | 0.34666658970527353 | 0.9661931818181818 |
| ensemble | 30.0096668324648 | 0.22766784671314672 | 0.9603766025641025 |
| persistence | 33.23277243589744 | 0.03565705128205128 | 0.9688701923076923 |
| climatology | 33.624579326923076 | 0.4503165064102564 | 0.5525641025641026 |
| random | 33.64865686759096 | 0.041185897435897435 | 0.9655448717948718 |

## Feature-group ablation (LightGBM, validation ERC h=4)

| group dropped | MAE | delta vs full |
| --- | --- | --- |
| none (full) | 32.0010432284137 |  |
| precipitation_deficit | 32.03928671295768 | 0.038243484543983186 |
| snowpack | 31.035353772092172 | -0.9656894563215275 |
| soil_dryness | 32.52626023237559 | 0.5252170039618917 |
| vegetation_fuel_dryness | 32.21366208769354 | 0.2126188592798428 |
| heat | 31.54948834339615 | -0.4515548850175506 |

## PI-ConvLSTM penalties

`k` and `f(vpd, precip_28d)` are fit on the training split only. λ_hydro = λ_fuel = 0.1 a priori; not searched on val or hindcast.
Configs: no penalties, hydro only, both.

L_hydro did not improve validation ERC h=4 MAE (31.164 vs 31.104 with no penalties).
L_fuel on top of L_hydro improved validation ERC h=4 MAE (31.164 vs 31.164 hydro-only).
Both penalties together did not beat no-penalty (31.164 vs 31.104).

## Hindcast 2026 (first look after freeze)

**Contaminated:** a post-hindcast scoring fix (`merge_pred` + NIFC epoch-ms dates) was applied. Hyperparameters were not changed. Skill vs persistence below is from look_index>1. See DECISIONS.md.

The 2-week drought MAE for ensemble is 1.18 categories versus 0.31 for persistence, a -282% skill (worse than persistence), CI [-517%, -132%].
The 4-week drought MAE for ensemble is 1.48 categories versus 0.63 for persistence, a -134% skill (worse than persistence), CI [-222%, -63%].
The 8-week drought MAE for ensemble is 1.74 categories versus 1.09 for persistence, a -59% skill (worse than persistence), CI [-121%, -23%].
The 2-week ERC-percentile MAE for ensemble is 32.24 versus 22.92 for persistence, a -41% skill (worse than persistence), CI [-87%, -11%].
The 4-week ERC-percentile MAE for ensemble is 33.80 versus 25.38 for persistence, a -33% skill (worse than persistence), CI [-85%, -6%].
The 8-week ERC-percentile MAE for ensemble is 31.15 versus 26.32 for persistence, a -18% skill (worse than persistence), CI [-67%, 19%].

The 4-week drought MAE for lightgbm is 1.14 categories versus 0.63 for persistence, a -80% skill (worse than persistence), CI [-152%, -25%].
The 8-week drought MAE for lightgbm is 1.53 categories versus 1.09 for persistence, a -40% skill (worse than persistence), CI [-94%, -8%].
The 4-week ERC-percentile MAE for lightgbm is 28.15 versus 25.38 for persistence, a -11% skill (worse than persistence), CI [-48%, 10%].
The 8-week ERC-percentile MAE for lightgbm is 26.98 versus 26.32 for persistence, a -3% skill (worse than persistence), CI [-32%, 21%].
The 4-week drought MAE for pi_convlstm_none is 2.06 categories versus 0.63 for persistence, a -191% skill (worse than persistence), CI [-325%, -94%].
The 8-week drought MAE for pi_convlstm_none is 1.90 categories versus 1.09 for persistence, a -75% skill (worse than persistence), CI [-164%, -25%].
The 4-week ERC-percentile MAE for pi_convlstm_none is 44.86 versus 25.38 for persistence, a -62% skill (worse than persistence), CI [-153%, -18%].
The 8-week ERC-percentile MAE for pi_convlstm_none is 41.71 versus 26.32 for persistence, a -39% skill (worse than persistence), CI [-124%, 16%].
The 4-week drought MAE for pi_convlstm_hydro is 2.06 categories versus 0.63 for persistence, a -191% skill (worse than persistence), CI [-324%, -93%].
The 8-week drought MAE for pi_convlstm_hydro is 1.90 categories versus 1.09 for persistence, a -75% skill (worse than persistence), CI [-164%, -25%].
The 4-week ERC-percentile MAE for pi_convlstm_hydro is 45.18 versus 25.38 for persistence, a -63% skill (worse than persistence), CI [-155%, -19%].
The 8-week ERC-percentile MAE for pi_convlstm_hydro is 41.69 versus 26.32 for persistence, a -39% skill (worse than persistence), CI [-124%, 16%].
The 4-week drought MAE for pi_convlstm_both is 2.06 categories versus 0.63 for persistence, a -191% skill (worse than persistence), CI [-324%, -93%].
The 8-week drought MAE for pi_convlstm_both is 1.90 categories versus 1.09 for persistence, a -75% skill (worse than persistence), CI [-164%, -25%].
The 4-week ERC-percentile MAE for pi_convlstm_both is 45.18 versus 25.38 for persistence, a -63% skill (worse than persistence), CI [-155%, -19%].
The 8-week ERC-percentile MAE for pi_convlstm_both is 41.69 versus 26.32 for persistence, a -39% skill (worse than persistence), CI [-124%, 16%].
