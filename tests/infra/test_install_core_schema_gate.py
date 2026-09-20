"""ADR-162 D2/D10 (U8a) -- install-core.sh decides from the schema STATE, read-only.

The installer used to test ``to_regclass('core.blackboard_entries')`` and, when
the table existed, print "schema already present -- skipping" and start
services -- against a v2.9.1 database, a half-loaded schema, or a ledger that
contradicts the schema alike. The Docker path additionally retried a failed
load with ``DROP SCHEMA IF EXISTS core CASCADE``.

Now both paths make one decision from two read-only facts -- whether a
``core`` namespace exists at all, and what the real ``core-admin database
status`` says -- and only a genuinely absent schema is ever written to
(``schema.sql`` in one transaction). Everything else is either "current,
continue" or "refuse before any service starts, never mutate".

These tests drive the **real installer** with fake ``poetry`` / ``psql`` /
``docker`` / ``curl`` / ``python3`` executables that record every invocation,
so the control flow of both paths is proven end to end without a database:
which state leads to a load, to a status check, to a refusal, and which
commands are never run. The schema-state conclusions themselves are backed by
real disposable-PostgreSQL tests in
``tests/shared/infrastructure/migrations/test_installer_schema_state_postgres.py``.

Credential hygiene as in ``test_install_core_db_url.py``: the fixture URL
carries a sentinel password that must never appear in installer output, and
assertions go through pre-computed booleans so a failure never prints it.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install-core.sh"
ENV_EXAMPLE = REPO / ".env.example"

SECRET = "s3cr3t-DO-NOT-LEAK-%40%26"
DB_URL = f"postgresql+asyncpg://user:{SECRET}@db.internal:5432/core"
QDRANT = "http://qdrant.internal:6333"

# Every fake reads its scripted behaviour from the environment and appends
# what it was asked to do to a log, one line per call. Knobs:
#   FAKE_CORE_NS   0|1     -> answer to the `core` namespace probe
#   FAKE_STATUS_RC 0|1|2   -> exit code of `core-admin database status`
#   FAKE_LOAD_FAIL 1       -> the atomic schema.sql load fails
#   FAKE_AUDIT     PASS|DEGRADED|FAIL|GARBAGE -> what `core-admin code audit
#                  --offline --format=json` emits at the verify step (the real
#                  offline audit is DEGRADED, exit 1, on a healthy tree; #907)
#   FAKE_DOCKER_DOWN 1     -> `docker info` fails (daemon not running)
#   REAL_PYTHON    path    -> interpreter `poetry run python` delegates to, so
#                  the verify step's JSON gate runs for real
_FAKES: dict[str, str] = {
    "python3": "#!/bin/bash\necho 3.12\n",
    "curl": "#!/bin/bash\nexit 0\n",
    "poetry": (
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'case "$*" in\n'
        '  "run core-admin database status")\n'
        '    printf "%s\\n" "status-url=${DATABASE_URL:-<unset>}" >> "$CALL_LOG"\n'
        '    echo "STATUS REPORT (fake) rc=${FAKE_STATUS_RC:-0}"\n'
        '    exit "${FAKE_STATUS_RC:-0}" ;;\n'
        '  "run core-admin code audit"*)\n'
        '    case "${FAKE_AUDIT:-DEGRADED}" in\n'
        '      PASS) printf \'{"verdict":"PASS","findings":[],"stats":{"skipped_blocking_rule_ids":[]}}\'; exit 0 ;;\n'
        '      DEGRADED) printf \'{"verdict":"DEGRADED","findings":[],"stats":{"skipped_blocking_rule_ids":["a.b","c.d","e.f"]}}\'; exit 1 ;;\n'
        '      FAIL) printf \'{"verdict":"FAIL","findings":[{"severity":"block"},{"severity":"block"}],"stats":{}}\'; exit 1 ;;\n'
        '      *) printf "not json"; exit 2 ;;\n'
        "    esac ;;\n"
        '  "run python -"*) shift 2; exec "$REAL_PYTHON" "$@" ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    ),
    "psql": (
        "#!/bin/bash\n"
        'printf "psql %s\\n" "$*" >> "$CALL_LOG"\n'
        "cat >/dev/null\n"
        'case "$*" in\n'
        '  *"SELECT 1"*) echo 1; exit 0 ;;\n'
        '  *pg_namespace*) echo "${FAKE_CORE_NS:-1}"; exit 0 ;;\n'
        '  *--single-transaction*) [ -n "${FAKE_LOAD_FAIL:-}" ] && exit 3; exit 0 ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    ),
    "docker": (
        "#!/bin/bash\n"
        'printf "docker %s\\n" "$*" >> "$CALL_LOG"\n'
        'case "$*" in\n'
        '  "compose version"|"compose up -d") exit 0 ;;\n'
        '  info) [ -n "${FAKE_DOCKER_DOWN:-}" ] && exit 1; exit 0 ;;\n'
        '  "compose logs postgres")\n'
        '    printf "PostgreSQL init process complete; ready for start up.\\n"\n'
        '    printf "database system is ready to accept connections\\n"; exit 0 ;;\n'
        '  *"SELECT 1"*) cat >/dev/null; echo 1; exit 0 ;;\n'
        '  *pg_namespace*) cat >/dev/null; echo "${FAKE_CORE_NS:-1}"; exit 0 ;;\n'
        '  *--single-transaction*) cat >/dev/null; [ -n "${FAKE_LOAD_FAIL:-}" ] && exit 3; exit 0 ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n"
    ),
}


def _workspace(tmp_path: Path) -> Path:
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(parents=True)
    for name, body in _FAKES.items():
        shim = shim_dir / name
        shim.write_text(body, encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    ws = tmp_path / "workspace"
    ws.mkdir()
    shutil.copy(INSTALLER, ws / "install-core.sh")
    shutil.copy(ENV_EXAMPLE, ws / ".env.example")
    (ws / "schema.sql").write_text("-- schema for the installer test\n", "utf-8")
    return ws


def _run(
    ws: Path,
    *args: str,
    core_ns: str = "1",
    status_rc: str = "0",
    load_fail: bool = False,
    audit: str = "DEGRADED",
    docker_down: bool = False,
) -> tuple[int, str, list[str]]:
    log = ws.parent / "calls.log"
    env = {
        **{k: v for k, v in os.environ.items() if k != "DATABASE_URL"},
        "PATH": os.pathsep.join([str(ws.parent / "bin"), os.environ.get("PATH", "")]),
        "CALL_LOG": str(log),
        "FAKE_CORE_NS": core_ns,
        "FAKE_STATUS_RC": status_rc,
        "FAKE_LOAD_FAIL": "1" if load_fail else "",
        "FAKE_AUDIT": audit,
        "FAKE_DOCKER_DOWN": "1" if docker_down else "",
        "REAL_PYTHON": sys.executable,
    }
    proc = subprocess.run(
        ["bash", str(ws / "install-core.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=ws,
    )
    calls = log.read_text("utf-8").splitlines() if log.exists() else []
    return proc.returncode, proc.stdout + proc.stderr, calls


def _bare(ws: Path, **kw: object) -> tuple[int, str, list[str]]:
    return _run(ws, "--bare", "--db-url", DB_URL, "--qdrant-url", QDRANT, **kw)  # type: ignore[arg-type]


def _status_calls(calls: list[str]) -> list[str]:
    return [c for c in calls if c == "run core-admin database status"]


def _loads(calls: list[str]) -> list[str]:
    return [c for c in calls if "--single-transaction" in c]


def _never_mutates(calls: list[str]) -> bool:
    forbidden = (
        "database migrate",
        "adopt-baseline",
        "--write",
        "DROP SCHEMA",
        "CASCADE",
    )
    return not any(f in c for c in calls for f in forbidden)


def _no_service_started(out: str, calls: list[str]) -> bool:
    started = (
        any(("uvicorn" in c) or ("daemon start" in c) for c in calls)
        or "CORE is installed and running" in out
        or "CORE is ready" in out
    )
    return not started


# ── fresh database: load once, atomically, then prove the ledger ────────────


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: 8f75cfd3-360f-4af6-9fc7-6c70c9857985
def test_fresh_database_loads_schema_once_atomically_then_verifies_current(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = (
        _bare(ws, core_ns="0") if path == "bare" else _run(ws, core_ns="0")
    )
    assert code == 0, "fresh install did not succeed (output redacted)"
    loads = _loads(calls)
    assert len(loads) == 1 and "ON_ERROR_STOP=1" in loads[0]
    # The load happens BEFORE the status check, which then must be exit 0.
    order = [
        c
        for c in calls
        if "--single-transaction" in c or c == "run core-admin database status"
    ]
    assert order[0] == loads[0] and order[1] == "run core-admin database status"
    assert len(_status_calls(calls)) == 1
    assert _never_mutates(calls)
    seen = (
        "this is a fresh database" in out
        and "schema applied from schema.sql" in out
        and "migration ledger is current" in out
    )
    assert seen, "fresh path did not report load + verified ledger"
    leaked = SECRET in out
    assert not leaked


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: df01d127-2331-454a-be31-4a123caeac99
def test_failed_fresh_load_refuses_without_retry_or_drop(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    if path == "bare":
        code, out, calls = _bare(ws, core_ns="0", load_fail=True)
    else:
        code, out, calls = _run(ws, core_ns="0", load_fail=True)
    assert code == 1
    assert len(_loads(calls)) == 1, "a failed load must not be retried"
    assert _never_mutates(calls), "DROP SCHEMA / CASCADE must never run"
    assert _status_calls(calls) == [], "no status check after a failed load"
    assert _no_service_started(out, calls)
    seen = "rolled back" in out and "schema-apply.log" in out
    assert seen
    leaked = SECRET in out
    assert not leaked


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: ba84b1d0-0f27-4548-af73-5a8be25855d0
def test_fresh_load_whose_ledger_is_not_current_is_a_refused_packaging_defect(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    if path == "bare":
        code, out, calls = _bare(ws, core_ns="0", status_rc="2")
    else:
        code, out, calls = _run(ws, core_ns="0", status_rc="2")
    assert code == 1
    assert len(_loads(calls)) == 1 and len(_status_calls(calls)) == 1
    assert _never_mutates(calls) and _no_service_started(out, calls)
    seen = "packaging defect" in out
    assert seen


# ── existing database: the real status decides ──────────────────────────────


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: 722e7c29-d549-40d2-a513-299bad6e0705
def test_existing_current_database_is_not_reloaded_and_continues(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _bare(ws) if path == "bare" else _run(ws)
    assert code == 0, "install against a current database did not succeed"
    assert _loads(calls) == [], "schema.sql must not be reloaded"
    assert len(_status_calls(calls)) == 1
    assert _never_mutates(calls)
    seen = "a CORE schema is present" in out and "database is current" in out
    assert seen
    gone = "already present" in out and "skipping" in out
    assert not gone, "the old 'present -- skipping' assumption is back"


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: 671c44ac-9b95-4dde-816d-4762f3dffdb0
def test_existing_non_current_database_is_refused_before_any_service(
    tmp_path: Path, path: str
) -> None:
    """status exit 2 covers pending, empty/unledgered, contradictory and
    partial/unrecognised schemas alike -- the installer shows the diagnostic
    and stops. It does not guess a repair and does not start anything."""
    ws = _workspace(tmp_path)
    if path == "bare":
        code, out, calls = _bare(ws, status_rc="2")
    else:
        code, out, calls = _run(ws, status_rc="2")
    assert code == 1
    assert _loads(calls) == []
    assert len(_status_calls(calls)) == 1
    assert _never_mutates(calls)
    assert _no_service_started(out, calls)
    assert "STATUS REPORT (fake)" in out, "the real diagnostic must be shown"
    seen = (
        "not current" in out
        and "no service was started" in out
        and "operator-run" in out
        and "Upgrading an existing CORE database" in out
        and "core-admin database status" in out
    )
    assert seen
    gone = "skipping" in out
    assert not gone
    # D12 §1: the complete repair recipe is not printed.
    recipe = "adopt-baseline" in out or "migrate --write" in out
    assert not recipe
    leaked = SECRET in out
    assert not leaked
    if path == "bare":
        assert not (ws / "start.sh").exists(), "start.sh written despite refusal"


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: 1041a373-0064-4938-b2ba-eb3b56b37f29
def test_status_check_failure_exits_non_zero_without_mutation(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    if path == "bare":
        code, out, calls = _bare(ws, status_rc="1")
    else:
        code, out, calls = _run(ws, status_rc="1")
    assert code == 1
    assert _loads(calls) == [] and _never_mutates(calls)
    assert _no_service_started(out, calls)
    seen = "status check itself failed" in out
    assert seen


# ── bare mode inspects the supplied database, not a stale .env ──────────────


# ID: 23b1e3bc-58d0-4de9-a6f8-cfdcb3a3bbe1
def test_bare_status_check_uses_the_supplied_db_url_even_with_a_foreign_env(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    (ws / ".env").write_text(
        "DATABASE_URL=postgresql+asyncpg://other:pw@elsewhere:5432/notcore\n", "utf-8"
    )
    code, out, calls = _bare(ws)
    assert code == 0
    handed = [c for c in calls if c.startswith("status-url=")]
    assert handed == [f"status-url={DB_URL}"]
    warned = "names a DATABASE_URL different from --db-url" in out
    assert warned
    leaked = SECRET in out or "elsewhere" in out
    assert not leaked, "installer output contains a database URL"


# ID: 4fad4d54-b6d0-4a2f-bf50-25dd2cc935fb
def test_docker_status_check_does_not_override_the_env_it_wrote(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, _, calls = _run(ws)
    assert code == 0
    handed = [c for c in calls if c.startswith("status-url=")]
    assert handed == ["status-url=<unset>"]  # the runtime's own .env applies


# ── verify step: JSON verdict, not exit code; refusals describe state ───────
#
# The offline audit exits 1 on a healthy tree (DEGRADED: DB/graph-dependent
# blocking rules are not evaluable without services; #907). The installer must
# read the JSON verdict like CI does (core-ci.yml), accept PASS and DEGRADED,
# and fail closed on FAIL / unreadable output -- saying what it already
# started.


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: 66b3e1d2-a474-487d-a639-43de3d72cd46
def test_degraded_audit_verdict_is_reported_as_clean_not_findings(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    code, out, _ = _bare(ws) if path == "bare" else _run(ws)
    assert code == 0
    assert "tree clean (0 blocking findings)" in out
    assert "3 blocking rule(s) need running services" in out
    assert "reported findings" not in out


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: d9a8bc1f-86cd-4977-ae27-06bac2955b13
def test_pass_audit_verdict_is_ok(tmp_path: Path, path: str) -> None:
    ws = _workspace(tmp_path)
    code, out, _ = _bare(ws, audit="PASS") if path == "bare" else _run(ws, audit="PASS")
    assert code == 0
    assert "constitutional audit: PASS" in out


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: c88762bc-3909-425d-8ebe-76198307de48
def test_fail_audit_verdict_refuses_and_describes_what_is_running(
    tmp_path: Path, path: str
) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = (
        _bare(ws, audit="FAIL") if path == "bare" else _run(ws, audit="FAIL")
    )
    assert code == 1
    assert "offline audit FAIL: 2 blocking finding(s)" in out
    assert _no_service_started(out, calls)
    assert "please report it" in out
    if path == "docker":
        assert "Postgres + Qdrant are running" in out
        assert "docker compose down" in out
    else:
        assert "nothing was started by this installer" in out


@pytest.mark.parametrize("path", ["bare", "docker"])
# ID: fc791c41-3997-46ef-aa01-8afcd9755872
def test_unreadable_audit_output_fails_closed(tmp_path: Path, path: str) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = (
        _bare(ws, audit="GARBAGE") if path == "bare" else _run(ws, audit="GARBAGE")
    )
    assert code == 1
    assert "no recognisable verdict" in out
    assert _no_service_started(out, calls)


# ── Docker preflight: the daemon must be reachable, not just installed ──────


# ID: 0d27ae25-f506-4dd8-97b4-ce018be6b42b
def test_docker_daemon_down_refuses_at_preflight_before_compose_up(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(ws, docker_down=True)
    assert code == 1
    assert "daemon is not running" in out
    assert not any(c.startswith("docker compose up") for c in calls)
    assert _loads(calls) == [] and _never_mutates(calls)


# ── the installer text itself ───────────────────────────────────────────────


# ID: cab3ead4-6e80-4eaf-aba1-884856c8cd9b
def test_installer_source_has_no_drop_schema_and_no_mutation_commands() -> None:
    src = INSTALLER.read_text("utf-8")
    code_lines = [
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    ]
    joined = "\n".join(code_lines)
    assert "DROP SCHEMA" not in joined and "CASCADE" not in joined
    assert "database migrate" not in joined and "adopt-baseline" not in joined
    assert "--write" not in joined
    assert "--single-transaction" in joined and "ON_ERROR_STOP=1" in joined
    assert "core-admin database status" in joined


# ID: 26454655-d287-496d-b807-cca3abbb1ca7
def test_help_states_the_rerun_contract() -> None:
    proc = subprocess.run(
        ["bash", str(INSTALLER), "--help"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert "Re-run is safe against a CURRENT database" in proc.stdout
    assert "REFUSED before any service starts" in proc.stdout
    assert "never migrates" in proc.stdout
