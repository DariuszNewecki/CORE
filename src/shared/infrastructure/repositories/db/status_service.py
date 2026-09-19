# src/shared/infrastructure/repositories/db/status_service.py

"""
Refactored under dry_by_design.
This is the single source of truth for database status logic,
consolidated from the CLI layer.

Read-only (ADR-162 D2/D3): a status check never creates the ledger table or
any other object. It reports pending migrations, ledger/schema contradictions
(recorded entries whose verify probe fails) and — when the ledger is empty on
a populated schema — the declared baseline whose probes hold, as a
*suggestion* for ``database migrate --adopt-baseline``; it never records one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.db.common import resolve_migration_assets
from shared.infrastructure.repositories.db.ledger_engine import SessionFactory
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_service import inspect_ledger


@dataclass
# ID: c4fbc704-9f97-48df-bc55-63fb1b850838
class StatusReport:
    """A data structure holding the results of a database status check."""

    is_connected: bool
    db_version: str | None
    applied_migrations: set[str]
    pending_migrations: list[str]
    ledger_present: bool = True
    schema_present: bool = True
    probe_failures: list[str] = field(default_factory=list)
    baseline_suggestion: str | None = None
    assets_origin: str | None = None  # "source" | "bundled" (ADR-162 D8)

    @property
    # ID: 6685ef00-f3c0-47fc-9465-55231b72a51e
    def is_current(self) -> bool:
        """Nothing pending and no contradiction — the state startup may trust."""
        return (
            self.is_connected
            and self.ledger_present
            and not self.pending_migrations
            and not self.probe_failures
        )


# ID: 75fac84c-5818-47c0-9d50-c0670d065c8c
async def status(*, session_factory: SessionFactory = get_session) -> StatusReport:
    """Checks DB connectivity and migration status, returning a structured report."""
    # 1) connection/ping (through the injected factory so tests can point it
    #    at a disposable instance)
    try:
        async with session_factory() as session:
            db_version = (await session.execute(text("select version()"))).scalar_one()
    except Exception:
        return StatusReport(
            is_connected=False,
            db_version=None,
            applied_migrations=set(),
            pending_migrations=[],
            ledger_present=False,
            schema_present=False,
        )

    # 2) manifest & ledger — read-only
    assets = resolve_migration_assets()
    manifest = load_manifest(assets=assets)
    inspection = await inspect_ledger(manifest, session_factory=session_factory)

    return StatusReport(
        is_connected=True,
        db_version=db_version,
        applied_migrations=inspection.applied,
        pending_migrations=inspection.pending,
        ledger_present=inspection.ledger_present,
        schema_present=inspection.schema_present,
        probe_failures=inspection.probe_failures,
        baseline_suggestion=inspection.baseline_suggestion,
        assets_origin=assets.origin,
    )
