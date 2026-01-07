# tests/test_smoke_db.py

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_smoke_db_session_fixture_provides_asyncsession(
    db_session: AsyncSession,
) -> None:
    """
    Baseline DB harness check:
    - db_session fixture yields AsyncSession
    - schema 'core' exists (created by the harness)
    """
    assert isinstance(
        db_session, AsyncSession
    ), "db_session did not provide an AsyncSession"

    # Ensure we are connected to the test database.
    db_url = os.getenv("DATABASE_URL", "")
    assert (
        "core_test" in db_url
    ), f"Refusing to run DB smoke test on non-test DB URL: {db_url!r}"

    # Confirm the harness created schema `core`.
    result = await db_session.execute(
        text(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'core'"
        )
    )
    assert (
        result.scalar() == "core"
    ), "Expected schema 'core' to exist (schema reset/apply may have failed)"


@pytest.mark.asyncio
async def test_smoke_db_schema_has_tables(db_session: AsyncSession) -> None:
    """
    Verifies that applying `sql/001_consolidated_schema.sql` resulted in at least one table
    under schema 'core'. This catches missing schema file, apply failures, or DB permission issues.
    """
    result = await db_session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'core'
            """
        )
    )
    count = int(result.scalar() or 0)
    assert (
        count > 0
    ), "No tables found in schema 'core' (schema file missing or not applied)"
