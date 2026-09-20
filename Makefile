.PHONY: setup data sanity train calibrate hindcast export pipeline serve web demo test lint score lodo statewide statewide-run multiregime subsets demo-data facts tiles

export COFIRE_DEV_SUBSET ?= 1
UV ?= uv
PY := $(UV) run python
API_HOST ?= 127.0.0.1
API_PORT ?= 8000

setup:
	$(UV) sync --extra dev
	cd app && npm install

data:
	$(PY) -m cofire.model.data.run

sanity:
	$(PY) -m cofire.model.sanity

train:
	$(PY) -m cofire.model.train

calibrate:
	$(PY) -m cofire.model.calibrate

hindcast:
	$(PY) -m cofire.model.hindcast

export:
	$(PY) -m cofire.model.export

pipeline:
	$(PY) -m cofire.model.pipeline

# Leave-one-drought-year-out: free in-sample shift test. Never touches 2026.
lodo:
	$(PY) -m cofire.model.lodo

# Freeze the committed demo fixture set (under 200 MB) so `make demo` runs the
# full app offline from a clean clone, with real numbers and no pipeline run.
demo-data:
	$(PY) -m cofire.model.demo_data

# Regenerate the landing page's figures from artifacts. Never hand-edit facts.json.
facts:
	$(PY) -m cofire.model.site_facts

# Build the keyless self-hosted basemap extract (deployed builds).
tiles:
	bash scripts/fetch_tiles.sh

# Pre-registered multi-regime calibration experiment (LODO only; never 2026).
multiregime:
	$(PY) -m cofire.model.uncertainty.run_multiregime

# Run LODO + multiregime on BOTH dev subsets so a domain change is never
# confounded with a method change.
subsets:
	COFIRE_SUBSET_NAME=larimer $(PY) -m cofire.model.uncertainty.run_multiregime
	COFIRE_SUBSET_NAME=pueblo  $(PY) -m cofire.model.uncertainty.run_multiregime

# Statewide PLAN only (dry run): per-stage ETA + stop-rule check. Runs nothing.
statewide:
	$(PY) -m cofire.model.statewide

# Actually run statewide, staged and resumable. Gated on an explicit override
# of the No-go verdict -- do not run while STATUS.md says No-go.
statewide-run:
	@head -1 STATUS.md
	@echo "Statewide needs an explicit override of the verdict above."
	@echo "If you mean it: $(PY) -m cofire.model.statewide --run"


serve:
	$(UV) run uvicorn cofire.api.main:app --host $(API_HOST) --port $(API_PORT)

web:
	cd app && npm run dev -- --port 3000

score:
	$(PY) -m cofire.api.score

# Offline demo: no pipeline run, no API keys, no network. Serves the committed
# fixture set in demo/. Run `make demo-data` first if demo/ is absent.
demo: setup
	@echo "Starting API on http://$(API_HOST):$(API_PORT) and web on http://127.0.0.1:3000"
	@echo "Wording: COFIRE forecasts conditions that allow fires to spread, not ignitions."
	$(UV) run uvicorn cofire.api.main:app --host $(API_HOST) --port $(API_PORT) & \
	cd app && npm run dev -- --port 3000

test:
	$(PY) -m pytest
	cd app && npx tsc --noEmit

lint:
	$(UV) run ruff check cofire tests scripts
	$(UV) run mypy --strict cofire/model
	$(PY) scripts/check_copy.py
