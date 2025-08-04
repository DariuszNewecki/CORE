# Makefile for CORE – Cognitive Orchestration Runtime Engine (Robust Version)

.PHONY: help install lock run stop lint format test manifest-update clean

# Default command: show help
help:
	@echo "CORE Development Makefile"
	@echo "-------------------------"
	@echo "Available commands:"
	@echo "  make install         - Install dependencies using Poetry"
	@echo "  make lock            - Update the poetry.lock file"
	@echo "  make run             - Stop any running server and start a new one with auto-reload"
	@echo "  make stop            - Stop the development server if it is running"
	@echo "  make lint            - Run Ruff to check for linting errors"
	@echo "  make format          - Auto-format code with Black and Ruff"
	@echo "  make test            - Run all tests with pytest"
	@echo "  make clean           - Remove temporary Python files"

install:
	@echo "📦 Installing dependencies..."
	python3 -m poetry install

lock:
	@echo "🔒 Resolving and locking dependencies..."
	python3 -m poetry lock

# --- MODIFICATION: The 'run' command now depends on 'stop' ---
# This ensures that `make stop` is always executed before `make run` starts.
run: stop
	@echo "🚀 Starting FastAPI server at http://127.0.0.1:8000"
	python3 -m poetry run uvicorn src.core.main:app --reload --host 0.0.0.0 --port 8000

# --- MODIFICATION: New target to stop the server ---
# It checks for the kill script and runs it.
stop:
	@if [ -f ./kill-core.sh ]; then \
		./kill-core.sh; \
	else \
		echo "⚠️  kill-core.sh not found. Skipping stop."; \
	fi

lint:
	@echo "🎨 Checking code style with Ruff..."
	python3 -m poetry run ruff check .

format:
	@echo "✨ Formatting code with Black and Ruff..."
	python3 -m poetry run ruff check . --fix
	python3 -m poetry run black .

test:
	@echo "🧪 Running tests with pytest..."
	python3 -m poetry run pytest

clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} +