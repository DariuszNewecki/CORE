#!/usr/bin/env bash
#
# install-core.sh — the one-command on-ramp to CORE.
#
# Two modes:
#
#   ./install-core.sh                      # Docker path (default)
#       Requires: docker, docker compose v2, poetry, python 3.12+
#       Brings up Postgres + Qdrant via Docker, loads the schema, and starts
#       the CORE API. Finishes by printing the opt-in consequence-chain demo
#       command (ADR-155 D1: installation never runs the demo automatically).
#
#   ./install-core.sh --bare \             # Bare path
#       --db-url  "postgresql+asyncpg://user:pass@host:5432/dbname" \
#       --qdrant-url "http://host:6333"
#       Requires: python 3.12+, poetry, psql client, reachable DB + Qdrant
#       Sets up the Python environment, loads the schema into a genuinely
#       empty database (or verifies an existing one is current), writes start.sh /
#       stop.sh, and prints next steps. You manage infra; CORE manages itself.
#       A plain postgresql:// URL is accepted and normalised to the
#       postgresql+asyncpg:// form CORE's async runtime requires (ADR-162 U1).
#
# Re-run is safe against a CURRENT database — steps that have already happened
# are detected and skipped. A database whose CORE schema is not current
# (pending migrations, an empty ledger, a ledger/schema contradiction, or a
# partial/unrecognised schema) is REFUSED before any service starts: the
# installer never migrates, never adopts a baseline and never drops a schema
# (ADR-162 D2/D10, U8a). Diagnose with: core-admin database status
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
API_LOG="var/logs/core-api.log"
DAEMON_LOG="var/logs/core-daemon.log"

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
      sed -n '2,31p' "$0" | sed 's/^#//' | sed 's/^ //'
      exit 0 ;;
    *) die "Unknown argument: $1. Run with --help for usage." ;;
  esac
done

if [[ "$BARE" -eq 1 ]]; then
  [[ -n "$DB_URL" ]]     || die "--bare requires --db-url postgresql+asyncpg://user:pass@host:5432/dbname"
  [[ -n "$QDRANT_URL" ]] || die "--bare requires --qdrant-url http://host:6333"
fi

# ---- database URL normalisation (ADR-162 D10, U1) --------------------------
# One operator-supplied URL feeds two consumers with incompatible schemes:
#   * CORE's runtime (async SQLAlchemy + asyncpg) requires postgresql+asyncpg://
#     — a plain postgresql:// makes the engine import psycopg2 and fail;
#   * psql (libpq) requires postgresql:// and treats postgresql+asyncpg://...
#     as a database *name*.
# Only the scheme prefix is rewritten; every byte after :// is untouched.
# Both forms are accepted; each is idempotent. Any other scheme (e.g.
# postgres://) passes through unchanged, exactly as before.
to_async_db_url() {
  case "$1" in
    postgresql://*) printf '%s' "postgresql+asyncpg://${1#postgresql://}" ;;
    *)              printf '%s' "$1" ;;
  esac
}
to_libpq_db_url() {
  case "$1" in
    postgresql+asyncpg://*) printf '%s' "postgresql://${1#postgresql+asyncpg://}" ;;
    *)                      printf '%s' "$1" ;;
  esac
}
DB_URL_ASYNC="$(to_async_db_url "$DB_URL")"   # persisted to .env for the runtime
DB_URL_LIBPQ="$(to_libpq_db_url "$DB_URL")"   # handed to psql only

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
# set_env_var NAME VALUE FILE — replace every "NAME=..." line in FILE with
# "NAME=VALUE", copying VALUE byte-for-byte. (A sed replacement would
# reinterpret '&' and '\' — which query strings legitimately contain.)
set_env_var() {
  local name="$1" value="$2" file="$3" line
  local tmp="${file}.tmp.$$"
  : > "$tmp"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "${name}="* ]]; then
      printf '%s=%s\n' "$name" "$value" >> "$tmp"
    else
      printf '%s\n' "$line" >> "$tmp"
    fi
  done < "$file"
  mv "$tmp" "$file"
}

write_env() {
  step "Configuring environment"
  if [[ -f .env ]]; then
    ok ".env already exists — leaving it untouched"
  else
    [[ -f .env.example ]] || die ".env.example not found — is this a complete CORE checkout?"
    cp .env.example .env
    # Patch DATABASE_URL and QDRANT_URL for the bare path
    if [[ "$BARE" -eq 1 ]]; then
      # Replace placeholder values with the supplied URLs. The runtime gets
      # the async scheme (see "database URL normalisation" above).
      set_env_var DATABASE_URL "$DB_URL_ASYNC" .env
      set_env_var QDRANT_URL "$QDRANT_URL" .env
      ok "created .env from .env.example with your DB + Qdrant URLs"
    else
      ok "created .env from .env.example (defaults are demo-ready; no API key needed)"
    fi
  fi
  mkdir -p var/run var/logs
}

# env_file_value NAME — the value of NAME= in .env, or empty. Never printed.
env_file_value() {
  local name="$1" line
  [[ -f .env ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "${name}="* ]]; then printf '%s' "${line#*=}"; return 0; fi
  done < .env
}

# ---- schema-state gate (ADR-162 D2/D10, U8a) --------------------------------
# One read-only decision shared by both paths. The database is in exactly one
# of three states, and only the first one is ever written to:
#
#   absent   — no `core` namespace exists at all (schema.sql is what creates
#              it). schema.sql is loaded in ONE transaction: a failed load
#              leaves nothing behind and the installer refuses. There is no
#              drop-and-retry. The real read-only `core-admin database status`
#              then has to report CURRENT (exit 0) — a fresh install visibly
#              proves its migration ledger is complete.
#   current  — a `core` namespace exists and `core-admin database status`
#              reports CURRENT: continue. schema.sql is not reloaded and the
#              ledger is not touched.
#   other    — a `core` namespace exists but status is not CURRENT (pending
#              migrations, an empty/unledgered schema, a ledger/schema
#              contradiction, a partial or unrecognised schema) or the check
#              itself cannot run: the real diagnostic is shown and the
#              installer exits non-zero BEFORE any API or daemon is started.
#              It never runs `database migrate`, `--adopt-baseline` or any
#              other mutation, and never guesses a repair.
#
# $1 — a function that runs one read-only SQL query and prints its scalar
#      result (`psql -tAc` semantics); $2 — a function that loads schema.sql
#      atomically. Each path supplies its own pair (docker compose exec vs.
#      the operator's --db-url).
CORE_NAMESPACE_PROBE="SELECT count(*) FROM pg_namespace WHERE nspname = 'core'"
SCHEMA_APPLY_LOG="var/logs/schema-apply.log"

# The real read-only status check, in the mode's own database. In bare mode
# the supplied --db-url is exported for the check so a pre-existing, unrelated
# .env cannot redirect it (a process-environment DATABASE_URL survives the
# dotenv cascade, #845). Never echoes the URL.
run_status_check() {
  if [[ "$BARE" -eq 1 ]]; then
    DATABASE_URL="$DB_URL_ASYNC" poetry run core-admin database status
  else
    poetry run core-admin database status
  fi
}

refuse_not_current() {
  printf '\n%s✗ The database already holds a CORE schema that is not current — refusing to continue.%s\n' "$R" "$X" >&2
  cat >&2 <<EOF
  The status report above is the diagnosis (pending migrations, an empty
  ledger, a ledger/schema contradiction, or a partial/unrecognised schema).
  Nothing was changed and no service was started. The installer never
  migrates, adopts a baseline or drops a schema.

  Upgrading a database created by a released version (v2.9.1, v2.10.1) is
  not yet supported: it must wait for the Governor-authorised 2.10.2 release
  and its published procedure (ADR-162, G11). Until then, do not start CORE
  against this database.

  Diagnose again at any time (read-only):  poetry run core-admin database status
EOF
  exit 1
}

schema_state_gate() {
  local query_fn="$1" load_fn="$2" present rc
  step "Checking the database schema state (read-only)"
  present="$("$query_fn" "$CORE_NAMESPACE_PROBE" 2>/dev/null | tr -d '[:space:]')" \
    || die "Could not inspect the database schema state. Nothing was changed; no service was started."
  case "$present" in
    0)
      ok "no CORE schema present — this is a fresh database"
      step "Applying the constitutional schema (one transaction)"
      if "$load_fn"; then
        ok "schema applied from schema.sql"
      else
        die "Schema load failed and was rolled back — the database still holds no CORE schema. Nothing was started. Details: ${SCHEMA_APPLY_LOG}"
      fi
      step "Verifying the migration ledger of the fresh install (read-only)"
      rc=0; run_status_check || rc=$?
      [[ "$rc" -eq 0 ]] \
        || die "A fresh schema.sql load did not produce a current ledger (status exit ${rc}). This is a packaging defect — do not start CORE against this database."
      ok "migration ledger is current — verified by 'core-admin database status'"
      ;;
    1)
      ok "a CORE schema is present — verifying it is current (never reloaded, never migrated)"
      rc=0; run_status_check || rc=$?
      case "$rc" in
        0) ok "database is current — continuing" ;;
        2) refuse_not_current ;;
        *) die "The schema status check itself failed (exit ${rc}). Nothing was changed; no service was started. Run 'poetry run core-admin database status' to see why." ;;
      esac
      ;;
    *)
      die "Unexpected schema probe result. Nothing was changed; no service was started."
      ;;
  esac
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

  # The log signal above can still precede the first accepted connection;
  # confirm with a real query before deciding anything about the schema.
  printf '  confirming a connection'
  db_ok=0
  for i in $(seq 1 30); do
    if docker compose exec -T postgres psql -U postgres -d core -tAc 'SELECT 1' 2>/dev/null \
         | grep -q '^1$'; then
      db_ok=1; printf '\n'; ok "Postgres accepting connections"; break
    fi
    printf '.'; sleep 2
  done
  [[ "$db_ok" -eq 1 ]] \
    || die "Postgres is not accepting connections. Check 'docker compose logs postgres'."

  # ---- schema state (read-only decision; see schema_state_gate) --------------
  docker_db_query() {
    docker compose exec -T postgres psql -U postgres -d core -tAc "$1"
  }
  docker_db_load_schema() {
    # One transaction: either the whole schema lands or nothing does.
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 --single-transaction -q \
      -U postgres -d core < schema.sql > "$SCHEMA_APPLY_LOG" 2>&1
  }
  schema_state_gate docker_db_query docker_db_load_schema

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

  # ---- done ------------------------------------------------------------------
  # ADR-155 D1: installation must NOT run the demo. The isolated
  # consequence-chain demo is offered as an explicit, opt-in command below — it
  # spins up its own disposable infrastructure and never touches this checkout.
  step "CORE is yours"
  cat <<EOF

  CORE is installed and running.

  See CORE govern itself, end to end, in one isolated run (opt-in, needs Docker):
    poetry run core-admin demo consequence-chain

  Try it yourself:
    poetry run core-admin code audit --offline      # audit this repo, no services
    poetry run core-admin runtime dashboard         # governor situational awareness

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
  # The URL carries credentials — never echo it in an error.
  psql "${DB_URL_LIBPQ}" -c "SELECT 1" >/dev/null 2>&1 \
    || die "Cannot connect to the database with the supplied --db-url. Verify the URL and that the server is reachable."
  ok "Postgres reachable"
  curl -fsS "${QDRANT_URL}/collections" >/dev/null 2>&1 \
    || die "Cannot reach Qdrant at ${QDRANT_URL}. Verify the URL and that the server is running."
  ok "Qdrant reachable"

  install_deps
  write_env

  # A pre-existing .env is left untouched (above) — but start.sh's runtime
  # reads it. Say so when it names a different database than --db-url; the
  # schema check below inspects --db-url, as asked. Values are never printed.
  if [[ -n "$(env_file_value DATABASE_URL)" && "$(env_file_value DATABASE_URL)" != "$DB_URL_ASYNC" ]]; then
    warn "the existing .env names a DATABASE_URL different from --db-url; the schema check uses --db-url, start.sh will use .env"
  fi

  # ---- schema state (read-only decision; see schema_state_gate) --------------
  bare_db_query() {
    psql "${DB_URL_LIBPQ}" -tAc "$1"
  }
  bare_db_load_schema() {
    # One transaction: either the whole schema lands or nothing does. Output
    # goes to the log — psql's messages must never carry the URL to the terminal.
    psql "${DB_URL_LIBPQ}" -v ON_ERROR_STOP=1 --single-transaction -q -f schema.sql \
      > "$SCHEMA_APPLY_LOG" 2>&1
  }
  schema_state_gate bare_db_query bare_db_load_schema

  # ---- write start.sh / stop.sh ----------------------------------------------
  step "Writing start.sh and stop.sh"

  cat > start.sh <<'STARTEOF'
#!/usr/bin/env bash
# Start the CORE API and daemon (bare mode — you supply the infra).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p var/run var/logs
API_HOST="${CORE_API_HOST:-127.0.0.1}"
API_PORT="${CORE_API_PORT:-8000}"

echo "Starting CORE API..."
nohup poetry run uvicorn src.api.main:create_app --factory \
  --host "$API_HOST" --port "$API_PORT" --env-file .env \
  >> var/logs/core-api.log 2>&1 &
echo $! > var/run/core-api.pid
echo "  API PID $(cat var/run/core-api.pid) — logs: var/logs/core-api.log"

echo "Starting CORE daemon..."
nohup poetry run core-admin daemon start \
  >> var/logs/core-daemon.log 2>&1 &
echo $! > var/run/core-daemon.pid
echo "  Daemon PID $(cat var/run/core-daemon.pid) — logs: var/logs/core-daemon.log"

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
