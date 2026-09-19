# tests/shared/infrastructure/migrations/test_installer_schema_state_postgres.py
"""ADR-162 D2/D10 (U8a) -- the installer's schema-state decision on real databases.

``tests/infra/test_install_core_schema_gate.py`` proves the control flow of
both installer paths with fake executables. This module proves the
*conclusions* against a disposable PostgreSQL: the real ``install-core.sh``
(bare path) with the real ``psql`` and the real ``core-admin database status``
-- ``poetry`` is shimmed only to dispatch ``poetry run core-admin`` to this
environment's entry point and to make ``poetry install`` a no-op -- against
databases in every state the gate distinguishes:

* genuinely empty            -> schema.sql loaded in one transaction, ledger
                                current, installer continues;
* current                    -> nothing reloaded, nothing recorded, continues;
* v2.9.1 / v2.10.1, unledgered  -> refused; the database is untouched;
* ledgered with pending      -> refused; no ledger row added;
* recorded-but-probe-fails   -> refused (contradiction);
* partial/unrecognised       -> refused; the foreign object survives (no DROP);
* poisoned schema.sql        -> the load rolls back, no ``core`` namespace, refused.

No path ever runs ``database migrate``, ``--adopt-baseline`` or ``--write``.
The server password is a random secret; it must never appear in output.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_service import adopt_baseline


if TYPE_CHECKING:
    from .conftest import DisposablePostgres, FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
INSTALLER = REPO_ROOT / "install-core.sh"
SCHEMA_SQL = REPO_ROOT / "schema.sql"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schema"
SCHEMA_V2_9_1 = FIXTURES / "schema-v2.9.1.sql"
SCHEMA_V2_10_1 = FIXTURES / "schema-v2.10.1.sql"
QDRANT = "http://qdrant.invalid:6333"

_CORE_NS = "select count(*) from pg_namespace where nspname = 'core'"


def _core_admin_exe() -> Path:
    exe = Path(sys.executable).parent / "core-admin"
    if not exe.is_file():
        pytest.skip("core-admin entry point not installed next to the interpreter")
    return exe


def _workspace(tmp_path: Path, schema_sql: Path = SCHEMA_SQL) -> Path:
    """A throwaway checkout: the real installer, the real schema.sql, fakes for
    everything that is not the database."""
    exe = _core_admin_exe()
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(parents=True)
    fakes = {
        "python3": "#!/bin/bash\necho 3.12\n",
        "curl": "#!/bin/bash\nexit 0\n",
        "poetry": (
            "#!/bin/bash\n"
            'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
            'if [ "$1" = "run" ] && [ "$2" = "core-admin" ]; then shift 2; '
            f'exec "{exe}" "$@"; fi\n'
            "exit 0\n"
        ),
    }
    for name, body in fakes.items():
        shim = shim_dir / name
        shim.write_text(body, encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    ws = tmp_path / "workspace"
    ws.mkdir()
    shutil.copy(INSTALLER, ws / "install-core.sh")
    shutil.copy(REPO_ROOT / ".env.example", ws / ".env.example")
    shutil.copy(schema_sql, ws / "schema.sql")
    return ws


def _install(ws: Path, db_url: str) -> tuple[int, str, list[str]]:
    log = ws.parent / "calls.log"
    env = {
        **{
            k: v
            for k, v in os.environ.items()
            if k not in {"DATABASE_URL", "PYTEST_CURRENT_TEST"}
        },
        "PATH": os.pathsep.join([str(ws.parent / "bin"), os.environ.get("PATH", "")]),
        "CALL_LOG": str(log),
    }
    proc = subprocess.run(
        [
            "bash",
            str(ws / "install-core.sh"),
            "--bare",
            "--db-url",
            db_url,
            "--qdrant-url",
            QDRANT,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=ws,
        timeout=600,
    )
    calls = log.read_text("utf-8").splitlines() if log.exists() else []
    return proc.returncode, proc.stdout + proc.stderr, calls


def _never_mutates(calls: list[str]) -> bool:
    return not any(
        f in c for c in calls for f in ("database migrate", "adopt-baseline", "--write")
    )


def _clean(out: str, server: DisposablePostgres) -> bool:
    """True when the output carries neither the password nor a URL."""
    return server.password not in out and "postgresql://" not in out


# ── fresh, current ──────────────────────────────────────────────────────────


# ID: 804564aa-4dea-485f-bbd8-7a3ce7de22d3
async def test_empty_database_gets_schema_sql_atomically_and_a_current_ledger(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
) -> None:
    db = fresh_database
    assert await db.scalar(_CORE_NS) == 0
    ws = _workspace(tmp_path)
    code, out, calls = _install(ws, db.url)
    assert code == 0, "fresh bare install did not succeed (output redacted)"
    assert await db.scalar(_CORE_NS) == 1
    assert len(await db.ledger_rows()) == len(load_manifest().order)
    assert calls.count("run core-admin database status") == 1
    assert _never_mutates(calls)
    seen = (
        "this is a fresh database" in out
        and "schema applied from schema.sql" in out
        and "migration ledger is current" in out
        and "CORE is ready" in out
    )
    assert seen
    assert _clean(out, disposable_postgres)
    assert (ws / "start.sh").exists()


# ID: a6943b5e-dee4-48e5-b582-a08b05e37261
async def test_current_database_is_neither_reloaded_nor_re_recorded(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_SQL)
    before = await db.scalar(
        "select string_agg(id || ':' || applied_at::text, ',' order by id) "
        "from core._migrations"
    )
    ws = _workspace(tmp_path)
    code, out, calls = _install(ws, db.url)
    assert code == 0, "rerun against a current database did not succeed"
    after = await db.scalar(
        "select string_agg(id || ':' || applied_at::text, ',' order by id) "
        "from core._migrations"
    )
    assert after == before, "the ledger changed on a rerun"
    assert calls.count("run core-admin database status") == 1
    assert _never_mutates(calls)
    seen = "a CORE schema is present" in out and "database is current" in out
    assert seen
    assert _clean(out, disposable_postgres)


# ── existing, not current: refused, untouched ───────────────────────────────


async def _assert_refused_untouched(
    db: FreshDatabase, server: DisposablePostgres, ws: Path, before_ledger: dict
) -> str:
    code, out, calls = _install(ws, db.url)
    assert code == 1
    assert await db.ledger_rows() == before_ledger, "the ledger was touched"
    assert _never_mutates(calls)
    assert calls.count("run core-admin database status") == 1
    refused = (
        "not current" in out
        and "no service was started" in out
        and "operator-run" in out
        and "core-admin database status" in out
    )
    assert refused, "refusal text missing"
    # D12 §1: the installer's own refusal text carries no repair recipe (the
    # status report above it is the CLI's own diagnostic, unchanged here).
    refusal = out.split("refusing to continue", 1)[1]
    recipe = "adopt-baseline" in refusal or "--write" in refusal
    assert not recipe, "the refusal text publishes the repair recipe"
    assert not (ws / "start.sh").exists(), "start.sh written despite refusal"
    assert _clean(out, server)
    return out


# ID: 1b0dd1fb-bb3a-464e-9fb5-b09a5c78f1ec
@pytest.mark.parametrize("fixture", ["v2.9.1", "v2.10.1"])
async def test_released_baseline_with_empty_ledger_is_refused_untouched(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
    fixture: str,
) -> None:
    db = fresh_database
    await db.load_schema(FIXTURES / f"schema-{fixture}.sql")
    tables_before = await db.scalar(
        "select count(*) from information_schema.tables where table_schema = 'core'"
    )
    ws = _workspace(tmp_path)
    await _assert_refused_untouched(db, disposable_postgres, ws, {})
    assert (
        await db.scalar(
            "select count(*) from information_schema.tables where table_schema = 'core'"
        )
        == tables_before
    )


# ID: ca55c0a5-6af7-4065-bf74-ad4fd517b613
async def test_ledgered_database_with_pending_migrations_is_refused(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_V2_9_1)
    await adopt_baseline("v2.9.1", write=True, session_factory=db.session_factory)
    before = await db.ledger_rows()
    assert before  # ledgered through the baseline, the rest pending
    ws = _workspace(tmp_path)
    out = await _assert_refused_untouched(db, disposable_postgres, ws, before)
    assert "Pending migrations" in out


# ID: a8e3b42f-da03-4bcf-8984-58223db7699b
async def test_recorded_migration_whose_probe_fails_is_refused(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
) -> None:
    """The ledger claims 20260919d (display_name) but the column is gone: a
    ledger/schema contradiction. The installer shows it and stops."""
    db = fresh_database
    await db.load_schema(SCHEMA_SQL)
    await db.execute("alter table core.users drop column display_name")
    before = await db.ledger_rows()
    ws = _workspace(tmp_path)
    out = await _assert_refused_untouched(db, disposable_postgres, ws, before)
    assert "contradiction" in out and "20260919d_users_display_name.sql" in out


# ID: 379e589f-6ad0-4ddb-9959-5caa3c759cf4
async def test_partial_unrecognised_core_schema_is_refused_without_drop(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
) -> None:
    db = fresh_database
    await db.execute("create schema core")
    await db.execute("create table core.not_ours (x int)")
    await db.execute("insert into core.not_ours values (42)")
    ws = _workspace(tmp_path)
    await _assert_refused_untouched(db, disposable_postgres, ws, {})
    # Nothing dropped, nothing loaded: the foreign object is exactly as it was.
    assert await db.scalar("select x from core.not_ours") == 42
    assert await db.scalar("select to_regclass('core.blackboard_entries') is null")
    assert await db.scalar("select to_regclass('core._migrations') is null")


# ── a failed fresh load leaves nothing behind ───────────────────────────────


# ID: 66594777-a474-48a3-8336-a90c07ac2157
async def test_poisoned_schema_load_rolls_back_completely_and_refuses(
    fresh_database: FreshDatabase,
    disposable_postgres: DisposablePostgres,
    tmp_path: Path,
) -> None:
    db = fresh_database
    poisoned = tmp_path / "poisoned-schema.sql"
    poisoned.write_text(
        SCHEMA_SQL.read_text("utf-8") + "\nSELECT 1/0;  -- fails at the very end\n",
        "utf-8",
    )
    ws = _workspace(tmp_path, schema_sql=poisoned)
    code, out, calls = _install(ws, db.url)
    assert code == 1
    assert await db.scalar(_CORE_NS) == 0, "a partial CORE schema was left behind"
    assert "run core-admin database status" not in calls
    assert _never_mutates(calls)
    seen = "rolled back" in out and "still holds no CORE schema" in out
    assert seen
    assert not (ws / "start.sh").exists()
    assert _clean(out, disposable_postgres)
    apply_log = (ws / "var" / "logs" / "schema-apply.log").read_text("utf-8")
    assert "division by zero" in apply_log
    assert disposable_postgres.password not in apply_log
