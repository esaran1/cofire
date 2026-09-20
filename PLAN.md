# COFIRE v0.3 plan

v0.2 code is in the repo; no model has been trained. v0.3 produces real Larimer numbers, sanity-gates them, and writes an honest go/no-go.

Hindcast 2026 is a locked holdout. Hyperparameters freeze on 2022–2023 validation (Larimer: 2023). Hindcast is scored once per frozen config. A bad hindcast is reported, not patched. Any later change is logged as **post-hindcast change**.

## Dependency graph

```
[Larimer cubes on disk]
    │
    ▼
[G] sanity gates (labels, grid, leakage, shuffle, baselines, n_eff)
    │  fail → fix pipeline, do not train
    ▼
[T] make train (val metrics only; freeze shipping arm)
    │
    ▼
[C] make calibrate (conformal + bootstrap on 2024–2025)
    │
    ▼
[H] make hindcast  ← first and only look at 2026 per config
    │  run_log.json appends git SHA + config hash + timestamp
    ▼
[E] make export
    │
    ▼
[R] metrics.md + comparison.md + fires.md + STATUS.md
    │
    ├─ Go/Partial → wire UI; start statewide in background
    └─ No-go → stop; name the diagnostic
```

## Slice order

| Slice | Deliverable | Verify |
| --- | --- | --- |
| P | This plan + DECISIONS + AI_USAGE | files |
| G | `make sanity` → `artifacts/sanity.md` | all gates pass or pipeline fix |
| T | `make train` + `artifacts/runtime.json` | val metrics only |
| C | `make calibrate` | comparison.json, no hindcast retune |
| H | `make hindcast` | run_log.json, fires.md with control |
| E | `make export` | forecast_index.json |
| R | STATUS.md | Go / Partial / No-go |

Stop any stage that exceeds 60 minutes on CPU; profile instead of continuing.

## What is not allowed

- Tuning λ, LightGBM leaves, or conformal α after seeing 2026 numbers
- Writing "Go" to be agreeable
- Comparing to products not actually benchmarked
- Presenting cell-weeks as independent samples

## v0.3 follow-up (post-verdict)

STATUS came back **No-go**. That gates two of the four follow-up items.

| Item | State | Why |
| --- | --- | --- |
| Statewide run + `logs/statewide.log` + per-stage resume | **Blocked** | Rule: statewide only on Go or Partial. No arm beats persistence on 2026. Needs an explicit override. |
| `make demo-data` freeze (< 200 MB) | **Blocked by statewide** | Spec says "once statewide finishes". Freezing Larimer No-go weights would ship a judge-facing fixture whose numbers lose to persistence. |
| Wire real artifacts into the app | **Done** | Hindcast reads coverage + fires from disk; About reads MANIFEST hash + shipping arm; legend prints resolution + issue date. |
| Name the cheapest diagnostic | **Done** (STATUS.md) | 2026 predicted-vs-actual USDM histogram; scoring-only, no new look. |

If the No-go is overridden, statewide needs the harness before it starts, not after: append-only `logs/statewide.log`, a per-stage checkpoint file so an interrupted run resumes at the last completed stage, and an ETA extrapolated from the Larimer wall times in `artifacts/runtime.json` (train 745.67 s on 480 cells).

**Statewide ETA.** The buffered Colorado bbox at 4 km is ~24,000 cells against Larimer's 480 — a **50x** scale-up (the same cell-count model predicts 491 for Larimer, so the ratio is sound). Linear extrapolation:

| stage | Larimer | statewide (linear) |
| --- | --- | --- |
| sanity | 10.3 s | ~9 min |
| train | 745.67 s | **~10.4 h** |
| calibrate | 6.17 s | ~5 min |
| hindcast | 12.28 s | ~10 min |
| export | 30.72 s | ~26 min |
| **total** | ~13 min | **~11.2 h** |

Train alone is ~10x over the 60-minute stop rule, and linear is the optimistic case — LightGBM is pinned to one thread and the ConvLSTM grid grows superlinearly in memory. So statewide is not a "kick it off in the background" job on this machine: it needs profiling and stage-splitting first, and the 60-minute rule says to stop and profile rather than let it run. This is a second, independent reason the statewide request is deferred, on top of the No-go.
