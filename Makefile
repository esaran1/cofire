.PHONY: refresh static setup data sanity train calibrate hindcast export pipeline serve web demo test lint score lodo statewide statewide-run multiregime subsets demo-data facts tiles

export COFIRE_DEV_SUBSET ?= 1
UV ?= uv
# Local runs use Python 3.11, as CI does (there is no .python-version file:
# Vercel's Python build offers 3.12 only and uv would refuse a 3.11 pin there).
export UV_PYTHON ?= 3.11
PY := $(UV) run python
API_HOST ?= 127.0.0.1
API_PORT ?= 8000

setup:
	$(UV) sync --extra dev --extra pipeline
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

# The shipped path: frozen configuration -> export -> rendering -> bundles.
# cofire/model/ is frozen at FREEZE_COMMIT; everything here reads it.
ship:
	$(PY) -m research.audits.pid_audit
	$(PY) -m cofire.ship.rendering
	$(PY) -m cofire.ship.export
	$(PY) -m cofire.ship.bundles
	$(PY) -m cofire.ship.facts
	$(PY) -m cofire.ship.demo
	$(PY) -m cofire.ship.story

# Weekly refresh: newest USDM map and ERC days, frozen path, scoring nothing.
refresh:
	$(PY) -m cofire.ship.runner refresh -- $(PY) -m cofire.ship.refresh

# Static site for GitHub Pages, into app/out.
static:
	./scripts/build_static.sh

pipeline:
	$(PY) -m cofire.model.pipeline

# Leave-one-drought-year-out: free in-sample shift test. Never touches 2026.
lodo:
	$(PY) -m cofire.model.lodo

# Freeze the committed demo fixture set (under 200 MB) so `make demo` runs the
# full app offline from a clean clone, with real numbers and no pipeline run.
demo-data:
	$(PY) -m cofire.ship.demo

# Regenerate the landing page's figures from artifacts. Never hand-edit facts.json.
facts:
	$(PY) -m cofire.ship.facts

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

# `next build` and `next dev` share .next and write incompatible layouts into
# it. Building while the dev server is running leaves the dev server serving a
# manifest whose chunks do not exist, so every route 404s on its CSS and JS and
# the site loads unstyled and dead. Clearing .next on dev start makes that
# failure impossible rather than merely unlikely.
web:
	cd app && rm -rf .next && npm run dev -- --port 3000

# Production build, in its own directory, so it cannot clobber the dev server.
web-build:
	cd app && rm -rf .next && npx next build

score:
	$(PY) -m cofire.api.score

# Offline demo: no pipeline run, no API keys, no network. Serves the committed
# fixture set in demo/. Run `make demo-data` first if demo/ is absent.
demo: setup
	@echo "Starting API on http://$(API_HOST):$(API_PORT) and web on http://127.0.0.1:3000"
	@echo "Wording: COFIRE forecasts conditions that allow fires to spread, not ignitions."
	COFIRE_DEMO=1 $(UV) run uvicorn cofire.api.main:app --host $(API_HOST) --port $(API_PORT) & \
	cd app && npm run dev -- --port 3000

# torch and LightGBM must not share a process on macOS: mixing their OpenMP
# runtimes segfaults the interpreter mid-suite. Run the torch tests in their
# own process. See DECISIONS.md.
test:
	OMP_NUM_THREADS=1 $(PY) -m pytest --ignore=tests/test_pi_convlstm.py
	OMP_NUM_THREADS=1 $(PY) -m pytest tests/test_pi_convlstm.py
	cd app && npx tsc --noEmit

lint:
	$(UV) run ruff check cofire research tests scripts
	$(UV) run mypy --strict cofire/model cofire/ship cofire/v12 cofire/v13 cofire/api research
	$(PY) scripts/check_copy.py
	$(PY) scripts/check_stats.py
