#!/usr/bin/env bash
#
# A developer utility to completely reset and rebuild the CORE operational database
# and the Qdrant vector collection.
# WARNING: This is a destructive operation.
#

set -euo pipefail

# --- Safety First: Ensure we are in the project root ---
if [ ! -f "pyproject.toml" ] || [ ! -d ".intent" ]; then
    echo "❌ Error: This script must be run from the CORE project root directory."
    exit 1
fi

# --- Check for a valid .env file BEFORE starting ---
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found."
    echo "   Please create one by running: cp .env.example .env"
    echo "   Then, fill in the required values (especially LLM keys and DATABASE_URL)."
    exit 1
fi

# --- Load environment variables from .env ---
set -o allexport
source <(grep -v '^\s*#' .env | grep -v '^\s*$')
set +o allexport

if [ -z "${DATABASE_URL-}" ] || [ -z "${QDRANT_URL-}" ] || [ -z "${DEEPSEEK_CHAT_API_KEY-}" ]; then
    echo "❌ Error: Your .env file is missing required values like DATABASE_URL, QDRANT_URL, or LLM API keys."
    echo "   Please review .env.example and update your .env file."
    exit 1
fi

# --- The following steps have been performed manually in pgAdmin ---
# echo "🔥 Dropping the 'core' schema..."
# CLEAN_DB_URL=$(echo "$DATABASE_URL" | sed 's/+asyncpg//')
# psql "$CLEAN_DB_URL" -c "DROP SCHEMA IF EXISTS core CASCADE;"
# echo "✅ PostgreSQL schema dropped."

# echo "🏗️  Re-creating the PostgreSQL schema from sql/001_consolidated_schema.sql..."
# psql "$CLEAN_DB_URL" -f sql/001_consolidated_schema.sql
# echo "✅ PostgreSQL schema re-created."
# --- End of manual steps ---


# --- Step 3: Re-create the Qdrant Collection ---
echo "⚡ Re-creating Qdrant vector collection..."
poetry run python3 scripts/reset_qdrant_collection.py
echo "✅ Qdrant collection is ready."

# --- Step 4: Re-build Knowledge from Source Code & Exports ---
echo "🧠 Re-building knowledge from scratch..."

echo "   -> (1/5) Importing bootstrap knowledge from mind_export/ YAMLs..."
poetry run core-admin mind import --write

echo "   -> (2/5) Syncing symbols from code to DB..."
poetry run core-admin manage database sync-knowledge --write

echo "   -> (3/5) Vectorizing all symbols..."
poetry run core-admin run vectorize --write --force

echo "   -> (4/5) Defining capabilities for all new symbols..."
poetry run core-admin manage define-symbols

echo "   -> (5/5) Running final constitutional audit..."
poetry run core-admin check audit

echo "🎉 Database reset and rebuild complete!"