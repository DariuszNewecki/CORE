# tests/shared/infrastructure/migrations/test_schema_gate_postgres.py
"""ADR-162 D2 (R2-A) — the startup schema gate, one real database per state.

Each state the ruling enumerates is built on the disposable Postgres with
the real manifest and files, evaluated through the real gate, and checked
for its verdict, its remedy text and whether ``run_startup_schema_gate``
refuses (exit 78). The gate is read-only: it must leave the ledger exactly
as it found it in every state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db import schema_gate as gate_module
from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_service import (
    adopt_baseline,
    migrate_db,
)
from shared.infrastructure.repositories.db.schema_gate import (
    EX_CONFIG,
    SchemaGateRefusal,
    SchemaGateState,
    evaluate_schema_gate,
    run_startup_schema_gate,
)


if TYPE_CHECKING:
    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
SCHEMA_SQL = REPO_ROOT / "schema.sql"
SCHEMA_V2_9_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.9.1.sql"
SCHEMA_V2_10_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.10.1.sql"


async def _refuses(
    db: FreshDatabase, component: str = "CORE daemon"
) -> SchemaGateRefusal:
    before = await db.ledger_rows()
    with pytest.raises(SchemaGateRefusal) as excinfo:
        await run_startup_schema_gate(component, session_factory=db.session_factory)
    assert await db.ledger_rows() == before, "the gate must not touch the ledger"
    assert excinfo.value.exit_code == EX_CONFIG == 78
    assert component in str(excinfo.value)
    return excinfo.value


# ID: 6e5cded4-8f27-4d54-86b0-423f07910949
async def test_current_schema_starts(fresh_database: FreshDatabase) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_SQL)
    verdict = await evaluate_schema_gate(session_factory=db.session_factory)
    assert verdict.state is SchemaGateState.CURRENT and not verdict.refuses
    assert "assets: source" in verdict.message
    returned = await run_startup_schema_gate(
        "CORE API", session_factory=db.session_factory
    )
    assert returned.state is SchemaGateState.CURRENT


# ID: 36c56f3b-6848-4934-8f8e-0a8a96cd625f
async def test_pending_migrations_refuse_naming_the_first_and_the_remedy(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_V2_10_1)
    await adopt_baseline("v2.10.1", write=True, session_factory=db.session_factory)
    verdict = await evaluate_schema_gate(session_factory=db.session_factory)
    assert verdict.state is SchemaGateState.PENDING
    assert "5 migration(s)" in verdict.message  # ledger column + 4 U5a backfills
    assert "first: 20260919_adr162_migrations_reconciled.sql" in verdict.message
    assert verdict.remedy == "core-admin database migrate --write"
    refusal = await _refuses(db)
    assert "core-admin database migrate --write" in str(refusal)
    # The remedy works and the gate then admits.
    await migrate_db(write=True, session_factory=db.session_factory)
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.CURRENT
    )


# ID: 11919811-36e7-4955-a30a-73dad60a2bd0
async def test_empty_ledger_on_populated_schema_refuses_with_adoption_remedy(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_V2_9_1)
    verdict = await evaluate_schema_gate(session_factory=db.session_factory)
    assert verdict.state is SchemaGateState.EMPTY_LEDGER
    assert verdict.details["baseline_suggestion"] == "v2.9.1"
    assert verdict.remedy is not None
    assert "--adopt-baseline v2.9.1 --write" in verdict.remedy
    await _refuses(db, "CORE API")


# ID: 38750d9a-f931-458c-9c4c-ade69bff4844
async def test_ledger_schema_contradiction_refuses_naming_the_migration(
    fresh_database: FreshDatabase,
) -> None:
    """The --bootstrap-after-upgrade trap: a v2.9.1 schema whose ledger claims
    everything. Today this started green and failed later; now it refuses."""
    db = fresh_database
    await db.load_schema(SCHEMA_V2_9_1)
    for mig in load_manifest().order:
        await db.execute(f"insert into core._migrations (id) values ('{mig}')")
    verdict = await evaluate_schema_gate(session_factory=db.session_factory)
    assert verdict.state is SchemaGateState.CONTRADICTION
    assert "first: 20260712_adr148_finalizing_and_consequence_recorded_at.sql" in (
        verdict.message
    )
    assert verdict.remedy == "core-admin database status"
    await _refuses(db)


# ID: 1a563792-85e8-4849-8596-2be842e23808
async def test_no_core_schema_refuses_with_install_remedy(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database  # brand-new, empty database
    verdict = await evaluate_schema_gate(session_factory=db.session_factory)
    assert verdict.state is SchemaGateState.NO_SCHEMA
    assert verdict.remedy and "schema.sql" in verdict.remedy
    await _refuses(db)
    assert await db.scalar("select to_regclass('core._migrations') is null") is True


# ID: bc47842e-1876-4013-9968-f76b0e5364ea
async def test_unreadable_manifest_refuses_as_assets_unavailable(
    fresh_database: FreshDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_SQL)

    def _broken() -> None:
        raise RuntimeError("manifest gone")

    monkeypatch.setattr(gate_module, "resolve_migration_assets", _broken)
    verdict = await evaluate_schema_gate(session_factory=db.session_factory)
    assert verdict.state is SchemaGateState.ASSETS_UNAVAILABLE
    assert "manifest gone" in verdict.message
    await _refuses(db)


# ID: 1f94667b-8a77-4a10-ac32-8e7dddcc2956
async def test_unreachable_database_is_reported_not_refused(
    disposable_postgres,  # type: ignore[no-untyped-def]
) -> None:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    bad = disposable_postgres.url("no_such_database_xyz")
    engine = create_async_engine(bad)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        verdict = await evaluate_schema_gate(session_factory=factory)
        assert verdict.state is SchemaGateState.DB_UNAVAILABLE and not verdict.refuses
        returned = await run_startup_schema_gate("CORE daemon", session_factory=factory)
        assert returned.state is SchemaGateState.DB_UNAVAILABLE
    finally:
        await engine.dispose()
