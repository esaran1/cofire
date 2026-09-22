# Phase 4: conformal PID against ACI

Pre-registered in `docs/PREREGISTRATION_V1.md`, hash recorded in STATUS.md
before this ran. Every figure below is read from
`artifacts/uncertainty/pid_results.csv`.

## Verdict: not adopted

```json
{
  "pueblo": {
    "dev_improvement": 0.1179,
    "width_ratio": 0.872,
    "meets_rule": true
  },
  "domains_evaluated": [
    "pueblo"
  ],
  "adopted": false,
  "note": "not adopted: larimer not evaluated, and the rule requires both domains. See STATUS.md."
}
```

The rule requires the improvement on both domains. Only Pueblo has
prediction parquets, so the comparison is single-domain and the verdict is
not adopted regardless of the numbers. Larimer needs a pipeline run before
this can be closed.

## Results (Pueblo, validation and calibration splits, 2026 never opened)

| h | arm | coverage | mean abs dev | mean width | worst 8wk dev | cov in transitions |
|---|---|---|---|---|---|---|
| 2 | aci | 0.894 | 0.1160 | 88.69 | 0.3563 | 0.893 |
| 2 | pid_full | 0.761 | 0.1400 | 65.55 | 0.2194 | 0.778 |
| 2 | pid_p | 0.901 | 0.1091 | 87.66 | 0.1046 | 0.930 |
| 2 | pid_pi | 0.873 | 0.0724 | 77.86 | 0.0942 | 0.901 |
| 2 | split | 0.894 | 0.1560 | 99.35 | 0.4909 | 0.850 |
| 4 | aci | 0.933 | 0.0856 | 93.36 | 0.0931 | 0.955 |
| 4 | pid_full | 0.761 | 0.1400 | 66.69 | 0.2073 | 0.772 |
| 4 | pid_p | 0.900 | 0.1076 | 90.03 | 0.1121 | 0.899 |
| 4 | pid_pi | 0.874 | 0.0718 | 79.70 | 0.1017 | 0.868 |
| 4 | split | 0.916 | 0.1399 | 104.52 | 0.2854 | 0.910 |
| 8 | aci | 0.363 | 0.5518 | 43.75 | 0.8346 | 0.166 |
| 8 | pid_full | 0.785 | 0.1199 | 64.66 | 0.1954 | 0.801 |
| 8 | pid_p | 0.899 | 0.0947 | 85.63 | 0.1000 | 0.858 |
| 8 | pid_pi | 0.873 | 0.0689 | 75.90 | 0.0826 | 0.866 |
| 8 | split | 0.364 | 0.5529 | 43.98 | 0.8346 | 0.167 |

## What the numbers say

At h=8 both frozen split conformal and ACI collapse to about 0.36 coverage
against a 0.90 target, a 54-point miss, and ACI is indistinguishable from the
baseline it exists to improve. The PID arms hold 0.79 to 0.90 and pay for it
in width, roughly doubling from 44 to between 65 and 86. Width is a
pre-registered secondary endpoint precisely so that this trade is visible.

`pid_full` is the weakest PID arm at every horizon: the scorecaster pulls the
radius toward the recent median score, which lowers it during calm stretches
just before volatility returns. The pre-registration fixed `pid_full` as the
arm compared against ACI, and that is what the adoption rule used. That
`pid_pi` scores better is recorded as an observation for a future
pre-registration, not swapped in after the fact.
