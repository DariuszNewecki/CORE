#!/usr/bin/env bash
# Init script for the hermetic test Postgres container (docker-compose.test.yml).
#
# The schema dump no longer contains \restrict / \unrestrict ACL markers
# (stripped at source per #521 item 3). The dump is piped directly into psql.

set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < /schema/db_schema_live.sql
