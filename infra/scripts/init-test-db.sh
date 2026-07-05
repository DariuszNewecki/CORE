#!/usr/bin/env bash
# Init script for the hermetic test Postgres container (docker-compose.test.yml).
#
# CORE's schema dump includes two file-level ACL markers that are not valid SQL
# or psql metacommands:
#   \restrict <token>    — line 5 (first line of dump body)
#   \unrestrict <token>  — last line of dump
# Both lines start with a backslash. sed strips them before the dump is piped
# into psql; without this, Docker's init harness aborts on the first unknown
# psql metacommand (ON_ERROR_STOP=1 is set by the official entrypoint).

set -euo pipefail

sed '/^\\/d' /schema/db_schema_live.sql \
  | psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
