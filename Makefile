# FILE: Makefile
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

OUTPUT_PATH ?= docs/10_CAPABILITY_REFERENCE.md

.PHONY: help install lock run stop audit lint format test check fast-check clean distclean nuke docs check-docs cli-tree

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "This Makefile provides shortcuts to the main CLI."
	@echo "For all commands, see: 'poetry run core-admin --help'"
	@echo ""
	@echo "Common Shortcuts:"
	@echo "make install       - Install dependencies"
	@echo "make fast-check    - Run linting and tests (RECOMMENDED FOR LOCAL DEV)"
	@echo "make check         - Run all checks including vectorization (for CI)"
	@echo "make lint          - Check code format and quality (read-only)"
	@echo "make format        - Fix code format and quality issues"
	@echo "make test          - Run tests via 'core-admin check ci test'"
	@echo "make run           - Start the API server"
	@echo "make cli-tree      - Display the full CLI command tree"
	@echo "make clean         - Remove temporary files"
	@echo "make docs          - Generate capability documentation"

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


# --- START: CORRECTED COMMANDS ---
audit:
	$(POETRY) run core-admin check ci audit

lint:
	$(POETRY) run core-admin check ci lint

format:
	$(POETRY) run core-admin fix format

test:
	$(POETRY) run core-admin check ci test

cli-tree:
	@echo "🌳 Generating CLI command tree..."
	$(POETRY) run core-admin check diagnostics cli-tree

fast-check:
	$(POETRY) run core-admin check ci lint
	$(POETRY) run core-admin check ci test
# --- END: CORRECTED COMMANDS ---
	
fix-lines:
	@echo "📏 Fixing long lines with AI assistant..."
	$(POETRY) run core-admin fix line-lengths --write
	
fix-docs:
	@echo "✍️  Adding missing docstrings with AI assistant..."
	$(POETRY) run core-admin fix docstrings --write

build-graph:
	@echo "🏗️  Building knowledge graph..."
	$(POETRY) run core-admin build graph

vectorize: build-graph
	@echo "🧠 Vectorizing knowledge graph..."
	$(POETRY) run core-admin run vectorize

check:
	@echo "🤝 Running full constitutional audit and documentation check..."
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) audit
	@$(MAKE) check-docs

docs:
	@echo "📚 Generating capability documentation..."
	$(POETRY) run core-admin build docs

check-docs: docs
	@echo "🔎 Checking for documentation drift..."
	@git diff --exit-code --quiet $(OUTPUT_PATH) || (echo "❌ ERROR: Documentation is out of sync. Please run 'make docs' and commit the changes." && exit 1)
	@echo "✅ Documentation is up to date."

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