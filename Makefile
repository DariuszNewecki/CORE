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
PATHS   ?= .

.PHONY: help install lock run stop audit lint format test coverage check clean clean-logs distclean nuke

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "make install       - Install deps with Poetry"
	@echo "make lock          - Update poetry.lock"
	@echo "make run           - Start uvicorn ($(APP)) on $(HOST):$(PORT)"
	@echo "make stop          - Stop dev server reliably by killing process on port $(PORT)"
	@echo "make audit         - Run the full self-audit (KnowledgeGraph + Auditor)"
	@echo "make lint          - Ruff checks"
	@echo "make format        - Black + Ruff --fix"
	@echo "make test [ARGS=]  - Pytest (pass ARGS='-k expr -vv')"
	@echo "make coverage      - Pytest with coverage"
	@echo "make check         - Lint + Tests + Audit"
	@echo "make clean         - Remove caches, pending_writes, sandbox"
	@echo "make distclean     - Clean + venv/build leftovers"
	@echo "make nuke          - git clean -fdx (danger)"

install:
	@echo "📦 Installing dependencies..."
	$(POETRY) install

lock:
	@echo "🔒 Resolving and locking dependencies..."
	$(POETRY) lock

# Ensure we stop before run
run: stop
	@echo "🚀 Starting FastAPI server at http://$(HOST):$(PORT)"
	$(POETRY) run uvicorn $(APP) --host $(HOST) --port $(PORT) $(RELOAD) --env-file $(ENV_FILE)

# --- THIS IS THE IMPROVED VERSION ---
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
	$(POETRY) run python -m src.core.capabilities

lint:
	@echo "🎨 Checking code style with Ruff..."
	$(POETRY) run ruff check $(PATHS)

format:
	@echo "✨ Formatting code with Black and Ruff..."
	$(POETRY) run black $(PATHS)
	$(POETRY) run ruff check $(PATHS) --fix

test:
	@echo "🧪 Running tests with pytest..."
	$(POETRY) run pytest $(ARGS)

coverage:
	@echo "🧮 Running tests with coverage..."
	$(POETRY) run pytest --cov=src --cov-report=term-missing:skip-covered $(ARGS)

check: lint test audit

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