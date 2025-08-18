# Makefile for CORE – Cognitive Orchestration Runtime Engine

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ---- Configurable knobs -----------------------------------------------------
POETRY  ?= python3 -m poetry
PYTHON  ?= python3
APP     ?= src.core.main:app
HOST    ?= 0.0.0.0
PORT    ?= 8000
RELOAD  ?= --reload
ENV_FILE ?= .env
PATHS   ?= src tests

# Manifest migrator (File 4)
MIGRATOR := src/system/tools/manifest_migrator.py
# FAIL_ON_CONFLICTS=1 will make duplicate capabilities fail the run
FAIL_ON_CONFLICTS ?= 0
ifeq ($(FAIL_ON_CONFLICTS),1)
	MIGRATOR_CONFLICT_FLAG := --fail-on-conflicts
else
	MIGRATOR_CONFLICT_FLAG :=
endif

# Drift output format for guard UI: short | pretty
FORMAT ?= short

.PHONY: help install lock run stop audit lint format test coverage check fast-check clean distclean nuke context \
        drift migrate manifests-validate manifests-scaffold manifests-dups guard-check fix-docstrings

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "make install                 - Install deps with Poetry"
	@echo "make lock                    - Update poetry.lock"
	@echo "make run                     - Start uvicorn ($(APP)) on $(HOST):$(PORT)"
	@echo "make stop                    - Stop dev server reliably by killing process on port $(PORT)"
	@echo "make audit                   - Run the full self-audit (KnowledgeGraph + Auditor)"
	@echo "make lint                    - Check formatting and code quality with Black and Ruff."
	@echo "make format                  - Auto-format code with Black and Ruff."
	@echo "make test [ARGS=]            - Pytest (pass ARGS='-k expr -vv')"
	@echo "make coverage                - Pytest with coverage"
	@echo "make fast-check              - Run fast checks (lint, test)."
	@echo "make check                   - Run all checks (lint, test, audit)."
	@echo "make migrate [FAIL_ON_CONFLICTS=0|1]"
	@echo "                             - Run manifest migrator (scaffold+validate+dups)."
	@echo "make manifests-validate      - Validate all manifests against schema"
	@echo "make manifests-scaffold      - Create missing manifests with placeholders"
	@echo "make manifests-dups          - Show duplicate capabilities across domains"
	@echo "make drift [FORMAT=short]    - Generate drift evidence + show guard drift view"
	@echo "make guard-check             - Run import/dependency guard checks (if available)"
	@echo "make align GOAL=...          - Check goal ↔ NorthStar alignment via API"
	@echo "make context                 - Build the project context file for AI collaboration"
	@echo "make clean                   - Remove caches, pending_writes, sandbox"
	@echo "make distclean               - Clean + venv/build leftovers"
	@echo "make nuke                    - git clean -fdx (danger)"
	@echo
	@echo "Variables:"
	@echo "  FAIL_ON_CONFLICTS=0|1   (default 0)  Fail if duplicate capabilities exist"
	@echo "  FORMAT=short|pretty     (default short) Guard drift output style"
	@echo "  HOST, PORT, RELOAD, ENV_FILE  (server run options)"

install:
	@echo "📦 Installing dependencies..."
	$(POETRY) install

lock:
	@echo "🔒 Resolving and locking dependencies..."
	$(POETRY) lock

run:
	@echo "🚀 Starting FastAPI server at http://$(HOST):$(PORT)"
	PYTHONPATH=src $(POETRY) run uvicorn $(APP) --host $(HOST) --port $(PORT) $(RELOAD) --env-file $(ENV_FILE)

stop:
	@echo "🛑 Stopping any process on port $(PORT)..."
	@if command -v lsof >/dev/null 2>&1; then \
		PID=$$(lsof -t -i:$(PORT) || true); \
		if [ -n "$$PID" ]; then \
			echo "  -> Found process with PID: $$PID. Terminating..."; \
			kill $$PID || true; \
		else \
			echo "  -> No process found on port $(PORT)."; \
		fi; \
	else \
		echo "  -> 'lsof' not found. Trying 'pkill'. You might want to install 'lsof' for better reliability."; \
		pkill -f "uvicorn.*$(APP)" || true; \
	fi

audit:
	@echo "🧠 Running constitutional self-audit..."
	PYTHONPATH=src $(POETRY) run python -m core.capabilities

lint:
	@echo "🎨 Checking code style with Black and Ruff..."
	$(POETRY) run black --check $(PATHS)
	$(POETRY) run ruff check $(PATHS)

format:
	@echo "✨ Formatting code with Black and Ruff..."
	$(POETRY) run black $(PATHS)
	$(POETRY) run ruff check --fix $(PATHS)

test:
	@echo "🧪 Running tests with pytest..."
	$(POETRY) run pytest $(ARGS)

coverage:
	@echo "🧮 Running tests with coverage..."
	$(POETRY) run pytest --cov=src --cov-report=term-missing:skip-covered $(ARGS)

fast-check: lint test

check: fast-check audit

# ---- Governance helpers -----------------------------------------------------

# Generate drift evidence first (manifest validation + duplicate scan),
# then show the guard's drift view (reads reports/drift_report.json).
drift:
	@echo "🧭 Generating drift evidence (schema + duplicates)..."
	PYTHONPATH=src $(POETRY) run $(PYTHON) $(MIGRATOR) all $(MIGRATOR_CONFLICT_FLAG) || true
	@echo "📄 Displaying guard drift view ($(FORMAT))..."
	PYTHONPATH=src $(POETRY) run core-admin guard drift --format $(FORMAT)

# Run full migrator pipeline explicitly (scaffold + validate + dup check)
migrate:
	@echo "🛠  Running manifest migrator pipeline..."
	PYTHONPATH=src $(POETRY) run $(PYTHON) $(MIGRATOR) all $(MIGRATOR_CONFLICT_FLAG)

manifests-validate:
	@echo "✅ Validating manifests against schema..."
	PYTHONPATH=src $(POETRY) run $(PYTHON) $(MIGRATOR) validate

manifests-scaffold:
	@echo "🧱 Scaffolding missing manifests..."
	PYTHONPATH=src $(POETRY) run $(PYTHON) $(MIGRATOR) scaffold

manifests-dups:
	@echo "🔍 Checking for duplicate capabilities across domains..."
	PYTHONPATH=src $(POETRY) run $(PYTHON) $(MIGRATOR) check-duplicates $(MIGRATOR_CONFLICT_FLAG)

guard-check:
	@echo "🔒 Running import/dependency guard checks (if available)..."
	# If your core-admin has 'guard check', this will run it; otherwise, remove this target.
	PYTHONPATH=src $(POETRY) run core-admin guard check --all || { echo 'guard-check: command unavailable' ; exit 0; }

fix-docstrings:
	@echo "✍️  Using agent to fix missing docstrings..."
	@echo "   (This will use the Generator LLM and may take a moment)"
	PYTHONPATH=src $(POETRY) run core-admin fix docstrings --write

# Usage: make align GOAL='scaffold a governed starter from intent'
align:
	@test -n "$(GOAL)" || (echo 'GOAL is required. Example: make align GOAL="build a governed starter kit"'; exit 2)
	@echo "🔎 Checking goal↔NorthStar alignment via API..."
	@echo "   (ensure the API is running: make run)"
	@curl -s -X POST http://$(HOST):$(PORT)/guard/align \
	  -H 'Content-Type: application/json' \
	  -d '{"goal":"$(GOAL)"}' | (command -v jq >/dev/null 2>&1 && jq . || cat)

# ---- Clean targets ---------------------------------------------------------

clean:
	@echo "🧹 Cleaning up temporary files and caches..."
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .cache
	rm -f .coverage
	rm -rf htmlcov
	rm -rf build dist *.egg-info
	rm -rf pending_writes sandbox
	@echo "✅ Clean complete."

distclean: clean
	@echo "🧨 Distclean: removing virtual environments and build leftovers..."
	rm -rf .venv
	@echo "✅ Distclean complete."

nuke:
	@echo "☢️  Running 'git clean -fdx' in 3s (CTRL+C to cancel)..."
	@sleep 3
	git clean -fdx
	@echo "✅ Repo nuked (untracked files/dirs removed)."

# ---- Developer Tooling ------------------------------------------------------
context:
	@echo "📦 Building project context for AI collaboration..."
	@scripts/concat_project.sh
