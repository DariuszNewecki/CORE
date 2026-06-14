#!/usr/bin/env bash
#
# install-core.sh — the one-command on-ramp to CORE.
#
# Clone the repo, run ./install-core.sh, and at the end you have a working CORE
# that has just shown you it governing itself. No prior knowledge required, and
# no LLM API key needed for the demo — the consequence-chain it shows you uses
# CORE's deterministic self-healing path (risk-classified-safe, auto-approvable).
#
# What it does, in order:
#   0. check prerequisites (docker, docker compose, poetry, python 3.12+)
#   1. install Python dependencies (poetry install)
#   2. create .env from the template (defaults work for the demo)
#   3. start Postgres + Qdrant (docker compose up -d) and wait for the DB
#   4. apply the constitutional schema (idempotent — skipped if already present)
#   5. verify the install with an offline audit (no services required)
#   6. start the CORE API
#   7. run the consequence-chain demo (scripts/demo.sh) — the believer moment
#   8. leave CORE running and yours, with the next steps printed
#
# Status: v1 — first end-to-end run is on a clean VM (#562). Re-run is safe;
# steps that have already happened are detected and skipped.
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"
API_HOST="${CORE_API_HOST:-127.0.0.1}"
API_PORT="${CORE_API_PORT:-8000}"
API_PID_FILE="var/run/core-api.pid"
API_LOG="var/log/core-api.log"

# ---- pretty output ---------------------------------------------------------
if [[ -t 1 ]]; then
  B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; C=$'\e[36m'; X=$'\e[0m'
else
  B=''; G=''; Y=''; R=''; C=''; X=''
fi
step() { printf '\n%s━━ %s ━━%s\n' "${B}${C}" "$*" "$X"; }
ok()   { printf '  %s✓%s %s\n' "$G" "$X" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$X" "$*"; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$*" "$X" >&2; exit 1; }

# ---- 0. prerequisites ------------------------------------------------------
step "Checking prerequisites"
need() { command -v "$1" >/dev/null 2>&1 || die "Missing '$1'. $2"; ok "$1"; }
need docker "Install Docker Engine: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required (the 'docker compose' subcommand)."
ok "docker compose"
need poetry "Install Poetry: https://python-poetry.org/docs/#installation"
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0.0)"
PYMAJ="${PYV%.*}"; PYMIN="${PYV#*.}"
{ [[ "$PYMAJ" -gt 3 ]] || { [[ "$PYMAJ" -eq 3 ]] && [[ "$PYMIN" -ge 12 ]]; }; } \
  || die "Python 3.12+ required (found ${PYV}). See https://www.python.org/downloads/"
ok "python ${PYV}"

# ---- 1. dependencies -------------------------------------------------------
step "Installing Python dependencies"
poetry install --no-interaction
ok "dependencies installed"

# ---- 2. configuration ------------------------------------------------------
step "Configuring environment"
if [[ -f .env ]]; then
  ok ".env already exists — leaving it untouched"
else
  cp .env.example .env
  ok "created .env from .env.example (defaults are demo-ready; no API key needed)"
fi
mkdir -p var/run var/log

# ---- 3. services -----------------------------------------------------------
step "Starting Postgres + Qdrant"
docker compose up -d
# Wait for Postgres to be REALLY ready. On first start the official image runs
# initdb behind a temporary socket-only server, then restarts for real — so any
# connection probe (pg_isready / SELECT 1) over the socket can pass against the
# temp server and race the schema apply into "the database system is shutting
# down". The reliable signal is the log: the entrypoint prints "PostgreSQL init
# process complete" before the real server starts, so we wait for the
# "ready to accept connections" line that comes AFTER it (or, on an existing
# volume where there is no initdb, any such line).
printf '  waiting for Postgres'
db_ready=0
for i in $(seq 1 90); do
  logs="$(docker compose logs postgres 2>/dev/null)"
  if printf '%s\n' "$logs" | grep -q 'PostgreSQL init process complete'; then
    # Fresh init finished: only the ready line AFTER it belongs to the real
    # server (the earlier one was the temporary init server, which then shuts
    # down — racing the schema apply if trusted).
    if printf '%s\n' "$logs" | sed -n '/PostgreSQL init process complete/,$p' \
         | grep -q 'database system is ready to accept connections'; then
      db_ready=1; printf '\n'; ok "Postgres ready"; break
    fi
  elif [[ "$i" -ge 6 ]] \
       && printf '%s\n' "$logs" | grep -q 'database system is ready to accept connections' \
       && ! printf '%s\n' "$logs" | grep -q 'shutting down'; then
    # No initdb after ~12s (existing volume, no temp server): the ready line is
    # the real server.
    db_ready=1; printf '\n'; ok "Postgres ready"; break
  fi
  printf '.'; sleep 2
done
[[ "$db_ready" -eq 1 ]] || die "Postgres did not become ready within 180s. Check 'docker compose logs postgres'."

# ---- 4. schema -------------------------------------------------------------
step "Applying the constitutional schema"
if docker compose exec -T postgres psql -U postgres -d core -tAc \
     "SELECT to_regclass('core.blackboard_entries')" 2>/dev/null | grep -q blackboard_entries; then
  ok "schema already present — skipping"
else
  # Apply with retries to ride out the initdb temp-server/real-server restart
  # (which can otherwise drop the connection mid-apply with "shutting down").
  # Each attempt starts from a clean slate so a partial apply from a raced
  # attempt doesn't fail the next one on "already exists".
  schema_done=0
  for attempt in $(seq 1 8); do
    docker compose exec -T postgres psql -U postgres -d core -c 'DROP SCHEMA IF EXISTS core CASCADE' >/dev/null 2>&1 || true
    # roles the dump's OWNER/GRANT statements reference (bare — app connects as
    # the postgres superuser, see .env DATABASE_URL), and btree_gist for the one
    # EXCLUDE-gist constraint (ships with the image, not created by the dump).
    docker compose exec -T postgres psql -U postgres -d core -c 'CREATE ROLE core_db' >/dev/null 2>&1 || true
    docker compose exec -T postgres psql -U postgres -d core -c 'CREATE ROLE core'    >/dev/null 2>&1 || true
    docker compose exec -T postgres psql -U postgres -d core -c 'CREATE EXTENSION IF NOT EXISTS btree_gist' >/dev/null 2>&1 || true
    if docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d core \
         < infra/sql/db_schema_live.sql >/dev/null 2>&1; then
      schema_done=1; ok "schema applied from infra/sql/db_schema_live.sql"; break
    fi
    sleep 3
  done
  [[ "$schema_done" -eq 1 ]] || die "Schema apply failed after retries. Check 'docker compose logs postgres'."
fi

# ---- 5. verify -------------------------------------------------------------
step "Verifying the install (offline audit — needs no running services)"
if poetry run core-admin code audit --offline --severity block >/dev/null 2>&1; then
  ok "constitutional audit runs and the tree is clean"
else
  warn "offline audit reported findings (that's fine — the demo will create and resolve one)"
fi

# ---- 6. start the API ------------------------------------------------------
step "Starting the CORE API"
if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
  ok "API already running at http://${API_HOST}:${API_PORT}"
else
  nohup poetry run uvicorn src.api.main:create_app --factory \
    --host "$API_HOST" --port "$API_PORT" --env-file .env >>"$API_LOG" 2>&1 &
  echo $! > "$API_PID_FILE"
  printf '  waiting for the API'
  for i in $(seq 1 30); do
    if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
      printf '\n'; ok "API up (PID $(cat "$API_PID_FILE"), logs: ${API_LOG})"; break
    fi
    printf '.'; sleep 2
    [[ "$i" -eq 30 ]] && { printf '\n'; die "API did not respond within 60s. Check ${API_LOG}."; }
  done
fi

# ---- 7. the demo -----------------------------------------------------------
step "Showing you CORE govern itself"
# The demo's execute step commits the fix — a fresh clone may have no git
# identity, which would make that commit fail. Set a local fallback if unset.
git config user.email >/dev/null 2>&1 || git config user.email "you@example.com"
git config user.name  >/dev/null 2>&1 || git config user.name  "CORE User"
CORE_API_HOST="$API_HOST" CORE_API_PORT="$API_PORT" bash scripts/demo.sh

# ---- 8. done ---------------------------------------------------------------
step "CORE is yours"
cat <<EOF

  CORE is installed, running, and has just shown you the full loop:
  a violation found, a fix proposed, approved, executed, and verified —
  with the whole causal chain recorded.

  Try it yourself:
    poetry run core-admin code audit --offline      # audit this repo, no services
    poetry run core-admin runtime dashboard         # governor situational awareness
    bash scripts/demo.sh                            # re-run the demo any time

  Turn on autonomy (CORE watches and self-heals in the background):
    make daemon-start

  Watch CORE write code (needs an LLM — configure one in .env):
    poetry run core-admin workers remediate <rule>

  Docs: https://dariusznewecki.github.io/CORE/
EOF
