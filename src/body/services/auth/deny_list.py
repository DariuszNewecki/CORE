# src/body/services/auth/deny_list.py
"""DB-backed access suspension deny-list (ADR-124 D4).

Provides immediate JWT invalidation on account suspension, surviving
core-api restarts. Backed by core.suspended_users; an in-process cache
(threading.Lock-protected dict) serves the hot path (every authenticated
request) without a per-request DB round-trip.

Startup contract: deny_list.initialize(session) is called once during the
lifespan startup before requests are served. Until then is_denied() returns
False (fail-open) to avoid blocking startup on DB unavailability.

Interface:
    deny_list.initialize(session)                        async, startup only
    deny_list.add(user_id, expires_at, *, session)       async, runs in caller's tx
    deny_list.remove(user_id, *, session)                async, runs in caller's tx
    deny_list.is_denied(user_id) -> bool                 sync, reads cache only
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ID: 3f7a1c9e-2b4d-4e8c-b5f0-6a1d3c7e2f4b
class _DenyList:
    """DB-backed suspension deny-list with in-process read cache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, datetime] = {}

    # ID: e1b2c3d4-5f6a-7b8c-9d0e-1f2a3b4c5d6e
    async def initialize(self, session: AsyncSession) -> None:
        """Load unexpired suspensions from DB into the in-process cache.

        Called once during lifespan startup. Idempotent.
        """
        result = await session.execute(
            text(
                "SELECT user_id::text, expires_at"
                " FROM core.suspended_users"
                " WHERE expires_at > now()"
            )
        )
        with self._lock:
            self._cache = {row.user_id: row.expires_at for row in result}

    # ID: 8c2e5a1f-4d3b-4f9c-b7e0-1a5d3c8e2f6b
    async def add(
        self,
        user_id: str | UUID,
        expires_at: datetime,
        *,
        session: AsyncSession,
    ) -> None:
        """Record a suspension in DB and update the in-process cache.

        Runs inside the caller's transaction — committed atomically with
        the is_active=false and refresh-token revocation writes.
        """
        await session.execute(
            text(
                "INSERT INTO core.suspended_users (user_id, expires_at)"
                " VALUES (:uid, :exp)"
                " ON CONFLICT (user_id) DO UPDATE"
                "   SET expires_at = EXCLUDED.expires_at,"
                "       suspended_at = now()"
            ),
            {"uid": str(user_id), "exp": expires_at},
        )
        with self._lock:
            self._cache[str(user_id)] = expires_at

    # ID: 5a9d2f7c-1e3b-4c8a-b0f6-4d2c1a5e9b3d
    async def remove(self, user_id: str | UUID, *, session: AsyncSession) -> None:
        """Remove a suspension from DB and in-process cache (on reactivation)."""
        await session.execute(
            text("DELETE FROM core.suspended_users WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        with self._lock:
            self._cache.pop(str(user_id), None)

    # ID: 1d6b4f9c-3a2e-4c8e-b7d0-5a1c3f6b9d4e
    def is_denied(self, user_id: str | UUID) -> bool:
        """Return True if user_id is on the deny-list and the entry has not expired.

        Synchronous — reads the in-process cache only; no DB round-trip.
        Expired entries are lazily evicted from the cache on read.
        """
        key = str(user_id)
        with self._lock:
            exp = self._cache.get(key)
            if exp is None:
                return False
            if datetime.now(UTC) >= exp:
                del self._cache[key]
                return False
            return True


deny_list = _DenyList()
