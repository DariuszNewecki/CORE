# tests/shared/infrastructure/migrations/conftest.py
"""Disposable PostgreSQL for the migration-ledger integration tests (ADR-162).

One throwaway ``postgres`` container per test module (the mechanism
``tests/fixtures/external_target/db_provisioning.py`` and
``docker-compose.test.yml`` already use), bound to an OS-assigned port on
127.0.0.1 only, with tmpfs storage, removed at module teardown. Each test
gets its own freshly created database inside it, so nothing here ever
touches ``core_test`` or any other CORE database.

Tests using these fixtures are ``integration``-marked: they need Docker. They
skip when Docker is unavailable unless ``CORE_REQUIRE_DB_TESTS=1`` (CI's
integration job), where a missing Docker is an infrastructure fault.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_SQL = REPO_ROOT / "schema.sql"
SCHEMA_V2_9_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.9.1.sql"

_IMAGE = os.environ.get("CORE_TEST_POSTGRES_IMAGE", "postgres:16")
_READY = "database system is ready to accept connections"


def _docker_usable() -> bool:
    if shutil.which("docker") is None:
        return False
    proc = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return proc.returncode == 0


def _skip_or_fail_without_docker() -> None:
    if _docker_usable():
        return
    if os.environ.get("CORE_REQUIRE_DB_TESTS", "") == "1":
        pytest.fail(
            "CORE_REQUIRE_DB_TESTS=1 but Docker is unavailable — the disposable "
            "Postgres these tests need cannot start"
        )
    pytest.skip("Docker is unavailable; disposable Postgres tests skipped")


@dataclass(frozen=True)
# ID: 388bf384-c50f-4fa8-8e52-b17a2f32403e
class DisposablePostgres:
    """A running throwaway Postgres server. ``password`` is never printed."""

    container: str
    host: str
    port: int
    password: str

    # ID: b6e40381-e3a2-43e3-9d92-bd1e81441b2b
    def url(self, database: str) -> str:
        return (
            f"postgresql+asyncpg://postgres:{self.password}@{self.host}:{self.port}"
            f"/{database}"
        )


def _start_container() -> DisposablePostgres:
    suffix = secrets.token_hex(6)
    name = f"core_migtest_pg_{suffix}"
    password = secrets.token_hex(12)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-p",
            "127.0.0.1::5432",
            "--tmpfs",
            "/var/lib/postgresql/data",
            _IMAGE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        port_line = subprocess.run(
            ["docker", "port", name, "5432"], check=True, capture_output=True, text=True
        ).stdout.strip()
        port = int(port_line.splitlines()[0].rsplit(":", 1)[-1])
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            logs = subprocess.run(
                ["docker", "logs", name], capture_output=True, text=True
            )
            if (logs.stdout + logs.stderr).count(_READY) >= 2:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("disposable Postgres never became ready")
    except Exception:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        raise
    return DisposablePostgres(
        container=name, host="127.0.0.1", port=port, password=password
    )


@pytest.fixture(scope="module")
# ID: 4426e7fb-81cc-419c-bf33-04df7cec3427
def disposable_postgres() -> Iterator[DisposablePostgres]:
    _skip_or_fail_without_docker()
    server = _start_container()
    try:
        yield server
    finally:
        subprocess.run(["docker", "rm", "-f", server.container], capture_output=True)


# ID: 6b5205a8-d5dd-45d5-a940-471ba0ae1777
def pg_dump_schema(server: DisposablePostgres, database: str) -> str:
    """``pg_dump --schema-only --no-owner --no-acl`` of ``database``, run with
    the server's own pg_dump inside the container (version-matched)."""
    return subprocess.run(
        [
            "docker",
            "exec",
            server.container,
            "pg_dump",
            "-U",
            "postgres",
            "--schema-only",
            "--no-owner",
            "--no-acl",
            database,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


async def _admin_execute(server: DisposablePostgres, sql: str) -> None:
    engine = create_async_engine(server.url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


@dataclass
# ID: ecb49a55-fb94-4b14-9c79-add60b7d2c2b
class FreshDatabase:
    """A newly created database on the disposable server plus a session factory."""

    name: str
    url: str
    engine: AsyncEngine
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]

    # ID: 94671848-f593-4104-ad3d-2ff1051c9e25
    async def scalar(self, sql: str) -> object:
        async with self.session_factory() as session:
            return (await session.execute(text(sql))).scalar_one()

    # ID: 7359a022-fc59-4d82-8ee6-c85570fb77c8
    async def execute(self, sql: str) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(text(sql))

    # ID: 17da78e2-2e39-4e8f-a9eb-8ef5f72c206f
    async def execute_script(self, sql: str) -> None:
        """Run a multi-statement script (e.g. a schema dump) via raw asyncpg."""
        raw = await self.engine.raw_connection()
        try:
            driver = raw.driver_connection  # asyncpg.Connection
            await driver.execute(sql)
        finally:
            raw.close()

    # ID: f9e2ed44-c539-4871-982e-fdf9883179bd
    async def load_schema(self, schema_sql: Path) -> None:
        """Load a pg_dump schema file the way CI seeds its ephemeral database:
        prerequisite roles and extensions first, then the portable dump."""
        async with self.session_factory() as session:
            async with session.begin():
                for role in ("core_db", "core"):
                    exists = (
                        await session.execute(
                            text(
                                "select 1 from pg_roles where rolname = :r"
                            ).bindparams(r=role)
                        )
                    ).first()
                    if exists is None:
                        await session.execute(text(f"create role {role}"))
                for ext in ("pg_trgm", "btree_gin", "btree_gist", "pgcrypto"):
                    await session.execute(text(f"create extension if not exists {ext}"))
        await self.execute_script(schema_sql.read_text(encoding="utf-8"))

    # ID: 806b7dd1-197d-4b66-9b3f-2ab107fd3601
    async def ledger_rows(self) -> dict[str, bool]:
        """{id: reconciled} for every ledger row; {} when the table is absent."""
        async with self.session_factory() as session:
            exists = (
                await session.execute(text("select to_regclass('core._migrations')"))
            ).scalar_one()
            if exists is None:
                return {}
            has_col = (
                await session.execute(
                    text(
                        "select exists (select 1 from information_schema.columns "
                        "where table_schema='core' and table_name='_migrations' "
                        "and column_name='reconciled')"
                    )
                )
            ).scalar_one()
            sql = (
                "select id, reconciled from core._migrations"
                if has_col
                else "select id, false from core._migrations"
            )
            rows = await session.execute(text(sql))
            return {r[0]: bool(r[1]) for r in rows}


async def _create_database(server: DisposablePostgres) -> FreshDatabase:
    name = f"t_{secrets.token_hex(6)}"
    await _admin_execute(server, f"create database {name}")
    engine = create_async_engine(server.url(name), pool_size=6, max_overflow=4)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    return FreshDatabase(
        name=name, url=server.url(name), engine=engine, session_factory=factory
    )


async def _drop_database(server: DisposablePostgres, db: FreshDatabase) -> None:
    await db.engine.dispose()
    # Terminate stragglers so DROP DATABASE cannot block.
    await _admin_execute(
        server,
        "select pg_terminate_backend(pid) from pg_stat_activity "
        f"where datname = '{db.name}' and pid <> pg_backend_pid()",
    )
    await _admin_execute(server, f"drop database if exists {db.name}")


@pytest.fixture
# ID: 6f3d2fd5-1192-4594-8b57-824e1322ca0c
async def fresh_database(
    disposable_postgres: DisposablePostgres,
) -> AsyncIterator[FreshDatabase]:
    """A brand-new empty database (no ``core`` schema) for one test."""
    db = await _create_database(disposable_postgres)
    try:
        yield db
    finally:
        await _drop_database(disposable_postgres, db)


@pytest.fixture
# ID: 243e0c11-ecab-472f-9588-dbca3d103f16
async def database_factory(
    disposable_postgres: DisposablePostgres,
) -> AsyncIterator[Callable[[], Awaitable[FreshDatabase]]]:
    """Create any number of extra fresh databases in one test; all dropped after."""
    created: list[FreshDatabase] = []

    async def _make() -> FreshDatabase:
        db = await _create_database(disposable_postgres)
        created.append(db)
        return db

    try:
        yield _make
    finally:
        for db in created:
            await _drop_database(disposable_postgres, db)


@pytest.fixture
# ID: f510a786-9660-4a2c-8194-0ab3b611c68c
def schema_dumper(disposable_postgres: DisposablePostgres) -> Callable[[str], str]:
    """``pg_dump --schema-only`` of a database on the disposable server."""
    return lambda database: pg_dump_schema(disposable_postgres, database)
