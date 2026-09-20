# COFIRE

Colorado Fire Intelligence and Risk Engine. 2026 Congressional App Challenge.

COFIRE forecasts **drought** and **conditions that allow fires to spread** across Colorado 2 to 8 weeks ahead at gridMET 4 km cells, **states how uncertain each forecast is, says when that uncertainty itself cannot be trusted**, and turns the result into a decision: predict (Beat the Model), observe (Observer Streaks), and harden (Ember Score).

It does **not** predict ignitions or where a fire will occur.

### What COFIRE claims, and what it does not

COFIRE does **not** claim better forecast skill than a persistence baseline. On the evaluated domain
and record, no trained arm improves on "next month looks like this month" at 4 or 8 weeks. That is
measured, reported in `artifacts/metrics.md` and `artifacts/lodo/lodo.md`, and not hidden.

What it does claim is an honest uncertainty layer: calibrated intervals where the record supports
them, an explicit **extrapolating** state where current conditions run past the calibration pool, and
an **uncalibrated** state where the interval is suppressed entirely rather than shown misleadingly.
Knowing when a forecast cannot be trusted is the product.

## Run

```bash
git clone <this-repo> && cd cofire
make setup   # uv sync + npm install
make demo    # offline: no API keys, no network, no pipeline run
```

Then open http://127.0.0.1:3000 (API on :8000).

`make demo` serves the committed fixture set in `demo/` (6.7 MB): one issue of Pueblo County
forecasts, the 2026 coverage series, the fires table with its matched non-fire control, the
multiregime and LODO results, and a feature slice for Place Cards. **Measured clone-to-running:
about 15 seconds** (npm install 4 s, API ready 2 s, web ready 5 s), verified from a directory
containing no `artifacts/` and no `data/`.

Regenerate the fixture after a pipeline run with `make demo-data`.

Then open http://127.0.0.1:3000 (API on :8000). The Larimer County vertical slice should finish on a laptop with network in under 45 minutes. Statewide is **staged and gated** (see `make statewide` for the plan and per-stage ETA); it is not
started while `STATUS.md` reads No-go.

Core pipeline needs **zero API keys**. Optional Earthdata / Synoptic keys are listed in `.env.example` and skipped when blank.

## What you get

- Map of drought / fire-spread condition rasters, time scrubber, Place Card with conformal sets and SHAP-derived Why bars
- Hindcast 2026 with a conformal-vs-bootstrap coverage plot
- Beat the Model, Observer Streaks, Ember Score against SQLite
- `artifacts/metrics.md`, PI-ConvLSTM ablation (no penalties / hydro / both)

Shipping resolution is **4 km**. 10–30 m HLS downscaling is off unless `COFIRE_ENABLE_HLS=1` and credentials work; the legend always prints the resolution actually displayed.

## Science notes

Models: LightGBM, a physics-informed ConvLSTM (`L_task + λ_hydro L_hydro + λ_fuel L_fuel`), and a validation-weighted ensemble. The API serves the arm that wins on validation.

Uncertainty: split conformal + ACI compared with a 300-draw residual bootstrap. See `artifacts/uncertainty/comparison.md`.

A 2020–2025 science-fair project (*Beyond the Forecast*) is **prior art by a different author**. It is cited in `docs/PRIOR_ART.md`. Nothing from it is copied. What is new here is the Colorado domain, fire-condition targets, a fuel-moisture constraint, conformal calibration, and this app.

Student-owned modules (rewrite these): `features.py`, `train.py`, `conformal.py`, `models/pi_convlstm.py`. Table: `AI_USAGE.md`.
