#!/bin/bash
# Recreates core_test schema from the live core database.
#
# IMPORTANT — pg_hba restriction:
#   dropdb/createdb require a superuser connection. pg_hba on 192.168.20.23 blocks
#   those commands from non-server hosts (including the dev container). Run this script
#   directly on the DB server, e.g.:
#     ssh <server> "bash /opt/dev/CORE/infra/scripts/reset_test_db.sh"
#   or open an interactive psql session as postgres on the server.
#
# This script is idempotent: running it again fully resyncs core_test to the
# current live schema without copying any live data.

set -euo pipefail

DB_HOST="192.168.20.23"
DB_USER="core"
DB_PASS="core"
LIVE_DB="core"
TEST_DB="core_test"
TEST_ROLE="core_test_db"
SCHEMA_OUT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)/schema.sql"

echo "Resetting ${TEST_DB} schema from ${LIVE_DB}..."

export PGPASSWORD="${DB_PASS}"

# Drop and recreate the test DB (superuser required — see note above).
dropdb -h "${DB_HOST}" -U "${DB_USER}" --if-exists "${TEST_DB}"
createdb -h "${DB_HOST}" -U "${DB_USER}" "${TEST_DB}"

# Dump portable schema (no OWNER TO / GRANT lines) to schema.sql at repo root,
# then load it into the test DB. --no-owner + --no-acl makes the file
# installable by any role on a fresh Postgres instance (#521 items 1-3).
pg_dump -h "${DB_HOST}" -U "${DB_USER}" \
    --schema-only --no-owner --no-acl \
    "${LIVE_DB}" \
    | sed '/^\\restrict/d; /^\\unrestrict/d' \
    > "${SCHEMA_OUT}"
psql -h "${DB_HOST}" -U "${DB_USER}" -d "${TEST_DB}" -q < "${SCHEMA_OUT}"

# Grant core_test_db access. pg_dump --schema-only copies GRANT ... TO core but
# not to core_test_db, so the test user would otherwise have no schema access.
psql -h "${DB_HOST}" -U "${DB_USER}" -d "${TEST_DB}" -q <<SQL
GRANT USAGE ON SCHEMA core TO ${TEST_ROLE};
GRANT ALL ON ALL TABLES IN SCHEMA core TO ${TEST_ROLE};
GRANT ALL ON ALL SEQUENCES IN SCHEMA core TO ${TEST_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON TABLES TO ${TEST_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON SEQUENCES TO ${TEST_ROLE};
SQL

unset PGPASSWORD
echo "Done. ${TEST_DB} is schema-only from ${LIVE_DB}, granted to ${TEST_ROLE}."
