# research/: what was tried and does not ship

Nothing in this directory runs in the deployed product. The weekly refresh,
the API, the export, the site build, the open data and the facts the app
shows never import it. `tests/test_shipped_path.py` checks this two ways: by
reading every import under `cofire/`, and by loading every shipped entry
point and confirming no `research` module was loaded.

The code is kept, typed and tested, so a reviewer can rerun every experiment
behind a decision the app reports. The results it produced are committed
under `artifacts/` and shown in the app where they matter, for example the
v1.2 results on the Method page. The code that produced them is not part of
the product.

## v12/: the v1.2 upgrade arms

All four stages ran under `docs/PREREGISTRATION_V12.md`, committed before any
of them. Each arm had to beat configuration A under the paired test and pass
the adoption rule.

| Module | Arm | Why it does not ship |
|---|---|---|
| `stage1.py`, `gate.py`, `preds.py`, `evaluate.py` | Recalibration of configuration A: static and online, intercept and slope | The runner and its scoring do not ship. The one pair that qualified (Larimer, drought easing at 4 weeks, static intercept and slope) ships through `cofire/v12/live.py` and `cofire/v12/recal.py`, which are on the shipped path. Online arms cannot ship before the unseal, because they would update on 2026 outcomes. |
| `stage2.py`, `snotel.py` | A climate level from SNOTEL snowpack | Worse than configuration A (pooled mean Brier 0.1179 against 0.0962). None adopted. |
| `stage3.py` | Pooling across domains | Drought Brier improved (0.0853 against 0.0885), but no pair survived the multiple-testing correction. None adopted. |
| `stage4.py` | Lag-aware forecast intervals (conformal PID with the real delay) | 0 of 15 domain-horizon pairs passed (every one failed the longest-miss-run criterion), so no band is drawn. |

Run any of them with `uv run python -m research.v12.stage1 run` (and so on).
The stage runners refuse to run if the look counter has moved.

## audits/: one-off diagnostics and records

| Module | What it is | Why it does not ship |
|---|---|---|
| `sensitivity.py` | Refits the stage 1 survivor test outside the frozen tree, with the leaks found by the sweep removed (`docs/LEAK_SWEEP.md`) | A diagnostic: it decided which claims survive. It changes no forecast. |
| `pid_audit.py` | Re-runs the shipped intervals with the honest delay | Its result (`artifacts/audit/pid_realtime.json`) is why the app draws no band. The audit itself does not run in the product. |
| `gridmet_reach.py` | Measures how far back gridMET revises its current year | It decided the provisional window recorded in `docs/DECISIONS.md`. |
| `vintage_migration.py` | The one-time move from overwritten files to vintages (2026-09-27) | Kept as the record of what was done. |

## What is not here, and why

`cofire/model/` also holds arms that do not ship, among them the LightGBM
arm, the physics-informed ConvLSTM, the ensemble, the SubX forecast-weather
arm and the ablations. They stay where they are, because `cofire/model/` is frozen at
the preregistered commit:
- any change to a file there would change the configuration hash;
- the frozen-model test (`tests/test_frozen_model.py`) would then fail, as
  it should.

The shipped configuration inside it:
- the Markov transition baseline for every drought target;
- the damped-persistence logistic for every fire target;
- damped regression for the continuous dryness forecast.

`app/lib/facts.json` (`configuration`) and the README's architecture
diagram show which parts ship.
