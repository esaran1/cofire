# COFIRE metrics

These models forecast **drought severity** and **conditions that allow fires to spread** (ERC percentile / fire-spread condition index). They do not forecast ignitions.

Shipping arm: **ensemble** (best validation ERC-percentile MAE).
Git: `a3f212d083122dcf5b6d62efe2a574d7beb4c67b`  MANIFEST: `ec21777b791c57a0295143b43cf551652c08149efe52a05354b00bddd414d18c`
Displayed resolution: 4000 m (gridMET native 4 km unless HLS is on and loaded).

Hyperparameters were frozen on the validation split. Hindcast 2026 is scored only in hindcast.py.

## Effective sample size

Training-window weekly domain-mean AR(1): USDM rho=0.9715393715327675 n_weeks=261 n_eff=3.7677279679039004; ERC rho=0.6665764669755729 n_weeks=261 n_eff=52.21695124334848. Headline intervals use week-block bootstrap, not cell-weeks as independent samples.

## Validation sentences

### lightgbm

The 2-week drought MAE for lightgbm is 0.30 categories versus 0.17 for persistence, a -82% skill (worse than persistence), CI [-206%, -26%].
Drought h=2 exact-category accuracy 0.7979878917378918; Brier P(cat>=2)=0.0738537183528063 ECE=0.07275725975675652; Brier P(cat>=3)=0.03453804397032176 ECE=0.01049946335616471.
The 2-week ERC-percentile MAE for lightgbm is 30.04 versus 26.96 for persistence, a -11% skill (worse than persistence), CI [-42%, 8%].
Fire-condition (ERC percentile) h=2 R²=-0.0030598747865098197.
The 4-week drought MAE for lightgbm is 0.52 categories versus 0.27 for persistence, a -91% skill (worse than persistence), CI [-215%, -36%].
Drought h=4 exact-category accuracy 0.5876958689458689; Brier P(cat>=2)=0.14738959004843588 ECE=0.13788303142306504; Brier P(cat>=3)=0.04027697995636926 ECE=0.01855420281258193.
The 4-week ERC-percentile MAE for lightgbm is 32.71 versus 29.27 for persistence, a -12% skill (worse than persistence), CI [-34%, 4%].
Fire-condition (ERC percentile) h=4 R²=-0.12588122826823467.
The 8-week drought MAE for lightgbm is 0.84 categories versus 0.40 for persistence, a -109% skill (worse than persistence), CI [-254%, -44%].
Drought h=8 exact-category accuracy 0.38256766381766383; Brier P(cat>=2)=0.18371890929349705 ECE=0.21034434805907462; Brier P(cat>=3)=0.04084578095097949 ECE=0.01748842038716433.
The 8-week ERC-percentile MAE for lightgbm is 33.74 versus 41.35 for persistence, a 18% skill improvement, CI [2%, 32%].
Fire-condition (ERC percentile) h=8 R²=-0.3391710714563432.

### pi_convlstm_none

The 2-week drought MAE for pi_convlstm_none is 1.15 categories versus 0.17 for persistence, a -618% skill (worse than persistence), CI [-1727%, -264%].
Drought h=2 exact-category accuracy 0.07554713804713804; Brier P(cat>=2)=0.23205715150304876 ECE=0.325470322155102; Brier P(cat>=3)=0.04510275506469753 ECE=0.05351414070629298.
The 2-week ERC-percentile MAE for pi_convlstm_none is 30.98 versus 26.96 for persistence, a -29% skill (worse than persistence), CI [-80%, 6%].
Fire-condition (ERC percentile) h=2 R²=-0.16587478674184353.
The 4-week drought MAE for pi_convlstm_none is 1.13 categories versus 0.27 for persistence, a -299% skill (worse than persistence), CI [-828%, -132%].
Drought h=4 exact-category accuracy 0.06160563973063973; Brier P(cat>=2)=0.21083782923887745 ECE=0.327970349541881; Brier P(cat>=3)=0.044916226981850195 ECE=0.05174200783910148.
The 4-week ERC-percentile MAE for pi_convlstm_none is 30.01 versus 29.27 for persistence, a -1% skill (worse than persistence), CI [-31%, 22%].
Fire-condition (ERC percentile) h=4 R²=-0.08253327020929935.
The 8-week drought MAE for pi_convlstm_none is 1.12 categories versus 0.40 for persistence, a -169% skill (worse than persistence), CI [-462%, -73%].
Drought h=8 exact-category accuracy 0.047664141414141416; Brier P(cat>=2)=0.2006766161633181 ECE=0.4018934864930257; Brier P(cat>=3)=0.032421450540848204 ECE=0.061871958713859365.
The 8-week ERC-percentile MAE for pi_convlstm_none is 26.46 versus 41.35 for persistence, a 39% skill improvement, CI [25%, 50%].
Fire-condition (ERC percentile) h=8 R²=-0.0046788264637416255.

### pi_convlstm_hydro

The 2-week drought MAE for pi_convlstm_hydro is 1.15 categories versus 0.17 for persistence, a -618% skill (worse than persistence), CI [-1727%, -264%].
Drought h=2 exact-category accuracy 0.07554713804713804; Brier P(cat>=2)=0.23192808597594552 ECE=0.32527198693448495; Brier P(cat>=3)=0.04510533148673227 ECE=0.053538196672754425.
The 2-week ERC-percentile MAE for pi_convlstm_hydro is 30.93 versus 26.96 for persistence, a -29% skill (worse than persistence), CI [-80%, 6%].
Fire-condition (ERC percentile) h=2 R²=-0.16081038619945143.
The 4-week drought MAE for pi_convlstm_hydro is 1.13 categories versus 0.27 for persistence, a -298% skill (worse than persistence), CI [-826%, -131%].
Drought h=4 exact-category accuracy 0.06160563973063973; Brier P(cat>=2)=0.210750632272781 ECE=0.3278373880578387; Brier P(cat>=3)=0.04490584567142619 ECE=0.05164158829254246.
The 4-week ERC-percentile MAE for pi_convlstm_hydro is 30.07 versus 29.27 for persistence, a -1% skill (worse than persistence), CI [-31%, 22%].
Fire-condition (ERC percentile) h=4 R²=-0.09012381901847166.
The 8-week drought MAE for pi_convlstm_hydro is 1.12 categories versus 0.40 for persistence, a -169% skill (worse than persistence), CI [-460%, -72%].
Drought h=8 exact-category accuracy 0.047664141414141416; Brier P(cat>=2)=0.20058087576076641 ECE=0.40177435407208073; Brier P(cat>=3)=0.032423622961696666 ECE=0.06188952891306594.
The 8-week ERC-percentile MAE for pi_convlstm_hydro is 26.46 versus 41.35 for persistence, a 39% skill improvement, CI [25%, 50%].
Fire-condition (ERC percentile) h=8 R²=-0.004713334181480455.

### pi_convlstm_both

The 2-week drought MAE for pi_convlstm_both is 1.15 categories versus 0.17 for persistence, a -618% skill (worse than persistence), CI [-1727%, -264%].
Drought h=2 exact-category accuracy 0.07554713804713804; Brier P(cat>=2)=0.23193353064735142 ECE=0.3252803482874124; Brier P(cat>=3)=0.04510565382525393 ECE=0.05354121182802187.
The 2-week ERC-percentile MAE for pi_convlstm_both is 30.94 versus 26.96 for persistence, a -29% skill (worse than persistence), CI [-80%, 6%].
Fire-condition (ERC percentile) h=2 R²=-0.16109294210395175.
The 4-week drought MAE for pi_convlstm_both is 1.13 categories versus 0.27 for persistence, a -298% skill (worse than persistence), CI [-826%, -131%].
Drought h=4 exact-category accuracy 0.06160563973063973; Brier P(cat>=2)=0.21075238676306407 ECE=0.3278400633713036; Brier P(cat>=3)=0.04490635735027247 ECE=0.051646545213437096.
The 4-week ERC-percentile MAE for pi_convlstm_both is 30.07 versus 29.27 for persistence, a -1% skill (worse than persistence), CI [-32%, 22%].
Fire-condition (ERC percentile) h=4 R²=-0.09039173209167517.
The 8-week drought MAE for pi_convlstm_both is 1.12 categories versus 0.40 for persistence, a -169% skill (worse than persistence), CI [-460%, -72%].
Drought h=8 exact-category accuracy 0.047664141414141416; Brier P(cat>=2)=0.20057036158260175 ECE=0.40176126939755696; Brier P(cat>=3)=0.03242273929157928 ECE=0.06188239171702778.
The 8-week ERC-percentile MAE for pi_convlstm_both is 26.46 versus 41.35 for persistence, a 39% skill improvement, CI [25%, 50%].
Fire-condition (ERC percentile) h=8 R²=-0.004772426263192964.

### ensemble

The 2-week drought MAE for ensemble is 0.68 categories versus 0.17 for persistence, a -306% skill (worse than persistence), CI [-738%, -141%].
Drought h=2 exact-category accuracy 0.17761752136752137; Brier P(cat>=2)=0.11441556570239395 ECE=0.21227299611917094; Brier P(cat>=3)=0.033178859849716705 ECE=0.030059356835827826.
The 2-week ERC-percentile MAE for ensemble is 28.70 versus 26.96 for persistence, a -6% skill (worse than persistence), CI [-39%, 13%].
Fire-condition (ERC percentile) h=2 R²=0.08208050040167059.
The 4-week drought MAE for ensemble is 0.78 categories versus 0.27 for persistence, a -186% skill (worse than persistence), CI [-444%, -81%].
Drought h=4 exact-category accuracy 0.11355947293447294; Brier P(cat>=2)=0.1528302129961972 ECE=0.21660065721378857; Brier P(cat>=3)=0.038077637995382635 ECE=0.0353485868779279.
The 4-week ERC-percentile MAE for ensemble is 28.98 versus 29.27 for persistence, a 1% skill improvement, CI [-19%, 17%].
Fire-condition (ERC percentile) h=4 R²=0.11003536122977442.
The 8-week drought MAE for ensemble is 0.96 categories versus 0.40 for persistence, a -138% skill (worse than persistence), CI [-331%, -59%].
Drought h=8 exact-category accuracy 0.08052884615384616; Brier P(cat>=2)=0.1911252941354207 ECE=0.2751383108055155; Brier P(cat>=3)=0.03852880295768204 ECE=0.03232710015072746.
The 8-week ERC-percentile MAE for ensemble is 28.16 versus 41.35 for persistence, a 32% skill improvement, CI [19%, 43%].
Fire-condition (ERC percentile) h=8 R²=0.10931605139975176.

## Validation table

| arm | ERC h=4 MAE | drought h=4 MAE | drought h=4 exact acc |
| --- | --- | --- | --- |
| lightgbm | 32.707949658083656 | 0.5196144648137327 | 0.5876958689458689 |
| pi_convlstm_none | 30.008899480505825 | 1.1296230862512933 | 0.06160563973063973 |
| pi_convlstm_hydro | 30.07016630917286 | 1.1269095682786772 | 0.06160563973063973 |
| pi_convlstm_both | 30.072280530576354 | 1.1267993275690762 | 0.06160563973063973 |
| ensemble | 28.976687118246048 | 0.7787921069720659 | 0.11355947293447294 |
| persistence | 29.26860754985755 | 0.27194622507122507 | 0.8000801282051282 |
| climatology | 33.2536391559829 | 1.0302773326210828 | 0.10915242165242166 |
| random | 33.28247185547804 | 0.5117076210826211 | 0.7155448717948718 |

## Feature-group ablation (LightGBM, validation ERC h=4)

| group dropped | MAE | delta vs full |
| --- | --- | --- |
| none (full) | 32.707949658083656 |  |
| precipitation_deficit | 32.32907469437473 | -0.37887496370892393 |
| snowpack | 32.91684285926501 | 0.20889320118135402 |
| soil_dryness | 32.21361078934075 | -0.4943388687429078 |
| vegetation_fuel_dryness | 33.66406045743533 | 0.9561107993516771 |
| heat | 33.34649951068391 | 0.6385498526002564 |

## PI-ConvLSTM penalties

`k` and `f(vpd, precip_28d)` are fit on the training split only. λ_hydro = λ_fuel = 0.1 a priori; not searched on val or hindcast.
Configs: no penalties, hydro only, both.

L_hydro did not improve validation ERC h=4 MAE (30.070 vs 30.009 with no penalties).
L_fuel on top of L_hydro did not improve validation ERC h=4 MAE (30.072 vs 30.070 hydro-only).
Both penalties together did not beat no-penalty (30.072 vs 30.009).
