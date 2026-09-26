# Correction to look 3: the interval results are void

Recorded 2026-09-26, after look 3. `docs/PREREGISTRATION_LOOK3.md` is left
exactly as hashed; this note sits beside it.

## What was wrong

Every PID and ACI run in this project, including Stage A, Stage B and the look-3
interval tests, streamed rows ordered by issue week and then cell, and called
the controller with `ahead=1`. Each row's interval was therefore adjusted by the
error of the row immediately before it: another cell in the same issue week,
whose outcome is not known until 2 to 8 weeks later. A real-time forecaster
cannot use that information. The 30 of 30 interval passes on 2026 rest on it and
are void as evidence.

The vendored controller's `ahead > 1` code path uses `np.infty`, removed in
NumPy 2, so the lagged path had never executed in this project.

## What the honest test shows

`cofire/ship/pid_audit.py`, on 2022 to 2025 only. 2026 was not read again:
look 3 is spent and a recomputation on it would be a fourth look.

As run (`ahead=1`):

| county | h | coverage | worst 13 weeks |
|---|---|---|---|
| larimer | 2 | 0.8985 | 0.8954 |
| larimer | 4 | 0.8987 | 0.8963 |
| larimer | 8 | 0.8991 | 0.8963 |
| pueblo | 2 | 0.8982 | 0.8944 |
| pueblo | 4 | 0.8978 | 0.8910 |
| pueblo | 8 | 0.8980 | 0.8917 |

With the real delay (`ahead = h weeks x cells per week`):

| county | h | coverage | worst 13 weeks |
|---|---|---|---|
| larimer | 2 | 0.9019 | 0.8162 |
| larimer | 4 | 0.9115 | 0.6407 |
| larimer | 8 | 0.9314 | 0.3115 |
| pueblo | 2 | 0.9123 | 0.8189 |
| pueblo | 4 | 0.9113 | 0.6460 |
| pueblo | 8 | 0.9063 | 0.2735 |

In real time the controller is unstable in every case: integrator windup under
delayed feedback, with radii between -1488 and
61758 on a 0 to 100 scale. Its coverage above
looks high partly because some radii are infinite.

The radius the export applied to every 2026 forecast was the leaky controller's
final state. Scored on 2024 to 2025:

| county | h | coverage | worst 13 weeks |
|---|---|---|---|
| larimer | 2 | 0.7170 | 0.5984 |
| larimer | 4 | 0.5902 | 0.2723 |
| larimer | 8 | 0.5814 | 0.2463 |
| pueblo | 2 | 0.4341 | 0.3123 |
| pueblo | 4 | 0.6015 | 0.4163 |
| pueblo | 8 | 0.4565 | 0.2691 |

Split conformal, a fixed 90th percentile of 2022 to 2023 errors scored on 2024
to 2025, is valid in real time but modest:

| county | h | coverage | worst 13 weeks |
|---|---|---|---|
| larimer | 2 | 0.8631 | 0.7675 |
| larimer | 4 | 0.8355 | 0.6221 |
| larimer | 8 | 0.8274 | 0.5362 |
| pueblo | 2 | 0.8687 | 0.7495 |
| pueblo | 4 | 0.9221 | 0.7894 |
| pueblo | 8 | 0.9271 | 0.8114 |

## Consequence

The pre-registration fixed the consequence of a failed interval test: the
horizon renders `uncalibrated`, with no band and the reason stated. An invalid
test cannot count as a pass, and the valid version fails, so that consequence
now applies to all six continuous horizons. No forecast band is drawn.

Unaffected: the probability forecasts, their look-3 reliability results (39 of
54 pass), and the 12 stage-1 skill survivors, none of which use the interval
controller.

Restoring a forecast band needs a method that is valid with the real delay,
evaluated under a new pre-registration.
