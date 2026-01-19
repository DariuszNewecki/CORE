# src/body/cli/logic/hub/repository.py

"""Refactored logic for src/body/cli/logic/hub/repository.py."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models import CliCommand


# ID: 15dc04c4-315d-4cc0-a5e1-ef138db23b01
async def fetch_all_commands(session: AsyncSession) -> list[CliCommand]:
    """Retrieves the full list of CLI commands from the DB SSOT."""
    rows = (await session.execute(select(CliCommand))).scalars().all()
    return list(rows or [])
