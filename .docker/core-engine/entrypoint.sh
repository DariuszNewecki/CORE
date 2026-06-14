#!/bin/bash
# core-engine entrypoint — boots the CORE daemon (Solo+ runtime, ADR-086 D1).
#
# This image is the application tier ONLY. It needs an external Postgres
# (DATABASE_URL) and Qdrant (QDRANT_URL); it never bundles a database. Mount
# the governed project (a git repo containing .intent/) at /workspace.
#
# The full CLI is available too — pass a command to run it instead of the
# daemon, e.g.:  docker run ... ghcr.io/dariusznewecki/core-engine:X.Y.Z \
#                  core-admin code audit
set -euo pipefail

# If a command was passed (e.g. `core-admin code audit`), run it directly.
# Full-CLI use is not gated by the daemon's DB/workspace requirements — a
# stateless command needs neither.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Default path = the daemon, which DOES require an external Postgres and a
# mounted governed project.
if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set — the core-engine daemon requires an external Postgres." >&2
  echo "       e.g. -e DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/core'" >&2
  exit 78  # EX_CONFIG (sysexits.h)
fi

if [ ! -d "/workspace/.intent" ]; then
  echo "ERROR: no .intent/ found at /workspace — mount your governed project." >&2
  echo '       e.g. -v "$PWD:/workspace"' >&2
  exit 78
fi

# Run the daemon in the foreground as PID 1 (receives SIGTERM on container stop).
exec core-admin daemon start
