# Prior art

A 2020–2025 science-fair project, *Beyond the Forecast*, trained a physics-informed ConvLSTM for frost and drought over Great Plains croplands. That work is **prior art by a different author**. Nothing from it — no code, weights, figures, data, or text — is copied into this repository.

It is cited here only as **published precedent** for two ideas:

1. A physics-informed loss that adds a domain constraint to a ConvLSTM task loss.
2. An anti-leakage protocol: statistics, scalers, and physical coefficients are fit on the training window only.

## What is new in COFIRE

| | Beyond the Forecast (precedent) | COFIRE (this repo) |
| --- | --- | --- |
| Domain | Great Plains croplands | Colorado, gridMET 4 km, Larimer slice first |
| Targets | Frost and drought | Drought (USDM ordinal) and **fire-spread conditions** (ERC percentile / fire-spread condition index) |
| Physical constraint | Thermodynamic frost constraint | **Fuel-moisture and PET-limited drying** constraints (`L_fuel`, `L_hydro`) |
| Uncertainty | Not the product | Split conformal + ACI, compared head-to-head with bootstrap |
| Delivery | Science-fair model | Public decision app: map, Beat the Model, Observer Streaks, Ember Score |

Every model here is implemented from scratch against Colorado inputs (gridMET, USDM, SNOTEL, 3DEP, NIFC). LightGBM, the ConvLSTM cell, the losses, conformal calibration, and the app are original to this repository.

COFIRE forecasts **conditions that allow fires to spread** and drought severity. It does not predict ignitions or where a fire will occur.
