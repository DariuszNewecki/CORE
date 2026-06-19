# tests/conftest.py
from __future__ import annotations

import functools
import os
import socket
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database import session_manager
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


# --- Skip DB-backed tests when the database is unreachable ----------------------
#
# `.env.test` points DATABASE_URL at a LAN Postgres (e.g. 192.168.20.23/core_test).
# That host is reachable from the dev box and the server, but NOT from an external
# CI runner (GitHub-hosted runners cannot route to a private 192.168.x.x address).
# Without a guard, every DB-backed test blocks on asyncpg's connect attempt until
# its timeout fires, repeatedly — turning the smoke suite into a ~50-minute hang.
#
# A test "needs the database" iff it (directly or via a fixture) opens a session
# through `get_session()`, which funnels through `session_manager._get_state()`.
# `_get_state` is resolved via the module global at call time, so monkeypatching it
# here intercepts every caller regardless of how `get_session` was imported. When
# the host is unreachable we raise `pytest.skip()` from that chokepoint, so the test
# is honestly reported as skipped (it did not run) rather than passed or failed.
# Tests that never touch the database are unaffected.


@functools.lru_cache(maxsize=1)
def _db_reachability() -> tuple[bool, str]:
    """Probe the configured DB host once. Returns (reachable, reason_if_not)."""
    url = os.environ.get("DATABASE_URL") or ""
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or 5432
    if not host:
        return False, "DATABASE_URL is not set"
    try:
        with socket.create_connection((host, port), timeout=3.0):
            return True, ""
    except OSError as exc:
        return False, f"database host {host}:{port} is unreachable ({exc.__class__.__name__})"


@pytest.fixture(autouse=True)
def _skip_db_tests_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    reachable, reason = _db_reachability()
    if reachable:
        return

    def _unreachable(*_args: object, **_kwargs: object) -> None:
        pytest.skip(f"requires database — {reason}")

    # raising=True: fail loudly if `_get_state` is ever renamed, rather than
    # silently no-op'ing and letting the hang return unnoticed.
    monkeypatch.setattr(session_manager, "_get_state", _unreachable, raising=True)
