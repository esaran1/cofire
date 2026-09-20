# External drought model slot

`ExternalDroughtModel` (`cofire/model/models/external.py`) loads an optional NetCDF of drought predictions on the same grid and issue dates as COFIRE. It is **optional infrastructure**, not the shipping model. When the file is absent, the pipeline runs unchanged.

When present it can be used as:

1. An extra feature column `external_drought` on each cell-week (value as of issue date).
2. An optional ensemble member for the drought target at horizons 2, 4, and 8 weeks.

It never trains, and it is never treated as a fire-condition forecast.

## Expected file

Default path: `data/external/drought_pred.nc` (override with `COFIRE_EXTERNAL_DROUGHT_NC`).

```
dimensions:
  time  - weekly issue dates (USDM Tuesdays), datetime64[ns]
  lat   - gridMET latitudes, north-to-south
  lon   - gridMET longitudes
variables:
  drought_h2 (time, lat, lon) float32   # ordinal 0–4 issued at `time`, valid t+2 weeks
  drought_h4 (time, lat, lon) float32
  drought_h8 (time, lat, lon) float32
optional:
  drought_now (time, lat, lon) float32  # category at issue time; used only as a feature
attributes:
  long_name = "external drought category 0-4 (None/D0=0 … D4=4)"
  grid_mapping = WGS84
```

Lat/lon must match the COFIRE grid to 1e-4 degrees. Dates that do not match an issue Tuesday are ignored, not interpolated. Missing cells are NaN and drop out of the ensemble weight for that cell.

A file with only `drought_now` is accepted as a feature source; it does not participate in the ensemble.
