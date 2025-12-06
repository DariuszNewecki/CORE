# FILE: Makefile
# Makefile for CORE — The Self-Improving System Architect
#
# This file maps concise 'make' commands to the authoritative 'core-admin' CLI.
# It serves as the developer's control panel.

# ---- Shell & defaults --------------------------------------------------------
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ---- Configurable knobs ------------------------------------------------------
POETRY      ?= poetry
APP         ?= src.api.main:create_app
HOST        ?= 0.0.0.0
PORT        ?= 8000
RELOAD      ?= --reload
ENV_FILE    ?= .env

# Internal helpers
PY          := $(POETRY) run python
CORE_ADMIN  := $(POETRY) run core-admin
OUTPUT_PATH := docs/10_CAPABILITY_REFERENCE.md

# ---- Phony targets -----------------------------------------------------------
.PHONY: \
  help install lock run stop \
  audit lint format test test-coverage check \
  dev-sync dev-sync-apply \
  fix-all dupes cli-tree clean distclean nuke \
  docs check-docs vectorize integrate \
  migrate export-db sync-knowledge sync-manifest \
  patterns check-patterns state

# ---- Help (auto-documented) --------------------------------------------------
help: ## Show this help message
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Tip: run 'core-admin --help' to see all granular CLI commands."

# ---- Setup -------------------------------------------------------------------
install: ## Install dependencies (poetry install)
	@echo "📦 Installing dependencies..."
	$(POETRY) install

lock: ## Resolve and lock dependencies
	@echo "🔒 Resolving and locking dependencies..."
	$(POETRY) lock

# ---- Run / Stop --------------------------------------------------------------
run: ## Start the FastAPI server (uvicorn)
	@echo "🚀 Starting FastAPI server at http://$(HOST):$(PORT)"
	$(POETRY) run uvicorn $(APP) --factory --host $(HOST) --port $(PORT) $(RELOAD) --env-file $(ENV_FILE)

stop: ## Kill any process listening on $(PORT)
	@echo "🛑 Stopping any process on port $(PORT)..."
	@command -v lsof >/dev/null 2>&1 && lsof -t -i:$(PORT) | xargs kill -9 2>/dev/null || true

# ---- Checks / Fixes ----------------------------------------------------------
audit: ## Run the constitutional audit
	$(CORE_ADMIN) check audit

lint: ## Check code format and quality (read-only)
	$(CORE_ADMIN) check lint

format: ## Fix code style issues (Black/Ruff via CLI)
	$(CORE_ADMIN) fix code-style

test: ## Run tests
	@echo "🧪 Running tests with pytest..."
	$(POETRY) run pytest

test-coverage: ## Run tests with coverage report and validation
	@echo "📊 Running tests with coverage report..."
	$(POETRY) run pytest --cov --cov-report=term-missing
	@echo "📈 Checking coverage meets constitutional requirement..."
	$(CORE_ADMIN) coverage check

check: ## Run full suite: Lint + Tests + Coverage + Audit + Docs
	@echo "🤝 Running full constitutional audit and documentation check..."
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) test-coverage
	$(MAKE) audit
	@$(MAKE) check-docs

fix-all: ## Run all self-healing fixes in curated sequence
	$(CORE_ADMIN) fix all

# ==============================================================================
#   DEV-SYNC: SAFE vs. APPLY
# ==============================================================================

dev-sync: ## Run the dev-sync workflow in DRY-RUN mode (safe, recommended)
	@echo "🔄 Running CORE dev-sync workflow (dry-run, no writes)..."
	$(CORE_ADMIN) dev sync --dry-run
	@echo "✅ Dev-sync dry-run complete! No changes were written."

dev-sync-apply: ## Run dev-sync WITH WRITES (dangerous!)
	@echo "⚠️  Running CORE dev-sync workflow WITH WRITES ENABLED..."
	@echo "⚠️  This will modify files, update vectors, and apply system changes."
	$(CORE_ADMIN) dev sync --write
	@echo "✅ Dev-sync with writes complete."

# ==============================================================================

dupes: ## Check for duplicate code (semantic similarity analysis)
	@echo "🔍 Running semantic duplication analysis..."
	$(CORE_ADMIN) inspect duplicates --threshold 0.96

cli-tree: ## Display CLI command tree
	@echo "🌳 Generating CLI command tree..."
	$(CORE_ADMIN) inspect command-tree

# ---- Pattern Management ------------------------------------------------------
patterns: ## List available design patterns
	@echo "📋 CORE Design Patterns"
	@$(CORE_ADMIN) patterns list

check-patterns: ## Check code compliance with design patterns
	@echo "🔍 Checking pattern compliance..."
	@$(CORE_ADMIN) patterns check

# ---- System State ------------------------------------------------------------
state: ## Show current CORE system state snapshot
	@echo "📊 CORE System State"
	@$(CORE_ADMIN) inspect state

# ---- Knowledge / DB helpers --------------------------------------------------
migrate: ## Apply pending DB schema migrations
	$(CORE_ADMIN) manage database migrate --apply

export-db: ## Export DB tables to canonical YAML
	$(CORE_ADMIN) manage database export

sync-knowledge: ## Scan codebase and sync symbols to DB (SSOT)
	$(CORE_ADMIN) manage database sync-knowledge --write

sync-manifest: ## Sync .intent manifest from DB
	$(CORE_ADMIN) manage database sync-manifest

vectorize: ## Vectorize knowledge graph, patterns, and policies
	@echo "🧠 Vectorizing constitutional patterns..."
	$(CORE_ADMIN) manage patterns vectorize
	@echo "🧠 Vectorizing constitutional policies..."
	$(CORE_ADMIN) manage policies vectorize
	@echo "🧠 Vectorizing knowledge graph..."
	$(CORE_ADMIN) run vectorize --write

integrate: ## Canonical integration sequence (submits changes)
	@echo "⚠️  WARNING: This will auto-commit and submit changes!"
	$(CORE_ADMIN) submit changes --message "feat: Integrate changes via make"

coverage-run: ## Run the nightly autonomous coverage remediation job
	@echo "🤖 Starting autonomous coverage remediation job..."
	$(POETRY) run python scripts/nightly_coverage_remediation.py

# ---- Docs --------------------------------------------------------------------
docs: ## Generate capability documentation
	@echo "📚 Generating capability documentation..."
	$(CORE_ADMIN) manage project docs

check-docs: docs ## Verify documentation is in sync
	@echo "🔎 Checking for documentation drift..."
	@git diff --exit-code --quiet "$(OUTPUT_PATH)" || (echo "❌ ERROR: Documentation is out of sync. Please run 'make docs' and commit the changes." && exit 1)
	@echo "✅ Documentation is up to date."

# ---- Clean -------------------------------------------------------------------
clean: ## Remove temporary files and caches
	@echo "🧹 Cleaning up temporary files and caches..."
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .cache
	rm -rf build dist *.egg-info
	rm -rf pending_writes sandbox
	@echo "✅ Clean complete."

distclean: clean ## Clean + remove virtual env
	@echo "🧨 Distclean: removing virtual environments and build leftovers..."
	rm -rf .venv
	@echo "✅ Distclean complete."

nuke: ## Danger! Remove ALL untracked files (git clean -fdx)
	@echo "☢️  Running 'git clean -fdx' in 3s (CTRL+C to cancel)..."
	@sleep 3
	git clean -fdx
	@echo "✅ Repo nuked (untracked files/dirs removed)."
