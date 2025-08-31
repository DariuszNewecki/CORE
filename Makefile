# Makefile for CORE – Cognitive Orchestration Runtime Engine
# This file provides convenient shortcuts to the canonical 'core-admin' CLI commands.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ---- Configurable knobs -----------------------------------------------------
POETRY  ?= python3 -m poetry
APP     ?= src.core.main:app
HOST    ?= 0.0.0.0
PORT    ?= 8000
RELOAD  ?= --reload
ENV_FILE ?= .env

.PHONY: help install lock run stop audit lint format test check fast-check clean distclean nuke

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "This Makefile provides shortcuts to the main CLI."
	@echo "For all commands, see: 'poetry run core-admin --help'"
	@echo ""
	@echo "Common Shortcuts:"
	@echo "make install       - Install dependencies"
	@echo "make check         - Run all checks via 'core-admin system check'"
	@echo "make test          - Run tests via 'core-admin system test'"
	@echo "make format        - Format code via 'core-admin system format'"
	@echo "make run           - Start the API server"
	@echo "make clean         - Remove temporary files"

install:
	@echo "📦 Installing dependencies..."
	$(POETRY) install

lock:
	@echo "🔒 Resolving and locking dependencies..."
	$(POETRY) lock

run:
	@echo "🚀 Starting FastAPI server at http://$(HOST):$(PORT)"
	$(POETRY) run uvicorn $(APP) --host $(HOST) --port $(PORT) $(RELOAD) --env-file $(ENV_FILE)

stop:
	@echo "🛑 Stopping any process on port $(PORT)..."
	@lsof -t -i:$(PORT) | xargs kill -9 2>/dev/null || true

# --- CORE CLI SHORTCUTS ---

audit:
	$(POETRY) run core-admin system audit

lint:
	$(POETRY) run core-admin system lint

format:
	$(POETRY) run core-admin system format

test:
	$(POETRY) run core-admin system test

check:
	$(POETRY) run core-admin system check

fast-check:
	$(POETRY) run core-admin system lint
	$(POETRY) run core-admin system test

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