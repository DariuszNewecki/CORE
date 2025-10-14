# src/services/repositories/db/status_service.py
"""
Refactored under dry_by_design.
Pattern: extract_module. Source of truth for database status logic.
Merged from: src/cli/logic/status.py::status
"""

from __future__ import annotations

from dataclasses import dataclass

from services.repositories.db.common import (
    ensure_ledger,
    get_applied,
    load_policy,
)
from services.repositories.db.engine import ping


@dataclass
# ID: c4fbc704-9f97-48df-bc55-63fb1b850838
class StatusReport:
    """A data structure holding the results of a database status check."""

    is_connected: bool
    db_version: str | None
    applied_migrations: set[str]
    pending_migrations: list[str]


# ID: 75fac84c-5818-47c0-9d50-c0670d065c8c
async def status() -> StatusReport:
    """Checks DB connectivity and migration status, returning a structured report."""
    # 1) connection/ping
    try:
        info = await ping()
        is_connected = info.get("ok", False)
        db_version = info.get("version")
    except Exception:
        return StatusReport(
            is_connected=False,
            db_version=None,
            applied_migrations=set(),
            pending_migrations=[],
        )

    # 2) policy & migrations
    pol = load_policy()
    order = pol.get("migrations", {}).get("order", [])

    await ensure_ledger()
    applied = await get_applied()
    pending = [m for m in order if m not in applied]

    return StatusReport(
        is_connected=is_connected,
        db_version=db_version,
        applied_migrations=applied,
        pending_migrations=pending,
    )
