# COFIRE v0.2 plan

v0 scaffold (data sources + `features.py`) is in the repo. v0.2 finishes the Larimer vertical slice and adds a second model arm, a conformal-vs-bootstrap comparison, and SHAP-derived Why bars.

## Dependency graph

```
[v0 data + features] already on disk
    │
    ├─► [M] ConditionModel interface
    │     LightGBMConditionModel ─────────────────────┐
    │     PhysicsInformedConvLSTM (3 λ configs) ──────┤
    │     ExternalDroughtModel (optional NetCDF) ─────┤
    │     validation-weighted ensemble ───────────────┘
    │                       │
    │                       ▼
    ├─► [T] make train → metrics.json/md, ablation table, shipping arm
    │                       │
    │           ┌───────────┴───────────┐
    │           ▼                       ▼
    ├─► [C] conformal (ACI)     [B] residual bootstrap (300)
    │           └───────────┬───────────┘
    │                       ▼
    ├─► [U] artifacts/uncertainty/comparison.md + coverage-over-2026 plot
    │                       │
    ├─► [S] TreeSHAP on LightGBM → grouped Why bars (feature_groups.yaml)
    │                       │
    ├─► [H] hindcast 2026 + NIFC overlay + cutoff assert
    │                       │
    ├─► [E] COG/JSON export (4 km; HLS flag off)
    │                       │
    ├─► [A] FastAPI + Next.js (map, Place Card SHAP, hindcast plot, Beat, Observe, Ember, About)
    │
    └─► [X] tests: PI shapes/overfit/penalties, bootstrap coverage,
            SHAP exhaustive mapping, copy lint, leakage, cutoff, API fixture
```

## Slice order

| Slice | Deliverable | Verify |
| --- | --- | --- |
| P | PLAN, PRIOR_ART, EXTERNAL_MODEL, DECISIONS, AI_USAGE | files exist |
| M | `models/` + PI-ConvLSTM tests | `pytest tests/test_pi_convlstm.py` |
| T | train three arms + ablation | `pytest tests/test_train_metrics.py` (synthetic) |
| U | conformal + bootstrap comparison | `pytest tests/test_conformal.py tests/test_bootstrap.py` |
| S | SHAP grouping + templates | `pytest tests/test_shap_groups.py` |
| H | hindcast cutoff + export | `pytest tests/test_hindcast.py` |
| A | API + Next.js + copy lint | `pytest tests/test_api.py`; `python scripts/check_copy.py`; Playwright |
| D | `make lint` / `make test` | both green without network |

Larimer CPU budget: PI-ConvLSTM < 30 min; full `make train` subset < 45 min.

Data fetch uses the Climatology Lab file server with bbox clip (THREDDS NCSS was unreachable). USDM yearly zips contain nested weekly zips.

## Shipping rule

The forecast the API serves is the arm with the best validation skill (ERC MAE, then drought MAE). The About screen and `metrics.md` name it. Ensemble is reported even if it does not win.
