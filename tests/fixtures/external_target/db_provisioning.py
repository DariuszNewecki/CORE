"""Disposable, local, hermetic PostgreSQL provisioning for Unit D.

Reuses CORE's own established hermetic-database mechanism -- the same
``postgres:16`` image and "schema.sql is canonical for a fresh install"
model ``docker-compose.test.yml`` already documents for CI ("Schema
source: schema.sql at repo root (canonical per #521)") -- but for a
throwaway, uniquely named database per run, never the shared ``core_test``.

CORE's own ``.env.test`` DATABASE_URL points at a LAN Postgres host; that
host is unreachable from this environment (confirmed before writing this
module). A local, disposable Docker container is the same fallback
CORE's own CI already documents for a from-scratch install -- not a novel
mechanism invented for Unit D.

Migration model: this loads ``schema.sql`` directly (a fresh install has
a current schema and an empty ledger, per ``migrate.py``'s own module
docstring), then calls the real, unmodified
``shared.infrastructure.repositories.db.migration_service.
bootstrap_migrations()`` to seed the ``core._migrations`` ledger, followed
by ``migrate_db(apply=False)`` to confirm nothing is left pending. No
migration SQL is re-executed against structure schema.sql already
created -- this is exactly the documented workflow, not a shortcut.
"""

from __future__ import annotations

import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL = REPO_ROOT / "schema.sql"

_DB_NAME_RE = re.compile(r"^core_unitd_[0-9a-f]{16}$")
_CONTAINER_NAME_RE = re.compile(r"^core_unitd_pg_[0-9a-f]{16}$")


# ID: 8e2068bf-ae59-41d4-a571-8f6849023cc5
class DatabaseNameError(ValueError):
    """Raised when a database or container name fails the disposable-name check."""


def validate_disposable_db_name(name: str) -> None:
    """Fail closed on any database name outside the disposable pattern.

    Applied before every creation/teardown-equivalent operation in this
    module. ``core_unitd_<16 lowercase hex>`` cannot collide with
    ``core``, ``core_test``, or any other CORE-recognized database name --
    this is the concrete "validate before create/delete" requirement.
    """
    if not _DB_NAME_RE.fullmatch(name):
        raise DatabaseNameError(
            f"refusing to operate on a non-disposable-shaped database name: "
            f"{name!r} (expected core_unitd_<16 hex chars>)"
        )


def validate_disposable_container_name(name: str) -> None:
    """Fail closed on any container name outside the disposable pattern."""
    if not _CONTAINER_NAME_RE.fullmatch(name):
        raise DatabaseNameError(
            f"refusing to operate on a non-disposable-shaped container name: "
            f"{name!r} (expected core_unitd_pg_<16 hex chars>)"
        )


@dataclass(frozen=True)
# ID: ce4caa7e-1cdd-48be-ae2e-9b3e3c85e1e7
class DisposableDatabase:
    """A running, uniquely named, throwaway PostgreSQL instance."""

    container_name: str
    db_name: str
    host: str
    port: int
    database_url: str  # never logged, printed, or persisted


def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # type: ignore[call-overload]
        args, capture_output=True, text=True, check=True, **kwargs
    )


# ID: e79e4b6a-c21f-4801-9cb9-c91f9c99847d
def start_disposable_database(*, timeout_sec: float = 30.0) -> DisposableDatabase:
    """Start a fresh, uniquely named local Postgres container: schema-loaded
    and migration-bootstrapped, ready for immediate use.

    Binds to an OS-assigned ephemeral port on 127.0.0.1 only (never the
    default 5432, never beyond localhost) so this can never collide with
    or be reachable alongside any other Postgres, LAN or local.
    """
    suffix = secrets.token_hex(8)
    db_name = f"core_unitd_{suffix}"
    container_name = f"core_unitd_pg_{suffix}"
    validate_disposable_db_name(db_name)
    validate_disposable_container_name(container_name)

    password = secrets.token_hex(16)  # never logged, never persisted

    _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={db_name}",
            "-p",
            "127.0.0.1::5432",
            "--tmpfs",
            "/var/lib/postgresql/data",
            "postgres:16",
        ]
    )

    port_line = _run(["docker", "port", container_name, "5432"]).stdout.strip()
    # e.g. "0.0.0.0:32783\n[::]:32783" -- the first (IPv4) mapping.
    port = int(port_line.splitlines()[0].rsplit(":", 1)[-1])

    database_url = (
        f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/{db_name}"
    )

    try:
        _wait_ready(container_name, timeout_sec=timeout_sec)
        _load_schema(
            host="127.0.0.1", port=port, user="postgres", password=password, db=db_name
        )
        _bootstrap_and_check_migrations(database_url)
    except Exception:
        subprocess.run(
            ["docker", "rm", "-f", container_name], capture_output=True, text=True
        )
        raise

    return DisposableDatabase(
        container_name=container_name,
        db_name=db_name,
        host="127.0.0.1",
        port=port,
        database_url=database_url,
    )


def _wait_ready(container_name: str, *, timeout_sec: float) -> None:
    """Block until the container's startup restart cycle has completed.

    The official postgres image performs a two-phase startup: an initdb
    pass listening only on the internal Unix socket, then a restart before
    the real TCP listener comes up. A TCP connection attempted during the
    first phase's brief window can see "Connection reset by peer" at the
    restart. Waiting for "database system is ready to accept connections"
    to appear twice in the container log is the documented-safe signal
    that the restart has completed.
    """
    deadline = time.monotonic() + timeout_sec
    marker = "database system is ready to accept connections"
    while time.monotonic() < deadline:
        proc = subprocess.run(
            ["docker", "logs", container_name], capture_output=True, text=True
        )
        if (proc.stdout + proc.stderr).count(marker) >= 2:
            return
        time.sleep(0.3)
    raise RuntimeError(
        f"disposable Postgres container {container_name!r} never completed "
        f"its startup restart cycle within {timeout_sec}s"
    )


def _load_schema(*, host: str, port: int, user: str, password: str, db: str) -> None:
    """Load schema.sql via a raw asyncpg connection -- plain SQL text, no
    CORE import required for this step."""
    import asyncio

    import asyncpg  # type: ignore[import-untyped]  # no published stubs

    if not SCHEMA_SQL.is_file():
        raise RuntimeError(f"canonical schema.sql not found at {SCHEMA_SQL}")
    sql = SCHEMA_SQL.read_text(encoding="utf-8")

    async def _apply() -> None:
        last_exc: Exception | None = None
        conn = None
        for _attempt in range(10):
            try:
                conn = await asyncpg.connect(
                    host=host, port=port, user=user, password=password, database=db
                )
                break
            except (OSError, ConnectionError) as exc:
                last_exc = exc
                await asyncio.sleep(0.5)
        if conn is None:
            raise RuntimeError(
                f"could not connect to the disposable database after retries: "
                f"{last_exc}"
            )
        try:
            await conn.execute(sql)
        finally:
            await conn.close()

    asyncio.run(_apply())


def _bootstrap_and_check_migrations(database_url: str) -> None:
    """Seed core._migrations and confirm nothing is pending, via the real,
    unmodified bootstrap_migrations()/migrate_db(apply=False).

    Run in a fresh subprocess with only DATABASE_URL overridden. This call
    is about CORE's OWN migration ledger (read from CORE's own
    infra/migrations/manifest.yaml, resolved independently of the process
    cwd) -- REPO_PATH/MIND are left unset here deliberately; this step has
    nothing to do with the external target.
    """
    import sys

    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "DATABASE_URL": database_url,
    }
    script = (
        "import asyncio\n"
        "from shared.infrastructure.repositories.db.migration_service import (\n"
        "    bootstrap_migrations, migrate_db,\n"
        ")\n"
        "asyncio.run(bootstrap_migrations())\n"
        "asyncio.run(migrate_db(apply=False))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"migration bootstrap/check failed (exit {result.returncode}):\n"
            f"{result.stderr}"
        )


# ID: 4bc62c87-2069-492d-ab71-9aeb15208d38
def stop_disposable_database(db: DisposableDatabase) -> None:
    """Stop and remove exactly the container this run created.

    Re-validates both names immediately before the destructive call --
    defense in depth even though *db* only ever comes from
    :func:`start_disposable_database` in this process.
    """
    validate_disposable_container_name(db.container_name)
    validate_disposable_db_name(db.db_name)
    subprocess.run(
        ["docker", "rm", "-f", db.container_name], capture_output=True, text=True
    )
