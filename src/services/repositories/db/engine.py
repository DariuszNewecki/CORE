# src/services/repositories/db/engine.py
"""
Refactored under dry_by_design.
Pattern: extract_module. Source of truth for DB engine logic is now session_manager.
Merged from: src/services/repositories/db/engine.py::_initialize_db
"""

from __future__ import annotations

from sqlalchemy import text

# The single source of truth for DB sessions is now imported.
from services.database.session_manager import get_session

# The get_session and _initialize_db functions previously here are now removed.


# ID: 4ec8bd10-ae74-4b30-b60c-799fb7d9f9bb
async def ping() -> dict:
    """Lightweight connectivity check, using the canonical session manager."""
    # _initialize_db is removed; get_session handles all engine/session logic.
    async with get_session() as session:
        async with session.begin():
            v = await session.execute(text("select version()"))
            return {"ok": True, "version": v.scalar_one()}
