# Conformal vs bootstrap

Nominal coverage target: **0.90**.
Bootstrap is a 300-draw residual bootstrap on the calibrate-split residuals.
Conformal `qhat` is frozen on the same split; ACI updates alpha online.
Neither method is tuned on the 2026 hindcast.

2026 is treated as a distribution-shift test. Coverage is reported, not retuned.

On the 2024–2025 calibration split, conformal 4-week ERC coverage is 0.914 (target 0.90, mean width 100.54); bootstrap coverage is 0.895 (mean width 97.91).
Hindcast coverage is not in this file yet.

## calibrate
| method | horizon | stratum | coverage | mean width | n |
| --- | --- | --- | --- | --- | --- |
| conformal | 2 | overall | 0.914 | 97.92 | 45360 |
| conformal | 2 | usdm=0 | 0.914 | 97.93 | 43500 |
| conformal | 2 | usdm=1 | 0.926 | 97.76 | 1860 |
| conformal | 2 | month=1 | 0.693 | 97.92 | 3888 |
| conformal | 2 | month=2 | 0.977 | 97.92 | 3456 |
| conformal | 2 | month=3 | 0.881 | 97.92 | 3456 |
| conformal | 2 | month=4 | 0.860 | 97.92 | 4320 |
| conformal | 2 | month=5 | 0.997 | 97.92 | 3456 |
| conformal | 2 | month=6 | 0.993 | 97.92 | 3456 |
| conformal | 2 | month=7 | 0.886 | 97.92 | 4320 |
| conformal | 2 | month=8 | 0.866 | 97.92 | 3456 |
| conformal | 2 | month=9 | 0.999 | 97.92 | 3888 |
| conformal | 2 | month=10 | 0.989 | 97.92 | 3888 |
| conformal | 2 | month=11 | 0.933 | 97.92 | 3456 |
| conformal | 2 | month=12 | 0.923 | 97.92 | 4320 |
| conformal | 4 | overall | 0.914 | 100.54 | 45360 |
| conformal | 4 | usdm=0 | 0.914 | 100.53 | 43500 |
| conformal | 4 | usdm=1 | 0.918 | 100.69 | 1860 |
| conformal | 4 | month=1 | 0.678 | 100.54 | 3888 |
| conformal | 4 | month=2 | 0.992 | 100.54 | 3456 |
| conformal | 4 | month=3 | 0.854 | 100.54 | 3456 |
| conformal | 4 | month=4 | 0.950 | 100.54 | 4320 |
| conformal | 4 | month=5 | 1.000 | 100.54 | 3456 |
| conformal | 4 | month=6 | 0.991 | 100.54 | 3456 |
| conformal | 4 | month=7 | 0.900 | 100.54 | 4320 |
| conformal | 4 | month=8 | 0.914 | 100.54 | 3456 |
| conformal | 4 | month=9 | 1.000 | 100.54 | 3888 |
| conformal | 4 | month=10 | 0.867 | 100.54 | 3888 |
| conformal | 4 | month=11 | 0.982 | 100.54 | 3456 |
| conformal | 4 | month=12 | 0.874 | 100.54 | 4320 |
| conformal | 8 | overall | 0.915 | 94.20 | 45360 |
| conformal | 8 | usdm=0 | 0.912 | 94.16 | 43500 |
| conformal | 8 | usdm=1 | 0.978 | 95.16 | 1860 |
| conformal | 8 | month=1 | 0.917 | 94.20 | 3888 |
| conformal | 8 | month=2 | 0.852 | 94.20 | 3456 |
| conformal | 8 | month=3 | 0.997 | 94.20 | 3456 |
| conformal | 8 | month=4 | 0.998 | 94.20 | 4320 |
| conformal | 8 | month=5 | 0.998 | 94.20 | 3456 |
| conformal | 8 | month=6 | 0.868 | 94.20 | 3456 |
| conformal | 8 | month=7 | 0.933 | 94.20 | 4320 |
| conformal | 8 | month=8 | 1.000 | 94.20 | 3456 |
| conformal | 8 | month=9 | 0.975 | 94.20 | 3888 |
| conformal | 8 | month=10 | 0.912 | 94.20 | 3888 |
| conformal | 8 | month=11 | 0.856 | 94.20 | 3456 |
| conformal | 8 | month=12 | 0.696 | 94.20 | 4320 |
| bootstrap | 2 | overall | 0.894 | 95.15 | 45360 |
| bootstrap | 2 | usdm=0 | 0.896 | 95.15 | 43500 |
| bootstrap | 2 | usdm=1 | 0.851 | 95.22 | 1860 |
| bootstrap | 2 | month=1 | 0.666 | 95.21 | 3888 |
| bootstrap | 2 | month=2 | 0.945 | 95.11 | 3456 |
| bootstrap | 2 | month=3 | 0.842 | 95.10 | 3456 |
| bootstrap | 2 | month=4 | 0.795 | 95.19 | 4320 |
| bootstrap | 2 | month=5 | 0.977 | 95.25 | 3456 |
| bootstrap | 2 | month=6 | 0.998 | 95.12 | 3456 |
| bootstrap | 2 | month=7 | 0.882 | 95.23 | 4320 |
| bootstrap | 2 | month=8 | 0.855 | 95.22 | 3456 |
| bootstrap | 2 | month=9 | 0.988 | 95.02 | 3888 |
| bootstrap | 2 | month=10 | 0.986 | 95.11 | 3888 |
| bootstrap | 2 | month=11 | 0.910 | 95.22 | 3456 |
| bootstrap | 2 | month=12 | 0.910 | 95.07 | 4320 |
| bootstrap | 4 | overall | 0.895 | 97.91 | 45360 |
| bootstrap | 4 | usdm=0 | 0.895 | 97.92 | 43500 |
| bootstrap | 4 | usdm=1 | 0.904 | 97.81 | 1860 |
| bootstrap | 4 | month=1 | 0.652 | 97.84 | 3888 |
| bootstrap | 4 | month=2 | 0.991 | 97.83 | 3456 |
| bootstrap | 4 | month=3 | 0.834 | 98.02 | 3456 |
| bootstrap | 4 | month=4 | 0.926 | 97.91 | 4320 |
| bootstrap | 4 | month=5 | 0.992 | 97.91 | 3456 |
| bootstrap | 4 | month=6 | 0.985 | 98.08 | 3456 |
| bootstrap | 4 | month=7 | 0.887 | 97.91 | 4320 |
| bootstrap | 4 | month=8 | 0.816 | 97.81 | 3456 |
| bootstrap | 4 | month=9 | 1.000 | 97.81 | 3888 |
| bootstrap | 4 | month=10 | 0.865 | 97.96 | 3888 |
| bootstrap | 4 | month=11 | 0.952 | 98.01 | 3456 |
| bootstrap | 4 | month=12 | 0.868 | 97.90 | 4320 |
| bootstrap | 8 | overall | 0.900 | 98.51 | 45360 |
| bootstrap | 8 | usdm=0 | 0.897 | 98.51 | 43500 |
| bootstrap | 8 | usdm=1 | 0.951 | 98.57 | 1860 |
| bootstrap | 8 | month=1 | 0.913 | 98.62 | 3888 |
| bootstrap | 8 | month=2 | 0.908 | 98.37 | 3456 |
| bootstrap | 8 | month=3 | 0.949 | 98.52 | 3456 |
| bootstrap | 8 | month=4 | 0.990 | 98.53 | 4320 |
| bootstrap | 8 | month=5 | 0.988 | 98.43 | 3456 |
| bootstrap | 8 | month=6 | 0.926 | 98.61 | 3456 |
| bootstrap | 8 | month=7 | 0.828 | 98.53 | 4320 |
| bootstrap | 8 | month=8 | 0.991 | 98.59 | 3456 |
| bootstrap | 8 | month=9 | 0.952 | 98.33 | 3888 |
| bootstrap | 8 | month=10 | 0.798 | 98.46 | 3888 |
| bootstrap | 8 | month=11 | 0.876 | 98.52 | 3456 |
| bootstrap | 8 | month=12 | 0.720 | 98.60 | 4320 |

## hindcast
No rows available.

Numbers are empirical. If conformal holds 0.90 where bootstrap drops, that is the result; the reverse is also reportable.
