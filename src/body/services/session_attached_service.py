# src/body/services/session_attached_service.py

"""Base class for body-layer services with defensive session lifecycle.

A SessionAttachedService receives an AsyncSession in __init__, may have
that session detached by an external caller via detach(), and refuses
work via _require_session() once detached. Subclasses inherit __init__
and detach unchanged; methods that need the session call
self._require_session() at the top and use the returned non-None
AsyncSession for the rest of their body.

This pattern exists for services that may outlive their session (e.g.
during long-running LLM-call boundaries — see CoherenceService).
Services with short-lived calls do not need it (e.g. SymbolQueryService).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


# ID: 3039eb67-81b4-4411-8165-929df3055ce5
class SessionAttachedService:
    """Body-layer base for services with a detachable AsyncSession.

    Constructor takes the session and stores it on self.session. After
    detach() the stored session is None; methods that need it must call
    self._require_session() which returns the live AsyncSession or
    raises a RuntimeError naming the concrete subclass.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session: AsyncSession | None = session

    # ID: 139f585d-f79c-49eb-be23-de5db6aa347b
    def detach(self) -> None:
        """Release the database session reference."""
        self.session = None

    # ID: 13f09345-1641-491c-81b8-50d7caefbecb
    def _require_session(self) -> AsyncSession:
        """Return the attached AsyncSession or raise if detached.

        The error message uses type(self).__name__ so subclasses get
        a correctly-attributed error without overriding this method.
        """
        if self.session is None:
            raise RuntimeError(
                f"{type(self).__name__} error: Session has been detached."
            )
        return self.session
