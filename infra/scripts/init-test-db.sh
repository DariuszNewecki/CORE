#!/usr/bin/env bash
# Init script for the hermetic test Postgres container (docker-compose.test.yml).
#
# schema.sql is portable: no OWNER TO or GRANT lines (#521 items 1-3).

set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < /schema/schema.sql
