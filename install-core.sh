#!/usr/bin/env bash
#
# install-core.sh — the one-command on-ramp to CORE.
#
# Two modes:
#
#   ./install-core.sh                      # Docker path (default)
#       Requires: docker, docker compose v2, poetry, python 3.12+
#       Brings up Postgres + Qdrant via Docker, loads the schema, starts
#       the CORE API, and runs the consequence-chain demo.
#
#   ./install-core.sh --bare \             # Bare path
#       --db-url  "postgresql://user:pass@host:5432/dbname" \
#       --qdrant-url "http://host:6333"
#       Requires: python 3.12+, poetry, psql client, reachable DB + Qdrant
#       Sets up the Python environment, loads the schema, writes start.sh /
#       stop.sh, and prints next steps. You manage infra; CORE manages itself.
#
# Re-run is safe — steps that have already happened are detected and skipped.
#
# Status: v2 — schema.sql at root, --no-owner (portable), Qdrant collection
# created lazily by API lifespan (#521). Bare mode added (#522).

set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"
API_HOST="${CORE_API_HOST:-127.0.0.1}"
API_PORT="${CORE_API_PORT:-8000}"
API_PID_FILE="var/run/core-api.pid"
DAEMON_PID_FILE="var/run/core-daemon.pid"
API_LOG="var/log/core-api.log"
DAEMON_LOG="var/log/core-daemon.log"

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

# ---- argument parsing ------------------------------------------------------
BARE=0
DB_URL=""
QDRANT_URL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bare)       BARE=1; shift ;;
    --db-url)     DB_URL="$2"; shift 2 ;;
    --db-url=*)   DB_URL="${1#*=}"; shift ;;
    --qdrant-url) QDRANT_URL="$2"; shift 2 ;;
    --qdrant-url=*) QDRANT_URL="${1#*=}"; shift ;;
    -h|--help)
      sed -n '2,23p' "$0" | sed 's/^#//' | sed 's/^ //'
      exit 0 ;;
    *) die "Unknown argument: $1. Run with --help for usage." ;;
  esac
done

if [[ "$BARE" -eq 1 ]]; then
  [[ -n "$DB_URL" ]]     || die "--bare requires --db-url postgresql://user:pass@host:5432/dbname"
  [[ -n "$QDRANT_URL" ]] || die "--bare requires --qdrant-url http://host:6333"
fi

# ===========================================================================
# SHARED STEPS (both paths)
# ===========================================================================

# ---- check python ----------------------------------------------------------
check_python() {
  PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0.0)"
  PYMAJ="${PYV%.*}"; PYMIN="${PYV#*.}"
  { [[ "$PYMAJ" -gt 3 ]] || { [[ "$PYMAJ" -eq 3 ]] && [[ "$PYMIN" -ge 12 ]]; }; } \
    || die "Python 3.12+ required (found ${PYV}). See https://www.python.org/downloads/"
  ok "python ${PYV}"
}

# ---- install deps ----------------------------------------------------------
install_deps() {
  step "Installing Python dependencies"
  poetry install --no-interaction
  ok "dependencies installed"
}

# ---- write .env ------------------------------------------------------------
write_env() {
  step "Configuring environment"
  if [[ -f .env ]]; then
    ok ".env already exists — leaving it untouched"
  else
    [[ -f .env.example ]] || die ".env.example not found — is this a complete CORE checkout?"
    cp .env.example .env
    # Patch DB_URL and QDRANT_URL for the bare path
    if [[ "$BARE" -eq 1 ]]; then
      # Replace placeholder values with the supplied URLs
      sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DB_URL}|" .env
      sed -i "s|^QDRANT_URL=.*|QDRANT_URL=${QDRANT_URL}|" .env
      ok "created .env from .env.example with your DB + Qdrant URLs"
    else
      ok "created .env from .env.example (defaults are demo-ready; no API key needed)"
    fi
  fi
  mkdir -p var/run var/log
}

# ===========================================================================
# DOCKER PATH
# ===========================================================================
run_docker() {
  need() { command -v "$1" >/dev/null 2>&1 || die "Missing '$1'. $2"; ok "$1"; }

  step "Checking prerequisites"
  need docker "Install Docker Engine: https://docs.docker.com/engine/install/"
  docker compose version >/dev/null 2>&1 \
    || die "Docker Compose v2 is required (the 'docker compose' subcommand)."
  ok "docker compose"
  need poetry "Install Poetry: https://python-poetry.org/docs/#installation"
  check_python

  install_deps
  write_env

  # ---- start services --------------------------------------------------------
  step "Starting Postgres + Qdrant"
  docker compose up -d
  # Wait for Postgres to be truly ready. On first start the official image runs
  # initdb behind a temporary socket-only server, then restarts — so pg_isready
  # can race the schema apply. Reliable signal: the log line that appears after
  # "PostgreSQL init process complete" (or any ready line on existing volumes).
  printf '  waiting for Postgres'
  db_ready=0
  for i in $(seq 1 90); do
    logs="$(docker compose logs postgres 2>/dev/null)"
    if printf '%s\n' "$logs" | grep -q 'PostgreSQL init process complete'; then
      if printf '%s\n' "$logs" | sed -n '/PostgreSQL init process complete/,$p' \
           | grep -q 'database system is ready to accept connections'; then
        db_ready=1; printf '\n'; ok "Postgres ready (fresh init)"; break
      fi
    elif [[ "$i" -ge 6 ]] \
         && printf '%s\n' "$logs" | grep -q 'database system is ready to accept connections' \
         && ! printf '%s\n' "$logs" | grep -q 'shutting down'; then
      db_ready=1; printf '\n'; ok "Postgres ready (existing volume)"; break
    fi
    printf '.'; sleep 2
  done
  [[ "$db_ready" -eq 1 ]] \
    || die "Postgres did not become ready within 180s. Check 'docker compose logs postgres'."

  # ---- apply schema ----------------------------------------------------------
  step "Applying the constitutional schema"
  if docker compose exec -T postgres psql -U postgres -d core -tAc \
       "SELECT to_regclass('core.blackboard_entries')" 2>/dev/null \
       | grep -q blackboard_entries; then
    ok "schema already present — skipping"
  else
    schema_done=0
    for attempt in $(seq 1 8); do
      docker compose exec -T postgres psql -U postgres -d core \
        -c 'DROP SCHEMA IF EXISTS core CASCADE' >/dev/null 2>&1 || true
      if docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d core \
           < schema.sql >/dev/null 2>&1; then
        schema_done=1; ok "schema applied from schema.sql"; break
      fi
      sleep 3
    done
    [[ "$schema_done" -eq 1 ]] \
      || die "Schema apply failed after retries. Check 'docker compose logs postgres'."
  fi

  # ---- verify ----------------------------------------------------------------
  step "Verifying the install (offline audit — no services required)"
  if poetry run core-admin code audit --offline --severity block >/dev/null 2>&1; then
    ok "constitutional audit runs and the tree is clean"
  else
    warn "offline audit reported findings (that's fine — the demo will create and resolve one)"
  fi

  # ---- start API -------------------------------------------------------------
  step "Starting the CORE API"
  if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
    ok "API already running at http://${API_HOST}:${API_PORT}"
  else
    nohup poetry run uvicorn src.api.main:create_app --factory \
      --host "$API_HOST" --port "$API_PORT" --env-file .env \
      >>"$API_LOG" 2>&1 &
    echo $! > "$API_PID_FILE"
    printf '  waiting for the API'
    for i in $(seq 1 30); do
      if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
        printf '\n'; ok "API up (PID $(cat "$API_PID_FILE"), logs: ${API_LOG})"; break
      fi
      printf '.'; sleep 2
      [[ "$i" -lt 30 ]] || { printf '\n'; die "API did not respond within 60s. Check ${API_LOG}."; }
    done
  fi

  # ---- demo ------------------------------------------------------------------
  step "Showing you CORE govern itself"
  git config user.email >/dev/null 2>&1 || git config user.email "you@example.com"
  git config user.name  >/dev/null 2>&1 || git config user.name  "CORE User"
  CORE_API_HOST="$API_HOST" CORE_API_PORT="$API_PORT" bash scripts/demo.sh

  # ---- done ------------------------------------------------------------------
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
}

# ===========================================================================
# BARE PATH
# ===========================================================================
run_bare() {
  need() { command -v "$1" >/dev/null 2>&1 || die "Missing '$1'. $2"; ok "$1"; }

  step "Checking prerequisites"
  need poetry "Install Poetry: https://python-poetry.org/docs/#installation"
  check_python
  need psql "Install the PostgreSQL client: https://www.postgresql.org/download/"

  # Pre-flight: verify DB and Qdrant are reachable before touching anything.
  step "Verifying connectivity"
  psql "${DB_URL}" -c "SELECT 1" >/dev/null 2>&1 \
    || die "Cannot connect to DB at ${DB_URL}. Verify the URL and that the server is reachable."
  ok "Postgres reachable"
  curl -fsS "${QDRANT_URL}/collections" >/dev/null 2>&1 \
    || die "Cannot reach Qdrant at ${QDRANT_URL}. Verify the URL and that the server is running."
  ok "Qdrant reachable"

  install_deps
  write_env

  # ---- apply schema ----------------------------------------------------------
  step "Applying the constitutional schema"
  # Check if already applied (idempotent gate).
  already=$(psql "${DB_URL}" -tAc \
    "SELECT to_regclass('core.blackboard_entries')" 2>/dev/null || echo "")
  if [[ "$already" == "core.blackboard_entries" ]]; then
    ok "schema already present — skipping"
  else
    psql "${DB_URL}" -v ON_ERROR_STOP=1 < schema.sql \
      || die "Schema apply failed. Check that your DB role has CREATE privilege."
    ok "schema applied from schema.sql"
  fi

  # ---- write start.sh / stop.sh ----------------------------------------------
  step "Writing start.sh and stop.sh"

  cat > start.sh <<'STARTEOF'
#!/usr/bin/env bash
# Start the CORE API and daemon (bare mode — you supply the infra).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p var/run var/log
API_HOST="${CORE_API_HOST:-127.0.0.1}"
API_PORT="${CORE_API_PORT:-8000}"

echo "Starting CORE API..."
nohup poetry run uvicorn src.api.main:create_app --factory \
  --host "$API_HOST" --port "$API_PORT" --env-file .env \
  >> var/log/core-api.log 2>&1 &
echo $! > var/run/core-api.pid
echo "  API PID $(cat var/run/core-api.pid) — logs: var/log/core-api.log"

echo "Starting CORE daemon..."
nohup poetry run core-admin daemon start \
  >> var/log/core-daemon.log 2>&1 &
echo $! > var/run/core-daemon.pid
echo "  Daemon PID $(cat var/run/core-daemon.pid) — logs: var/log/core-daemon.log"

echo "CORE is running."
STARTEOF
  chmod +x start.sh
  ok "start.sh written"

  cat > stop.sh <<'STOPEOF'
#!/usr/bin/env bash
# Stop the CORE API and daemon.
set -euo pipefail
cd "$(dirname "$0")"
stop_pid() {
  local f="$1" name="$2"
  if [[ -f "$f" ]]; then
    pid=$(cat "$f")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "  stopped ${name} (PID ${pid})"
    else
      echo "  ${name} not running"
    fi
    rm -f "$f"
  else
    echo "  no PID file for ${name}"
  fi
}
stop_pid var/run/core-daemon.pid "daemon"
stop_pid var/run/core-api.pid    "API"
STOPEOF
  chmod +x stop.sh
  ok "stop.sh written"

  # ---- verify ----------------------------------------------------------------
  step "Verifying the install (offline audit)"
  if poetry run core-admin code audit --offline --severity block >/dev/null 2>&1; then
    ok "constitutional audit passes"
  else
    warn "offline audit reported findings — run 'poetry run core-admin code audit --offline' to inspect"
  fi

  # ---- done ------------------------------------------------------------------
  step "CORE is ready"
  cat <<EOF

  CORE is installed. Start it with:

    ./start.sh          # API + daemon
    ./stop.sh           # graceful shutdown

  Try it:
    poetry run core-admin code audit --offline      # offline audit, no services
    poetry run core-admin runtime dashboard         # situational awareness

  Configure an LLM in .env to enable autonomous code generation.

  Docs: https://dariusznewecki.github.io/CORE/
EOF
}

# ===========================================================================
# DISPATCH
# ===========================================================================
if [[ "$BARE" -eq 1 ]]; then
  run_bare
else
  run_docker
fi
