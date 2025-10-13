# FILE: Makefile
# Makefile for CORE – Cognitive Orchestration Runtime Engine
# This file provides convenient shortcuts to the canonical 'core-admin' CLI commands.

# ---- Shell & defaults --------------------------------------------------------
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ---- Configurable knobs ------------------------------------------------------
POETRY      ?= python3 -m poetry
APP         ?= src.core.main:create_app
HOST        ?= 0.0.0.0
PORT        ?= 8000
RELOAD      ?= --reload
ENV_FILE    ?= .env

# Capability docs output
OUTPUT_PATH ?= docs/10_CAPABILITY_REFERENCE.md

# Internal helpers
PY          := $(POETRY) run python

# ---- Phony targets -----------------------------------------------------------
.PHONY: \
  help install lock run stop \
  audit lint format test fast-check check dev-sync \
  cli-tree clean distclean nuke \
  docs check-docs vectorize integrate \
  migrate export-db sync-knowledge sync-manifest

# ---- Help (auto-documented) --------------------------------------------------
# Use the pattern "target: ## description" to list in `make help`.
help: ## Show this help message
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "This Makefile maps to 'core-admin' CLI commands."
	@echo ""
	@awk 'BEGIN {FS":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Tip: run '$(POETRY) run core-admin --help' for the full CLI."

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
	$(POETRY) run core-admin check audit

lint: ## Check code format and quality (read-only)
	$(POETRY) run core-admin check lint

format: ## Fix code style issues (Black/Ruff via CLI)
	$(POETRY) run core-admin fix code-style

test: ## Run tests
	@echo "🧪 Running tests with pytest..."
	$(POETRY) run pytest

fast-check: ## Lint + tests (quick local cycle)
	$(MAKE) lint
	$(MAKE) test

check: ## Lint + tests + audit + docs drift check
	@echo "🤝 Running full constitutional audit and documentation check..."
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) audit
	@$(MAKE) check-docs

dev-sync: ## Run the safe, non-destructive developer sync and audit workflow
	$(POETRY) run core-admin check system

cli-tree: ## Display CLI command tree
	@echo "🌳 Generating CLI command tree..."
	$(POETRY) run core-admin inspect command-tree

# ---- Knowledge / DB helpers --------------------------------------------------
migrate: ## Apply pending DB schema migrations
	$(POETRY) run core-admin manage database migrate

export-db: ## Export DB tables to canonical YAML
	$(POETRY) run core-admin manage database export

sync-knowledge: ## Scan codebase and sync symbols to DB (Single Source of Truth)
	$(POETRY) run core-admin manage database sync-knowledge --write

sync-manifest: ## Sync .intent/mind/project_manifest.yaml from DB
	$(POETRY) run core-admin manage database sync-manifest

vectorize: ## Vectorize knowledge graph (embeddings pipeline)
	@echo "🧠 Vectorizing knowledge graph..."
	$(POETRY) run core-admin run vectorize

integrate: ## Canonical integration sequence (submit changes)
	@echo "🤝 Running Canonical Integration Sequence via 'submit changes'..."
	$(POETRY) run core-admin submit changes --message "feat: Integrate changes via make"

# ---- Docs --------------------------------------------------------------------
docs: ## Generate capability documentation
	@echo "📚 Generating capability documentation..."
	# Option A: preferred CLI-managed docs (if implemented)
	-$(POETRY) run core-admin manage project docs || true
	# Option B: direct module entry point (fallback)
	$(PY) -m features.introspection.generate_capability_docs --output "$(OUTPUT_PATH)"

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
	rm -f .coverage
	rm -rf htmlcov
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
