# src/shared/infrastructure/repositories/db/ledger_engine.py
"""
The atomic migration ledger engine (ADR-162 D7 / R7-A).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — executes migration
statements and ledger writes mechanically; decides nothing about *which*
migration to run (that is the manifest's, and the operator's, decision).

Guarantees, per migration:

* **One transaction.** The migration's statements and its ``core._migrations``
  row commit together or not at all. A failure at migration N leaves 1..N-1
  recorded and N fully rolled back — no partially applied change, no ledger
  row without its change (URS G11 rollback; ADR-162 D7).
* **Concurrency-locked.** Every apply takes ``pg_advisory_xact_lock`` on a
  fixed key and re-reads the ledger inside the lock, so concurrent invocations
  apply each migration exactly once; the loser observes the row and skips.
* **Reconciliation is exceptional (D12 §2).** A migration is recorded without
  execution only when its manifest entry is ``reconcilable`` *and* its
  ``verify`` probe already proves the complete postcondition. Otherwise the
  engine executes it — and, when a ``verify`` probe exists, refuses to record
  it if the probe still fails after execution (ledger ≡ catalog).
* **Fail closed.** Entries flagged ``transactional: false``, files with
  non-transactional statements, and files with foreign transaction control
  are refused before anything is executed.
* **One schema authority.** The engine owns ledger *rows*; the ledger's
  *structure* changes only through ledgered migrations. ``ensure_ledger``
  creates a missing ledger in its legacy shape (``id``, ``applied_at``) and
  never alters an existing one; the ``reconciled`` column arrives through
  ``20260919_adr162_migrations_reconciled.sql`` like any other change. Until
  that migration has executed, rows are recorded legacy-shaped; a
  reconciled row recorded in that window has its marker set once the column
  exists (:func:`backfill_reconciled_markers`, an explicit, logged step).

Sessions are injected (``session_factory``) so the engine runs identically
against the configured database and against a disposable test instance.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .manifest import MigrationEntry
from .migration_sql import MigrationSqlError, prepare_migration_sql


logger = getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

# Fixed advisory-lock key for every ledger writer (ADR-162 D7 §3). Decimal
# rendering of the ASCII bytes "CORE" "MIGR"; fits a signed 64-bit key.
LEDGER_LOCK_KEY = 0x434F52454D494752

LEDGER_TABLE = "core._migrations"

# Legacy shape only: every later column is a ledgered migration's business.
_LEDGER_DDL = """
create table if not exists core._migrations (
  id text primary key,
  applied_at timestamptz not null default now()
)
"""


# ID: e4d4d3ac-2b53-4a8b-9c80-6fde8088d4d8
class LedgerEngineError(RuntimeError):
    """The engine refused or failed to apply a migration."""


# ID: e816d287-a600-41a3-9c33-53e2384ed975
class MigrationOutcome(str, Enum):
    APPLIED = "applied"  # statements executed, row recorded
    RECONCILED = "reconciled"  # probe already true, row recorded, nothing run
    SKIPPED_RECORDED = "skipped_recorded"  # another writer recorded it first


@dataclass(frozen=True)
# ID: 8ce01f94-f708-41de-9031-b672f5412b59
class MigrationResult:
    id: str
    outcome: MigrationOutcome
    statements_executed: int
    # False only for a RECONCILED row recorded while the ledger still lacked
    # the ``reconciled`` column (see backfill_reconciled_markers).
    marker_recorded: bool = True


# ---------------------------------------------------------------------------
# Read-only ledger access (never creates objects — usable by status/gates)
# ---------------------------------------------------------------------------


# ID: dad1ad99-e64f-4442-b938-9328d9f87aa7
async def ledger_exists(session: AsyncSession) -> bool:
    row = await session.execute(text("select to_regclass('core._migrations')"))
    return row.scalar_one() is not None


# ID: c485dbda-6048-4f64-95e8-b5ca0e575f17
async def ledger_has_reconciled_column(session: AsyncSession) -> bool:
    row = await session.execute(
        text(
            "select exists (select 1 from information_schema.columns "
            "where table_schema = 'core' and table_name = '_migrations' "
            "and column_name = 'reconciled')"
        )
    )
    return bool(row.scalar_one())


# ID: 3d01687a-382c-4587-bf56-4470ccd29849
async def read_applied(session: AsyncSession) -> set[str]:
    """Applied migration ids; empty when the ledger table does not exist."""
    if not await ledger_exists(session):
        return set()
    result = await session.execute(text("select id from core._migrations"))
    return {r[0] for r in result}


# ID: 18263638-8814-42ce-abbb-9cecdbc88849
async def get_applied(session_factory: SessionFactory = get_session) -> set[str]:
    async with session_factory() as session:
        return await read_applied(session)


# ID: 250d6c0a-8f5d-4989-802c-56289287d804
async def run_probe(session: AsyncSession, sql: str) -> bool:
    """Evaluate a manifest probe: one row, one boolean, read-only."""
    result = await session.execute(text(sql))
    value = result.scalar_one()
    if not isinstance(value, bool):
        raise LedgerEngineError(
            f"probe must return a single boolean, got {value!r}: {sql[:120]}"
        )
    return value


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


# ID: 8bb15c59-050f-4c0e-bbd1-3fa99d8a35f9
async def ensure_ledger(session_factory: SessionFactory = get_session) -> None:
    """Create a missing ledger table in its legacy shape (write mode only).

    Never alters an existing ledger: structural changes to ``core._migrations``
    are ledgered migrations themselves (ADR-162 D7; one schema authority).
    """
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text("create schema if not exists core"))
            await session.execute(text(_LEDGER_DDL))


async def _record(session: AsyncSession, mig_id: str, *, reconciled: bool) -> bool:
    """Insert the ledger row; legacy-shaped while the column does not exist yet.

    Returns whether the ``reconciled`` marker was persisted.
    """
    if await ledger_has_reconciled_column(session):
        await session.execute(
            text(
                "insert into core._migrations (id, applied_at, reconciled) "
                "values (:id, :ts, :reconciled)"
            ).bindparams(id=mig_id, ts=datetime.now(tz=UTC), reconciled=reconciled)
        )
        return True
    await session.execute(
        text(
            "insert into core._migrations (id, applied_at) values (:id, :ts)"
        ).bindparams(id=mig_id, ts=datetime.now(tz=UTC))
    )
    if reconciled:
        logger.warning(
            "Migration %s reconciled, but the ledger predates the reconciled "
            "marker; the marker is set once the column migration has run.",
            mig_id,
        )
    return not reconciled


# ID: afe15a5f-35e7-4908-b5df-71a049ac2e06
async def backfill_reconciled_markers(
    mig_ids: list[str], *, session_factory: SessionFactory = get_session
) -> list[str]:
    """Set ``reconciled = true`` for rows recorded before the column existed.

    Ledger-row maintenance, not a schema change: called by the service after
    a ``--write`` run in which the column migration executed later than a
    reconciliation. Returns the ids updated (none when the column is still
    absent).
    """
    if not mig_ids:
        return []
    async with session_factory() as session:
        async with session.begin():
            if not await ledger_has_reconciled_column(session):
                return []
            await session.execute(
                text("select pg_advisory_xact_lock(:k)").bindparams(k=LEDGER_LOCK_KEY)
            )
            result = await session.execute(
                text(
                    "update core._migrations set reconciled = true "
                    "where id = any(:ids) and reconciled = false returning id"
                ).bindparams(ids=mig_ids)
            )
            updated = [r[0] for r in result]
    for mig_id in updated:
        logger.info("Ledger marker set: %s recorded as reconciled.", mig_id)
    return updated


# ID: 1d587ce6-c49b-4fbb-ba00-18ea58252e25
async def record_ledger_row(
    mig_id: str,
    *,
    reconciled: bool,
    session_factory: SessionFactory = get_session,
) -> bool:
    """Record ``mig_id`` under the ledger lock without executing anything.

    Returns False when the row already exists. This is the primitive behind
    verified baseline adoption (ADR-162 D3); it is never a substitute for
    :func:`apply_migration` on a pending entry.
    """
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("select pg_advisory_xact_lock(:k)").bindparams(k=LEDGER_LOCK_KEY)
            )
            if mig_id in await read_applied(session):
                return False
            await _record(session, mig_id, reconciled=reconciled)
            return True


# ID: d1bb09fd-617d-4e07-87a6-0b9b70f49810
async def apply_migration(
    entry: MigrationEntry,
    sql_path: Path,
    *,
    session_factory: SessionFactory = get_session,
) -> MigrationResult:
    """Apply one manifest entry atomically (see module docstring)."""
    if not entry.transactional:
        raise LedgerEngineError(
            f"{entry.id}: declared transactional: false — non-transactional "
            "migrations are unsupported until designed (ADR-162 D7)"
        )
    try:
        prepared = prepare_migration_sql(
            sql_path.read_text(encoding="utf-8"), source=entry.id
        )
    except MigrationSqlError as exc:
        raise LedgerEngineError(str(exc)) from exc
    except OSError as exc:
        raise LedgerEngineError(f"{entry.id}: cannot read {sql_path}: {exc}") from exc

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("select pg_advisory_xact_lock(:k)").bindparams(k=LEDGER_LOCK_KEY)
            )
            # Re-read inside the lock: a concurrent writer may have won.
            if entry.id in await read_applied(session):
                logger.info("Migration %s already recorded — skipping", entry.id)
                return MigrationResult(entry.id, MigrationOutcome.SKIPPED_RECORDED, 0)

            if entry.reconcilable and entry.verify is not None:
                if await run_probe(session, entry.verify):
                    marked = await _record(session, entry.id, reconciled=True)
                    logger.info(
                        "Migration %s reconciled: postcondition already holds", entry.id
                    )
                    return MigrationResult(
                        entry.id, MigrationOutcome.RECONCILED, 0, marker_recorded=marked
                    )

            for stmt in prepared.statements:
                await session.execute(text(stmt))

            if entry.verify is not None and not await run_probe(session, entry.verify):
                # Rolled back by leaving the ``session.begin()`` block via raise.
                raise LedgerEngineError(
                    f"{entry.id}: verify probe still fails after execution; "
                    "the migration was rolled back and not recorded"
                )
            await _record(session, entry.id, reconciled=False)
            return MigrationResult(
                entry.id, MigrationOutcome.APPLIED, len(prepared.statements)
            )


# ID: 44d74473-44a9-4225-af9a-cc1ec4f78997
def describe(result: MigrationResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "outcome": result.outcome.value,
        "statements_executed": result.statements_executed,
    }
