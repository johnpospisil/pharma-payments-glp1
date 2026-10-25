# Pharma payments and GLP-1 prescribing: pipeline entry points.
# Paths: override with PPG_RAW_DIR / PPG_DATA_DIR (see src/ppg/config.py and .env).
# Targets are filled in as the prompts in CLAUDE.md are run.

PY := uv run python -I

# Ignore any other active virtualenv (e.g. ~/tf): uv always uses this project's .venv.
unexport VIRTUAL_ENV

.PHONY: all check-env check-env-local data build models figures report app serve-app release qa test lint test-fast progress data-open-payments data-partd data-reference

# On macOS the ~2 h rebuild runs under caffeinate -s so the machine can't sleep mid-run (D39)
CAFFEINATE := $(shell command -v caffeinate >/dev/null 2>&1 && echo "caffeinate -s -i")

all:
ifeq ($(PPG_AWAKE),)
	PPG_AWAKE=1 $(CAFFEINATE) $(MAKE) all
else
all: check-env data build models figures report app release qa
endif

check-env:
	$(PY) -m ppg.check_env

# Same checks without requiring Drive3 (everything after ingest).
check-env-local:
	$(PY) -m ppg.check_env --no-raw

data: check-env data-open-payments data-partd data-reference

build:
	$(PY) -m ppg.ingest.quality
	$(PY) -m ppg.build.drug_map
	$(PY) -m ppg.build.linkage
	$(PY) -m ppg.build.payments
	$(PY) -m ppg.build.panel

models:
	$(PY) -m ppg.models.event_study all
	$(PY) -m ppg.models.event_study diagnostics
	$(PY) -m ppg.models.event_study report
	$(PY) -m ppg.models.cs_panel all
	$(PY) -m ppg.models.cs_panel validate
	for b in Trulicity Victoza Ozempic; do /opt/homebrew/bin/Rscript src/ppg/models/r/honest.R \
	  report/qa/es/panel_universal_$$b.json report/qa/es/honest_panel_$$b.json; done
	$(PY) -m ppg.models.matched all
	$(PY) -m ppg.models.matched report
	$(PY) -m ppg.models.switching all
	$(PY) -m ppg.models.switching report
	$(PY) -m ppg.models.dose_response all
	$(PY) -m ppg.models.dose_response pretrends
	$(PY) -m ppg.models.dose_response report
	$(PY) -m ppg.models.falsification all
	$(PY) -m ppg.models.falsification report
	$(PY) -m ppg.models.sensitivity all
	$(PY) -m ppg.models.sensitivity report
	$(PY) -m ppg.models.matched report
	$(PY) -m ppg.models.heterogeneity all
	$(PY) -m ppg.models.heterogeneity report

figures:
	$(PY) -m ppg.viz.figures
	$(PY) -m ppg.viz.final

# P22: article numbers from report/qa -> report/_variables.yml, then render to report/_site
report:
	$(PY) -m ppg.report.vars > /dev/null
	cd report && quarto render

# P23: specialty x state explorer data (disclosure-controlled) -> app/data; serve with `make serve-app`
app:
	$(PY) -m ppg.app.build > /dev/null

# P25: released datasets (drug-name map; the explorer cube as one table) -> release/
release:
	$(PY) -m ppg.release.build > /dev/null

serve-app:
	@echo "explorer: http://localhost:8766/app/"
	$(PY) -m http.server 8766 --directory .

# P20: article claims vs report/qa, and the disclosure audit of everything public
qa:
	$(PY) -m ppg.qa.claims
	$(PY) -m ppg.qa.disclosure > /dev/null
	@$(PY) -c "import json; d = json.load(open('report/qa/disclosure_audit.json')); print('disclosure audit:', 'PASS' if d['pass'] else 'FAIL'); raise SystemExit(0 if d['pass'] else 1)"

test:
	uv run pytest -q

# Unit tests only (skip checks on the real data, ~1 min)
test-fast:
	uv run pytest -q -m "not data"

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

# Live progress of running jobs (any terminal). WATCH=1 refreshes every 2 s; JOB=<name> filters.
progress:
	@$(PY) -m ppg.progress $(JOB) $(if $(WATCH),--watch,)

# P03: Open Payments download -> Parquet -> reconciliation and summary
data-open-payments: check-env
	$(PY) -m ppg.ingest.open_payments all
	$(PY) -m ppg.ingest.op_reconcile
	$(PY) -m ppg.ingest.op_summary

# P04: Part D (+ Part B by Provider) download -> Parquet -> suppression QA
data-partd: check-env
	$(PY) -m ppg.ingest.partd all
	$(PY) -m ppg.ingest.partd_qa

# P05: reference data (practices, taxonomy, diabetes prevalence, enrollment) + derived tables
data-reference: check-env
	$(PY) -m ppg.ingest.reference
	$(PY) -m ppg.build.specialty
	$(PY) -m ppg.build.denominators
