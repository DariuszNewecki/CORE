#!/bin/bash
# Recreates test database from live database

DB_HOST="192.168.20.23"
DB_USER="core"
DB_PASS="core"  # Add password
LIVE_DB="core"
TEST_DB="core_test"

echo "🔄 Resetting test database from live..."

# Set password for non-interactive use
export PGPASSWORD=$DB_PASS

# Drop and recreate test DB
dropdb -h $DB_HOST -U $DB_USER --if-exists $TEST_DB 2>/dev/null || true
createdb -h $DB_HOST -U $DB_USER $TEST_DB 2>/dev/null || echo "DB already exists"

# Copy schema and data from live
pg_dump -h $DB_HOST -U $DB_USER -d $LIVE_DB | psql -h $DB_HOST -U $DB_USER -d $TEST_DB

unset PGPASSWORD
echo "✅ Test database ready"
