# Conformal vs bootstrap

Nominal coverage target: **0.90**.
Bootstrap is a 300-draw residual bootstrap on the calibrate-split residuals.
Conformal `qhat` is frozen on the same split; ACI updates alpha online.
Neither method is tuned on the 2026 hindcast.

2026 is treated as a distribution-shift test. Coverage is reported, not retuned.

On the 2024–2025 calibration split, conformal 4-week ERC coverage is 0.914 (target 0.90, mean width 112.28); bootstrap coverage is 0.894 (mean width 105.93).
On the 2026 hindcast, conformal 4-week ERC coverage is 0.485 (mean width 67.10); bootstrap coverage is 0.963 (mean width 105.93).
Conformal hindcast coverage misses the 0.90 target by 41.5 points. Whether the ACI learning rate (0.01) is too slow for weekly steps is a pre-registered follow-up, not a post-hindcast fix.

## calibrate
| method | horizon | stratum | coverage | mean width | n |
| --- | --- | --- | --- | --- | --- |
| conformal | 2 | overall | 0.914 | 110.85 | 50400 |
| conformal | 2 | usdm=0 | 0.952 | 110.90 | 28804 |
| conformal | 2 | usdm=1 | 0.888 | 110.80 | 11712 |
| conformal | 2 | usdm=2 | 0.824 | 110.82 | 7934 |
| conformal | 2 | usdm=3 | 0.889 | 110.59 | 1950 |
| conformal | 2 | month=1 | 0.613 | 110.85 | 4320 |
| conformal | 2 | month=2 | 0.979 | 110.85 | 3840 |
| conformal | 2 | month=3 | 0.972 | 110.85 | 3840 |
| conformal | 2 | month=4 | 0.947 | 110.85 | 4800 |
| conformal | 2 | month=5 | 0.985 | 110.85 | 3840 |
| conformal | 2 | month=6 | 0.990 | 110.85 | 3840 |
| conformal | 2 | month=7 | 0.936 | 110.85 | 4800 |
| conformal | 2 | month=8 | 0.965 | 110.85 | 3840 |
| conformal | 2 | month=9 | 0.929 | 110.85 | 4320 |
| conformal | 2 | month=10 | 0.947 | 110.85 | 4320 |
| conformal | 2 | month=11 | 0.983 | 110.85 | 3840 |
| conformal | 2 | month=12 | 0.777 | 110.85 | 4800 |
| conformal | 4 | overall | 0.914 | 112.28 | 50400 |
| conformal | 4 | usdm=0 | 0.935 | 112.26 | 28804 |
| conformal | 4 | usdm=1 | 0.894 | 112.15 | 11712 |
| conformal | 4 | usdm=2 | 0.867 | 112.40 | 7934 |
| conformal | 4 | usdm=3 | 0.914 | 112.97 | 1950 |
| conformal | 4 | month=1 | 0.878 | 112.28 | 4320 |
| conformal | 4 | month=2 | 0.973 | 112.28 | 3840 |
| conformal | 4 | month=3 | 0.976 | 112.28 | 3840 |
| conformal | 4 | month=4 | 0.935 | 112.28 | 4800 |
| conformal | 4 | month=5 | 0.959 | 112.28 | 3840 |
| conformal | 4 | month=6 | 0.983 | 112.28 | 3840 |
| conformal | 4 | month=7 | 0.943 | 112.28 | 4800 |
| conformal | 4 | month=8 | 0.989 | 112.28 | 3840 |
| conformal | 4 | month=9 | 0.918 | 112.28 | 4320 |
| conformal | 4 | month=10 | 0.825 | 112.28 | 4320 |
| conformal | 4 | month=11 | 0.902 | 112.28 | 3840 |
| conformal | 4 | month=12 | 0.738 | 112.28 | 4800 |
| conformal | 8 | overall | 0.914 | 114.66 | 50400 |
| conformal | 8 | usdm=0 | 0.920 | 114.70 | 28804 |
| conformal | 8 | usdm=1 | 0.923 | 114.74 | 11712 |
| conformal | 8 | usdm=2 | 0.880 | 114.52 | 7934 |
| conformal | 8 | usdm=3 | 0.916 | 114.20 | 1950 |
| conformal | 8 | month=1 | 0.981 | 114.66 | 4320 |
| conformal | 8 | month=2 | 0.923 | 114.66 | 3840 |
| conformal | 8 | month=3 | 0.998 | 114.66 | 3840 |
| conformal | 8 | month=4 | 0.987 | 114.66 | 4800 |
| conformal | 8 | month=5 | 0.992 | 114.66 | 3840 |
| conformal | 8 | month=6 | 0.872 | 114.66 | 3840 |
| conformal | 8 | month=7 | 0.997 | 114.66 | 4800 |
| conformal | 8 | month=8 | 0.981 | 114.66 | 3840 |
| conformal | 8 | month=9 | 0.987 | 114.66 | 4320 |
| conformal | 8 | month=10 | 0.893 | 114.66 | 4320 |
| conformal | 8 | month=11 | 0.550 | 114.66 | 3840 |
| conformal | 8 | month=12 | 0.788 | 114.66 | 4800 |
| bootstrap | 2 | overall | 0.894 | 106.69 | 50400 |
| bootstrap | 2 | usdm=0 | 0.935 | 106.70 | 28804 |
| bootstrap | 2 | usdm=1 | 0.856 | 106.67 | 11712 |
| bootstrap | 2 | usdm=2 | 0.815 | 106.70 | 7934 |
| bootstrap | 2 | usdm=3 | 0.829 | 106.74 | 1950 |
| bootstrap | 2 | month=1 | 0.611 | 106.71 | 4320 |
| bootstrap | 2 | month=2 | 0.993 | 106.65 | 3840 |
| bootstrap | 2 | month=3 | 0.979 | 106.63 | 3840 |
| bootstrap | 2 | month=4 | 0.953 | 106.68 | 4800 |
| bootstrap | 2 | month=5 | 0.931 | 106.66 | 3840 |
| bootstrap | 2 | month=6 | 0.986 | 106.74 | 3840 |
| bootstrap | 2 | month=7 | 0.890 | 106.67 | 4800 |
| bootstrap | 2 | month=8 | 0.854 | 106.74 | 3840 |
| bootstrap | 2 | month=9 | 0.919 | 106.66 | 4320 |
| bootstrap | 2 | month=10 | 0.878 | 106.73 | 4320 |
| bootstrap | 2 | month=11 | 0.946 | 106.72 | 3840 |
| bootstrap | 2 | month=12 | 0.824 | 106.69 | 4800 |
| bootstrap | 4 | overall | 0.894 | 105.93 | 50400 |
| bootstrap | 4 | usdm=0 | 0.916 | 105.93 | 28804 |
| bootstrap | 4 | usdm=1 | 0.864 | 105.95 | 11712 |
| bootstrap | 4 | usdm=2 | 0.854 | 105.91 | 7934 |
| bootstrap | 4 | usdm=3 | 0.898 | 105.95 | 1950 |
| bootstrap | 4 | month=1 | 0.948 | 105.92 | 4320 |
| bootstrap | 4 | month=2 | 0.998 | 105.94 | 3840 |
| bootstrap | 4 | month=3 | 0.953 | 105.94 | 3840 |
| bootstrap | 4 | month=4 | 0.951 | 105.90 | 4800 |
| bootstrap | 4 | month=5 | 0.930 | 105.90 | 3840 |
| bootstrap | 4 | month=6 | 0.968 | 105.92 | 3840 |
| bootstrap | 4 | month=7 | 0.859 | 105.93 | 4800 |
| bootstrap | 4 | month=8 | 0.711 | 105.97 | 3840 |
| bootstrap | 4 | month=9 | 0.922 | 105.92 | 4320 |
| bootstrap | 4 | month=10 | 0.777 | 105.93 | 4320 |
| bootstrap | 4 | month=11 | 0.878 | 105.98 | 3840 |
| bootstrap | 4 | month=12 | 0.841 | 105.94 | 4800 |
| bootstrap | 8 | overall | 0.894 | 106.28 | 50400 |
| bootstrap | 8 | usdm=0 | 0.884 | 106.28 | 28804 |
| bootstrap | 8 | usdm=1 | 0.894 | 106.29 | 11712 |
| bootstrap | 8 | usdm=2 | 0.912 | 106.25 | 7934 |
| bootstrap | 8 | usdm=3 | 0.975 | 106.33 | 1950 |
| bootstrap | 8 | month=1 | 0.995 | 106.33 | 4320 |
| bootstrap | 8 | month=2 | 0.927 | 106.30 | 3840 |
| bootstrap | 8 | month=3 | 0.924 | 106.26 | 3840 |
| bootstrap | 8 | month=4 | 0.979 | 106.31 | 4800 |
| bootstrap | 8 | month=5 | 0.983 | 106.30 | 3840 |
| bootstrap | 8 | month=6 | 0.800 | 106.27 | 3840 |
| bootstrap | 8 | month=7 | 0.781 | 106.27 | 4800 |
| bootstrap | 8 | month=8 | 0.908 | 106.26 | 3840 |
| bootstrap | 8 | month=9 | 0.973 | 106.23 | 4320 |
| bootstrap | 8 | month=10 | 0.937 | 106.31 | 4320 |
| bootstrap | 8 | month=11 | 0.620 | 106.28 | 3840 |
| bootstrap | 8 | month=12 | 0.884 | 106.27 | 4800 |

## hindcast
| method | horizon | stratum | coverage | mean width | n |
| --- | --- | --- | --- | --- | --- |
| conformal | 2 | overall | 0.498 | 63.36 | 17280 |
| conformal | 2 | usdm=1 | 0.548 | 72.35 | 3452 |
| conformal | 2 | usdm=2 | 0.463 | 60.32 | 7749 |
| conformal | 2 | usdm=3 | 0.508 | 62.27 | 4789 |
| conformal | 2 | usdm=4 | 0.536 | 61.65 | 1290 |
| conformal | 2 | month=1 | 0.907 | 98.45 | 1920 |
| conformal | 2 | month=2 | 0.971 | 76.91 | 1920 |
| conformal | 2 | month=3 | 0.162 | 65.87 | 2400 |
| conformal | 2 | month=4 | 0.458 | 64.87 | 1920 |
| conformal | 2 | month=5 | 0.731 | 56.81 | 1920 |
| conformal | 2 | month=6 | 0.079 | 53.44 | 2400 |
| conformal | 2 | month=7 | 0.359 | 51.49 | 1920 |
| conformal | 2 | month=8 | 0.542 | 49.47 | 1920 |
| conformal | 2 | month=9 | 0.420 | 46.24 | 960 |
| conformal | 4 | overall | 0.485 | 67.10 | 16320 |
| conformal | 4 | usdm=1 | 0.495 | 75.54 | 3430 |
| conformal | 4 | usdm=2 | 0.386 | 64.29 | 7217 |
| conformal | 4 | usdm=3 | 0.528 | 66.13 | 4383 |
| conformal | 4 | usdm=4 | 0.871 | 63.63 | 1290 |
| conformal | 4 | month=1 | 0.885 | 99.81 | 1920 |
| conformal | 4 | month=2 | 0.630 | 79.19 | 1920 |
| conformal | 4 | month=3 | 0.148 | 73.25 | 2400 |
| conformal | 4 | month=4 | 0.893 | 68.00 | 1920 |
| conformal | 4 | month=5 | 0.324 | 58.25 | 1920 |
| conformal | 4 | month=6 | 0.355 | 56.77 | 2400 |
| conformal | 4 | month=7 | 0.468 | 52.93 | 1920 |
| conformal | 4 | month=8 | 0.298 | 49.62 | 1920 |
| conformal | 4 | month=9 | nan | nan | 0 |
| conformal | 8 | overall | 0.538 | 67.22 | 14400 |
| conformal | 8 | usdm=1 | 0.637 | 75.66 | 3386 |
| conformal | 8 | usdm=2 | 0.519 | 65.71 | 6153 |
| conformal | 8 | usdm=3 | 0.520 | 64.89 | 3571 |
| conformal | 8 | usdm=4 | 0.422 | 58.70 | 1290 |
| conformal | 8 | month=1 | 0.919 | 101.96 | 1920 |
| conformal | 8 | month=2 | 0.704 | 79.55 | 1920 |
| conformal | 8 | month=3 | 0.726 | 69.29 | 2400 |
| conformal | 8 | month=4 | 0.371 | 58.81 | 1920 |
| conformal | 8 | month=5 | 0.197 | 57.63 | 1920 |
| conformal | 8 | month=6 | 0.491 | 55.07 | 2400 |
| conformal | 8 | month=7 | 0.326 | 50.73 | 1920 |
| conformal | 8 | month=8 | nan | nan | 0 |
| conformal | 8 | month=9 | nan | nan | 0 |
| bootstrap | 2 | overall | 0.967 | 106.70 | 17280 |
| bootstrap | 2 | usdm=1 | 0.995 | 106.75 | 3452 |
| bootstrap | 2 | usdm=2 | 0.954 | 106.71 | 7749 |
| bootstrap | 2 | usdm=3 | 0.959 | 106.67 | 4789 |
| bootstrap | 2 | usdm=4 | 0.998 | 106.64 | 1290 |
| bootstrap | 2 | month=1 | 1.000 | 106.79 | 1920 |
| bootstrap | 2 | month=2 | 1.000 | 106.78 | 1920 |
| bootstrap | 2 | month=3 | 0.938 | 106.63 | 2400 |
| bootstrap | 2 | month=4 | 0.997 | 106.63 | 1920 |
| bootstrap | 2 | month=5 | 1.000 | 106.60 | 1920 |
| bootstrap | 2 | month=6 | 0.998 | 106.62 | 2400 |
| bootstrap | 2 | month=7 | 0.941 | 106.81 | 1920 |
| bootstrap | 2 | month=8 | 0.919 | 106.76 | 1920 |
| bootstrap | 2 | month=9 | 0.851 | 106.80 | 960 |
| bootstrap | 4 | overall | 0.963 | 105.93 | 16320 |
| bootstrap | 4 | usdm=1 | 0.990 | 105.96 | 3430 |
| bootstrap | 4 | usdm=2 | 0.948 | 105.94 | 7217 |
| bootstrap | 4 | usdm=3 | 0.955 | 105.91 | 4383 |
| bootstrap | 4 | usdm=4 | 0.998 | 105.96 | 1290 |
| bootstrap | 4 | month=1 | 0.999 | 105.95 | 1920 |
| bootstrap | 4 | month=2 | 0.996 | 105.89 | 1920 |
| bootstrap | 4 | month=3 | 0.996 | 105.95 | 2400 |
| bootstrap | 4 | month=4 | 0.999 | 105.93 | 1920 |
| bootstrap | 4 | month=5 | 0.994 | 105.92 | 1920 |
| bootstrap | 4 | month=6 | 0.972 | 105.91 | 2400 |
| bootstrap | 4 | month=7 | 0.926 | 106.00 | 1920 |
| bootstrap | 4 | month=8 | 0.807 | 105.93 | 1920 |
| bootstrap | 4 | month=9 | nan | nan | 0 |
| bootstrap | 8 | overall | 0.948 | 106.30 | 14400 |
| bootstrap | 8 | usdm=1 | 0.962 | 106.24 | 3386 |
| bootstrap | 8 | usdm=2 | 0.922 | 106.33 | 6153 |
| bootstrap | 8 | usdm=3 | 0.963 | 106.26 | 3571 |
| bootstrap | 8 | usdm=4 | 1.000 | 106.39 | 1290 |
| bootstrap | 8 | month=1 | 0.984 | 106.25 | 1920 |
| bootstrap | 8 | month=2 | 0.991 | 106.28 | 1920 |
| bootstrap | 8 | month=3 | 0.998 | 106.37 | 2400 |
| bootstrap | 8 | month=4 | 1.000 | 106.36 | 1920 |
| bootstrap | 8 | month=5 | 0.983 | 106.27 | 1920 |
| bootstrap | 8 | month=6 | 0.944 | 106.29 | 2400 |
| bootstrap | 8 | month=7 | 0.725 | 106.24 | 1920 |
| bootstrap | 8 | month=8 | nan | nan | 0 |
| bootstrap | 8 | month=9 | nan | nan | 0 |

Numbers are empirical. If conformal holds 0.90 where bootstrap drops, that is the result; the reverse is also reportable.
