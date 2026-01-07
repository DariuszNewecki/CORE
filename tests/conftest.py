# tests/conftest.py
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.session_manager import (
    dispose_all_engines_for_current_loop_only,
    get_session,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engines_after_each_test() -> AsyncGenerator[None, None]:
    yield
    await dispose_all_engines_for_current_loop_only()
