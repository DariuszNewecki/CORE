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

.PHONY: help install lock run stop lint format test coverage check clean clean-logs distclean nuke

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "make install       - Install deps with Poetry"
	@echo "make lock          - Update poetry.lock"
	@echo "make run           - Start uvicorn ($(APP)) on $(HOST):$(PORT)"
	@echo "make stop          - Stop dev server (kill script or pkill fallback)"
	@echo "make lint          - Ruff checks"
	@echo "make format        - Black + Ruff --fix"
	@echo "make test [ARGS=]  - Pytest (pass ARGS='-k expr -vv')"
	@echo "make coverage      - Pytest with coverage"
	@echo "make check         - Lint + Tests"
	@echo "make clean         - Remove caches, pending_writes, sandbox"
	@echo "make clean-logs    - Remove logs/*"
	@echo "make distclean     - Clean + venv/node/build"
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

stop:
	@if [ -f ./kill-core.sh ]; then \
		echo "🛑 Using kill-core.sh"; ./kill-core.sh; \
	else \
		echo "🛑 kill-core.sh not found. Attempting pkill uvicorn..."; \
		pkill -f "uvicorn .*$(APP)" || true; \
	fi

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

check: lint test

# ---- Clean targets ---------------------------------------------------------

clean:
	@echo "🧹 Cleaning up temporary files and caches..."
	# Bytecode & __pycache__
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	# Tool caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache .cache
	# Coverage & reports
	rm -f .coverage
	rm -rf htmlcov
	# Build/packaging junk
	rm -rf build dist *.egg-info
	# Local dirs you don't want to keep
	rm -rf pending_writes sandbox
	@echo "✅ Clean complete."

clean-logs:
	@echo "🧻 Removing logs/* ..."
	rm -rf logs/* || true
	@echo "✅ Logs cleaned."

distclean: clean clean-logs
	@echo "🧨 Distclean: removing virtual environments and build leftovers..."
	rm -rf .venv node_modules
	@echo "✅ Distclean complete."

nuke:
	@echo "☢️  Running 'git clean -fdx' in 3s (CTRL+C to cancel)..."
	@sleep 3
	git clean -fdx
	@echo "✅ Repo nuked (untracked files/dirs removed)."
