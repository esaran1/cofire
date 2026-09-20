# COFIRE

Colorado Fire Intelligence and Risk Engine. 2026 Congressional App Challenge.

COFIRE forecasts **drought** and **conditions that allow fires to spread** across Colorado 2 to 8 weeks ahead at gridMET 4 km cells, with calibrated uncertainty, and turns the forecast into three actions: predict (Beat the Model), observe (Observer Streaks), and harden (Ember Score).

It does **not** predict ignitions or where a fire will occur.

## Run

```bash
git clone <this-repo> && cd cofire
make setup          # uv + npm
COFIRE_DEV_SUBSET=1 make demo
```

Then open http://127.0.0.1:3000 (API on :8000). The Larimer County vertical slice should finish on a laptop with network in under 45 minutes. Statewide overnight:

```bash
COFIRE_DEV_SUBSET=0 make data train calibrate hindcast
```

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
