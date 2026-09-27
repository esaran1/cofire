# COFIRE

Colorado Fire Intelligence and Risk Engine. 2026 Congressional App Challenge.

COFIRE forecasts **drought** and **conditions that allow fires to spread** 2 to 8 weeks ahead at gridMET 4 km cells, for five areas: the **City and County of Denver** (all of CO-01, Glendale and Holly Hills enclaves included), the two watersheds Denver Water collects from (the **Upper South Platte above Strontia Springs** and the **Blue River above Dillon**), and **Larimer** and **Pueblo** counties. It says which numbers it can stand behind, and turns the result into a decision: predict (Beat the Model), observe (Observer Streaks), and prepare (the Urban Ember Score for Denver, the wildland-edge Ember Score elsewhere).

It does **not** predict ignitions or where a fire will occur.

### What COFIRE claims, and what it does not

- **Skill** is claimed for 22 of 115 target and area pairs, the ones that beat their baseline after multiplicity control across all five areas and a shuffled-target check, with training labels kept out of the evaluation period. Nowhere else. 12 are in Larimer and Pueblo and 10 in Denver and its watersheds. One of the 12, Pueblo drought reaching D2 in 4 weeks, was withdrawn by the leak-free refit and restored when a missing drought map (2022-12-27) was fixed; see [`docs/LEAK_SWEEP.md`](docs/LEAK_SWEEP.md) and `STATUS.md`. No target holds in every area where it can be tested, so every claim is for its own area only.
- **Probabilities** for Larimer and Pueblo were tested once on the sealed 2026 year against pre-registered criteria: 39 of 54 passed reliability. Denver and its watersheds were added after the seal and are never scored on 2026; their probabilities were checked on 2022 to 2023 with the same threshold. Where a target failed or could not be checked, the app shows the area's historical rate for that time of year instead of a per-cell number, and says why.
- **Forecast ranges are not shown.** The pre-registered interval tests passed, but the test was flawed: it updated each forecast with outcomes from the same week, which a real forecast would not know for 2 to 8 weeks. Run with the real delay, the method is unstable. The results are void and the app draws no band. See [`docs/CORRECTION_LOOK3.md`](docs/CORRECTION_LOOK3.md), beside the unedited [`docs/PREREGISTRATION_LOOK3.md`](docs/PREREGISTRATION_LOOK3.md), and the follow-up sweep for the same class of fault in [`docs/LEAK_SWEEP.md`](docs/LEAK_SWEEP.md).

## Run

```bash
git clone <this-repo> && cd cofire
make setup   # uv sync + npm install
make demo    # offline: no API keys, no network, no pipeline run
```

Then open http://127.0.0.1:3000 (API on :8000).

`make demo` serves the committed fixture set in `demo/`: two issues of forecasts for all five
areas as per-domain bundles, and the look-3 and survivor tables the Hindcast and Method screens
read. **Measured clone-to-running: 26 seconds** on 2026-09-27 with warm uv and npm caches (`make setup` 4 s, both servers answering 22 s later), from a fresh clone with no `data/`; every route then passed for every area (Playwright, 54 tests).

Regenerate the fixture after a pipeline run with `make demo-data`.

Then open http://127.0.0.1:3000 (API on :8000). The Larimer County vertical slice should finish on a laptop with network in under 45 minutes. Statewide is **staged and gated** (see `make statewide` for the plan and per-stage ETA); it is not
started while `STATUS.md` reads No-go.

Core pipeline needs **zero API keys**. Optional Earthdata / Synoptic keys are listed in `.env.example` and skipped when blank.

## What you get

- Map of forecast cells and a Place Card per cell: point forecast, per-cell probabilities where they held up, and the county rate where they did not
- Hindcast: the look-3 results against each pre-registered criterion, with the interval correction first
- Beat the Model, Observer Streaks, Ember Score against SQLite
- `artifacts/metrics.md`, PI-ConvLSTM ablation (no penalties / hydro / both)

Shipping resolution is **4 km**. 10–30 m HLS downscaling is off unless `COFIRE_ENABLE_HLS=1` and credentials work; the legend always prints the resolution actually displayed.

## Science notes

What ships: a Markov transition model for drought targets, a damped-persistence logistic for fire-spread exceedances, and a damped regression for the continuous ERC percentile, all fit on 2007 to 2021 and frozen at `FREEZE_COMMIT`. On this record they beat every trained arm tried (LightGBM, a physics-informed ConvLSTM, an ensemble), so the trained arms do not ship.

Uncertainty: no forecast band is drawn; see the correction above. Any method that updates as outcomes arrive must pass the delayed-feedback gate in `tests/test_delayed_feedback_gate.py`, which checks that no update uses an observation unavailable at issue time.

A 2020–2025 science-fair project (*Beyond the Forecast*) is **prior art by a different author**. It is cited in `docs/PRIOR_ART.md`. Nothing from it is copied. What is new here is the Colorado domain, fire-condition targets, a fuel-moisture constraint, conformal calibration, and this app.

Student-owned modules (rewrite these): `features.py`, `train.py`, `conformal.py`, `models/pi_convlstm.py`. Table: `AI_USAGE.md`.
