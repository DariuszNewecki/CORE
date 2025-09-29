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

.PHONY: help install lock run stop audit lint format test check fast-check clean distclean nuke docs check-docs cli-tree integrate

help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "This Makefile provides shortcuts to the main CLI."
	@echo "For all commands, see: 'poetry run core-admin --help'"
	@echo ""
	@echo "Common Shortcuts:"
	@echo "make install       - Install dependencies"
	@echo "make integrate     - Run the full, canonical integration sequence"
	@echo "make check         - Run all checks including vectorization (for CI)"
	@echo "make fast-check    - Run linting and tests (RECOMMENDED FOR LOCAL DEV)"
	@echo "make lint          - Check code format and quality (read-only)"
	@echo "make format        - Fix code format and quality issues"
	@echo "make test          - Run tests via 'core-admin check tests'"
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


# --- START OF UPDATED COMMANDS ---
audit:
	$(POETRY) run core-admin check audit

lint:
	$(POETRY) run core-admin check lint

format:
	$(POETRY) run core-admin fix code-style

test:
	$(POETRY) run core-admin check tests

cli-tree:
	@echo "🌳 Generating CLI command tree..."
	$(POETRY) run core-admin inspect command-tree

fast-check:
	$(MAKE) lint
	$(MAKE) test
	
fix-lines:
	@echo "📏 Fixing long lines with AI assistant..."
	$(POETRY) run core-admin fix line-lengths --write
	
fix-docs:
	@echo "✍️  Adding missing docstrings with AI assistant..."
	$(POETRY) run core-admin fix docstrings --write

vectorize:
	@echo "🧠 Vectorizing knowledge graph..."
	$(POETRY) run core-admin run vectorize

check:
	@echo "🤝 Running full constitutional audit and documentation check..."
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) audit
	@$(MAKE) check-docs

# The 'integrate' command is now superseded by the more explicit 'submit' command.
# Kept for backward compatibility for now, but points to the new workflow command.
integrate:
	@echo "🤝 Running Canonical Integration Sequence via 'submit changes'..."
	$(POETRY) run core-admin submit changes --message "feat: Integrate changes via make"

docs:
	@echo "📚 Generating capability documentation..."
	# This is a conceptual placeholder. The 'build docs' command would need to be re-wired.
	# For now, let's assume it maps to a management task.
	$(POETRY) run core-admin manage project docs
# --- END OF UPDATED COMMANDS ---

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