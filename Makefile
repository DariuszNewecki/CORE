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

.PHONY: help install lock run stop audit lint format test coverage check fast-check clean clean-logs distclean nuke context drift align

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "make install       - Install deps with Poetry"
	@echo "make lock          - Update poetry.lock"
	@echo "make run           - Start uvicorn ($(APP)) on $(HOST):$(PORT)"
	@echo "make stop          - Stop dev server reliably by killing process on port $(PORT)"
	@echo "make audit         - Run the full self-audit (KnowledgeGraph + Auditor)"
	@echo "make lint          - Check formatting and code quality with Black and Ruff."
	@echo "make format        - Auto-format code with Black and Ruff."
	@echo "make test [ARGS=]  - Pytest (pass ARGS='-k expr -vv')"
	@echo "make coverage      - Pytest with coverage"
	@echo "make fast-check    - Run fast checks (lint, test). Use before committing minor changes."
	@echo "make check         - Run all checks (lint, test, audit). Use before submitting a PR."
	@echo "make drift         - Run capability drift check (short JSON)"
	@echo "make align GOAL=   - Check goal ↔ NorthStar alignment via API"
	@echo "make context       - Build the project context file for AI collaboration"
	@echo "make clean         - Remove caches, pending_writes, sandbox"
	@echo "make distclean     - Clean + venv/build leftovers"
	@echo "make nuke          - git clean -fdx (danger)"

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

# ---- Governance helpers -----------------------------------------------------

drift:
	@echo "🧭 Running capability drift check (short JSON)..."
	PYTHONPATH=src $(POETRY) run core-admin guard drift --format short

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
