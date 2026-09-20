.PHONY: setup data train calibrate hindcast export serve web demo test lint score

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

train:
	$(PY) -m cofire.model.train

calibrate:
	$(PY) -m cofire.model.calibrate

hindcast:
	$(PY) -m cofire.model.hindcast

export:
	$(PY) -m cofire.model.export

serve:
	$(UV) run uvicorn cofire.api.main:app --host $(API_HOST) --port $(API_PORT)

web:
	cd app && npm run dev -- --port 3000

score:
	$(PY) -m cofire.api.score

demo: setup
	$(MAKE) data train calibrate hindcast export
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
