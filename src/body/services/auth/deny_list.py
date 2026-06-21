# src/body/services/auth/deny_list.py
"""In-process suspension deny-list (ADR-124 D4).

Provides immediate JWT invalidation on account suspension without waiting for
the access token to expire naturally.  Phase 1 implementation: in-process dict
protected by a threading.Lock().  Replace with Redis in multi-process deployments.

Interface contract: deny_list.is_denied(user_id) -> bool
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import UUID


# ID: 3f7a1c9e-2b4d-4e8c-b5f0-6a1d3c7e2f4b
class _DenyList:
    """Thread-safe in-process deny-list keyed by user_id string."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, datetime] = {}

    # ID: 8c2e5a1f-4d3b-4f9c-b7e0-1a5d3c8e2f6b
    def add(self, user_id: str | UUID, expires_at: datetime) -> None:
        """Add user_id to the deny-list until expires_at."""
        with self._lock:
            self._entries[str(user_id)] = expires_at

    # ID: 5a9d2f7c-1e3b-4c8a-b0f6-4d2c1a5e9b3d
    def is_denied(self, user_id: str | UUID) -> bool:
        """Return True if user_id is on the deny-list and the entry has not expired."""
        key = str(user_id)
        with self._lock:
            exp = self._entries.get(key)
            if exp is None:
                return False
            if datetime.now(UTC) >= exp:
                del self._entries[key]
                return False
            return True

    # ID: 1d6b4f9c-3a2e-4c8e-b7d0-5a1c3f6b9d4e
    def remove(self, user_id: str | UUID) -> None:
        """Remove user_id from the deny-list (on reactivation)."""
        with self._lock:
            self._entries.pop(str(user_id), None)


deny_list = _DenyList()
