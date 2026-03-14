# Makefile for CORE — The Self-Improving System Architect
#
# UPDATED: Layer-Aware paths (Mind/Body/Will).
# Removed references to the legacy 'features' directory.

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

# Daemon PID file — lives in var/ (runtime, gitignored)
DAEMON_PID  := var/run/core-daemon.pid
DAEMON_LOG  := var/log/core-daemon.log

# ---- Phony targets -----------------------------------------------------------
.PHONY: \
  help install lock run stop \
  daemon daemon-start daemon-stop daemon-status daemon-restart daemon-logs \
  audit check-constitution check-ui validate \
  lint format test coverage dev-sync \
  dupes traces refusals cli-tree clean nuke \
  docs vectorize integrate \
  migrate export-db sync-knowledge \
  patterns state

# ---- Help (auto-documented) --------------------------------------------------
help: ## Show this help message
	@echo "CORE Development Makefile (Layered Architecture v2.3)"
	@echo "------------------------------------------------------------"
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Tip: run 'core-admin --help' to see the resource-based CLI hierarchy."

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

# ==============================================================================
#   DAEMON — Background worker control
# ==============================================================================

daemon: daemon-status ## Alias: show daemon status

daemon-start: ## Start the CORE daemon in the background
	@mkdir -p var/run var/log
	@if [ -f $(DAEMON_PID) ] && kill -0 "$$(cat $(DAEMON_PID))" 2>/dev/null; then \
		echo "⚠️  Daemon already running (PID $$(cat $(DAEMON_PID)))"; \
		exit 0; \
	fi
	@echo "🟢 Starting CORE daemon..."
	@nohup $(POETRY) run python -c "import asyncio; from will.commands.daemon import _run_daemon; asyncio.run(_run_daemon())" >> $(DAEMON_LOG) 2>&1 & echo $$! > $(DAEMON_PID)
	@sleep 2
	@if kill -0 "$$(cat $(DAEMON_PID))" 2>/dev/null; then \
		echo "✅ Daemon started (PID $$(cat $(DAEMON_PID))) — logs: $(DAEMON_LOG)"; \
	else \
		echo "❌ Daemon failed to start. Check logs: $(DAEMON_LOG)"; \
		rm -f $(DAEMON_PID); \
		exit 1; \
	fi

daemon-stop: ## Stop the CORE daemon gracefully
	@{ \
	  if [ ! -f $(DAEMON_PID) ]; then \
	    echo "ℹ️  No PID file found — daemon may not be running"; \
	    exit 0; \
	  fi; \
	  PID=$$(cat $(DAEMON_PID)); \
	  if kill -0 "$$PID" 2>/dev/null; then \
	    echo "🛑 Stopping CORE daemon (PID $$PID)..."; \
	    kill -TERM "$$PID"; \
	    for i in 1 2 3 4 5; do \
	      sleep 1; \
	      kill -0 "$$PID" 2>/dev/null || break; \
	    done; \
	    if kill -0 "$$PID" 2>/dev/null; then \
	      echo "⚠️  Daemon did not stop gracefully — sending SIGKILL"; \
	      kill -KILL "$$PID"; \
	    fi; \
	    echo "✅ Daemon stopped"; \
	  else \
	    echo "ℹ️  Daemon not running (stale PID $$PID)"; \
	  fi; \
	  rm -f $(DAEMON_PID); \
	}

daemon-restart: daemon-stop daemon-start ## Restart the CORE daemon

daemon-status: ## Show daemon status
	@if [ -f $(DAEMON_PID) ] && kill -0 "$$(cat $(DAEMON_PID))" 2>/dev/null; then \
		echo "🟢 Daemon is RUNNING (PID $$(cat $(DAEMON_PID)))"; \
		echo "   Logs: $(DAEMON_LOG)"; \
	elif [ -f $(DAEMON_PID) ]; then \
		echo "🔴 Daemon is STOPPED (stale PID file)"; \
		rm -f $(DAEMON_PID); \
	else \
		echo "🔴 Daemon is STOPPED"; \
	fi

daemon-logs: ## Tail daemon logs (Ctrl+C to exit)
	@if [ ! -f $(DAEMON_LOG) ]; then \
		echo "ℹ️  No daemon log found at $(DAEMON_LOG)"; \
		exit 0; \
	fi
	@tail -f $(DAEMON_LOG)

# ==============================================================================
#   QUALITY GATES & VALIDATION (Composing Atomic Resource Actions)
# ==============================================================================

check-constitution: ## Check constitutional compliance (audit)
	@echo "⚖️  Running constitutional audit..."
	$(CORE_ADMIN) code audit

check-ui: ## Check for UI leaks in Body layer (Headless enforcement)
	@echo "🔍 Checking Body-layer UI contracts..."
	$(CORE_ADMIN) code check-ui

audit: dev-sync check-constitution check-ui ## Full audit: sync → constitution → ui
	@echo "✅ Full system audit complete"

validate: audit ## Alias for audit (pre-commit validation)
	@echo "✅ Validation complete"

# ==============================================================================

# ---- Individual Resource Actions (Neurons) -----------------------------------
lint: ## Check code format and quality (read-only)
	$(CORE_ADMIN) code lint

format: ## Fix code style and import order
	@echo "✨ Formatting code (Black/Ruff)..."
	$(CORE_ADMIN) code format --write
	@echo "🧹 Sorting imports..."
	$(CORE_ADMIN) code format-imports --write

test: ## Run test suite
	@echo "🧪 Running tests with pytest..."
	$(POETRY) run pytest --cov=src --cov-report=json

coverage: ## Check coverage compliance
	@echo "📈 Checking coverage meets constitutional requirement..."
	$(CORE_ADMIN) code audit --verbose

# ==============================================================================
#   DEV-SYNC: Atomic Operations Composed (The "Limb" Pipeline)
# ==============================================================================

dev-sync: ## Synchronize local state (IDs -> Dedup -> Format -> DB -> Vectors)
	@echo "🔄 CORE Development Sync Pipeline"
	@echo "=================================="
	@echo "1️⃣  Fixing symbol IDs..."
	@$(CORE_ADMIN) symbols fix-ids --write
	@echo "2️⃣  Resolving duplicate IDs..."
	@$(CORE_ADMIN) symbols resolve-duplicates --write
	@echo "3️⃣  Formatting code & imports..."
	@$(MAKE) format
	@echo "4️⃣  Syncing knowledge graph..."
	@$(CORE_ADMIN) symbols sync --write
	@echo "5️⃣  Updating memory (vectors)..."
	@$(CORE_ADMIN) vectors sync-code --write
	@echo "6️⃣  Generating operational summary..."
	@$(CORE_ADMIN) admin summary
	@echo "✅ Dev-sync complete"

# ==============================================================================

# ---- Forensics & Analytics (Admin Resource) ----------------------------------
dupes: ## Check for duplicate code (semantic analysis)
	@echo "👯 Running semantic duplication analysis..."
	$(CORE_ADMIN) code audit-duplicates --threshold 0.96

traces: ## View recent autonomous decision traces
	$(CORE_ADMIN) admin traces

refusals: ## View constitutional refusal logs
	$(CORE_ADMIN) admin refusals

patterns: ## Analyze architectural pattern usage
	$(CORE_ADMIN) admin patterns

state: ## Show current database and migration status
	$(CORE_ADMIN) database status

# ---- Maintenance & Lifecycle -------------------------------------------------
migrate: ## Apply pending DB schema migrations
	$(CORE_ADMIN) database migrate --apply

export-db: ## Export DB tables to canonical YAML
	$(CORE_ADMIN) database export

sync-knowledge: ## Scan codebase and sync symbols to DB (SSOT)
	$(CORE_ADMIN) database sync --write

vectorize: ## Full vectorization (Constitution + Code)
	@echo "🧠 Vectorizing constitution..."
	$(CORE_ADMIN) vectors sync --write
	@echo "🧠 Vectorizing code symbols..."
	$(CORE_ADMIN) vectors sync-code --write

integrate: ## Finalize changes and integrate into system
	$(CORE_ADMIN) proposals integrate --message "feat: Integrate changes via make"

# ---- Docs --------------------------------------------------------------------
docs: ## Generate capability documentation
	@echo "📚 Generating capability documentation..."
	$(CORE_ADMIN) project docs

# ---- Clean -------------------------------------------------------------------
clean: ## Remove temporary files and caches
	@echo "🧹 Cleaning temporary files..."
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .cache
	rm -rf build dist *.egg-info var/workflows/pending_writes work/testing
	@echo "✅ Clean complete."

nuke: ## Danger! Remove ALL untracked files
	@echo "☢️  Running 'git clean -fdx' in 3s..."
	@sleep 3
	git clean -fdx
