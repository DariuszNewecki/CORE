# src/shared/infrastructure/repositories/db/status_service.py

"""
Refactored under dry_by_design.
This is the single source of truth for database status logic,
consolidated from the CLI layer.

Read-only (ADR-162 D2/D3): a status check never creates the ledger table or
any other object. A missing ledger is reported as ``ledger_present=False``
with every manifest entry pending — it is a state to name, not to repair here.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.db.ledger_engine import (
    SessionFactory,
    ledger_exists,
    read_applied,
)
from shared.infrastructure.repositories.db.manifest import load_manifest


@dataclass
# ID: c4fbc704-9f97-48df-bc55-63fb1b850838
class StatusReport:
    """A data structure holding the results of a database status check."""

    is_connected: bool
    db_version: str | None
    applied_migrations: set[str]
    pending_migrations: list[str]
    ledger_present: bool = True


# ID: 75fac84c-5818-47c0-9d50-c0670d065c8c
async def status(*, session_factory: SessionFactory = get_session) -> StatusReport:
    """Checks DB connectivity and migration status, returning a structured report."""
    # 1) connection/ping (through the injected factory so tests can point it
    #    at a disposable instance)
    try:
        async with session_factory() as session:
            db_version = (await session.execute(text("select version()"))).scalar_one()
        is_connected = True
    except Exception:
        return StatusReport(
            is_connected=False,
            db_version=None,
            applied_migrations=set(),
            pending_migrations=[],
            ledger_present=False,
        )

    # 2) manifest & ledger — read-only
    manifest = load_manifest()
    async with session_factory() as session:
        present = await ledger_exists(session)
        applied = await read_applied(session) if present else set()
    pending = [m for m in manifest.order if m not in applied]

    return StatusReport(
        is_connected=is_connected,
        db_version=db_version,
        applied_migrations=applied,
        pending_migrations=pending,
        ledger_present=present,
    )
