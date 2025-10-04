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

# --- Load environment variables from .env ---
if [ -f .env ]; then
    set -o allexport
    source <(grep -v '^\s*#' .env | grep -v '^\s*$')
    set +o allexport
else
    echo "❌ Error: .env file not found. Cannot connect to the database."
    exit 1
fi

if [ -z "${DATABASE_URL-}" ] || [ -z "${QDRANT_URL-}" ]; then
    echo "❌ Error: DATABASE_URL and QDRANT_URL must be set in your .env file."
    exit 1
fi

# --- Final Confirmation ---
echo "☢️  WARNING: This will permanently delete all data in the 'core' schema of your database"
echo "    and expects that your Qdrant volume has been cleared."
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# --- Step 1: Drop the PostgreSQL Schema ---
echo "🔥 Dropping the 'core' schema..."
CLEAN_DB_URL=$(echo "$DATABASE_URL" | sed 's/+asyncpg//')
psql "$CLEAN_DB_URL" -c "DROP SCHEMA IF EXISTS core CASCADE;"
echo "✅ PostgreSQL schema dropped."

# --- Step 2: Re-migrate the PostgreSQL Schema ---
echo "🏗️  Re-creating the PostgreSQL schema from migrations..."
poetry run core-admin manage database migrate --apply
echo "✅ PostgreSQL schema re-created."

# --- Step 3: Re-create the Qdrant Collection ---
echo "⚡ Re-creating Qdrant vector collection..."
poetry run python3 scripts/create_qdrant_collection.py
echo "✅ Qdrant collection is ready."

# --- Step 4: Re-build Knowledge from Source Code ---
echo "🧠 Re-building knowledge from scratch..."

echo "   -> (1/6) Syncing operational knowledge (Roles & Resources)..."
poetry run core-admin manage database sync-operational

echo "   -> (2/6) Syncing symbols from code to DB..."
poetry run core-admin manage database sync-knowledge --write

echo "   -> (3/6) Vectorizing all symbols..."
poetry run core-admin run vectorize --write

echo "   -> (4/6) Defining capabilities for new symbols..."
poetry run core-admin manage define-symbols

echo "   -> (5/6) Syncing DB state back to project manifest..."
poetry run core-admin manage database sync-manifest

echo "   -> (6/6) Running final constitutional audit..."
poetry run core-admin check audit

echo "🎉 Database reset and rebuild complete!"
