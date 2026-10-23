# Pharma payments and GLP-1 prescribing: pipeline entry points.
# Paths: override with PPG_RAW_DIR / PPG_DATA_DIR (see src/ppg/config.py and .env).
# Targets are filled in as the prompts in CLAUDE.md are run.

PY := uv run python -I

# Ignore any other active virtualenv (e.g. ~/tf): uv always uses this project's .venv.
unexport VIRTUAL_ENV

.PHONY: all check-env check-env-local data build models figures report app test lint

all: check-env data build models figures report app

check-env:
	$(PY) -m ppg.check_env

# Same checks without requiring Drive3 (everything after ingest).
check-env-local:
	$(PY) -m ppg.check_env --no-raw

data: check-env
	@echo "data: added in P03 (Open Payments), P04 (Part D), P05 (NPPES + reference)"

build:
	@echo "build: added in P07-P10"

models:
	@echo "models: added in P13-P19"

figures:
	@echo "figures: added in P11 and P21"

report:
	@echo "report: added in P22"

app:
	@echo "app: added in P23"

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
