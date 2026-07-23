# tests/body/services/blackboard_service/test_blackboard_query_service_fetch_entry_by_id.py
"""Unit tests for BlackboardQueryService.fetch_entry_by_id.

No real DB required — ServiceRegistry.session is patched to a fake async
context manager whose session.execute() returns a canned row, so this
verifies row-mapping/None-handling logic in isolation. Real-DB coverage
comes from the isolated consequence-chain demo's end-to-end scenario test
(ADR-155 Phase 2), which calls this method for real against disposable
infrastructure — not the shared LAN test database.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from body.services.blackboard_service.blackboard_query_service import (
    BlackboardQueryService,
)
from body.services.service_registry import ServiceRegistry


class _FakeResult:
    def __init__(self, row: tuple | None) -> None:
        self._row = row

    def fetchone(self) -> tuple | None:
        return self._row


@asynccontextmanager
async def _session_ctx(session: AsyncMock):
    yield session


def _patched_session(row: tuple | None):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult(row))
    return patch.object(
        ServiceRegistry, "session", return_value=_session_ctx(session)
    ), session


async def test_fetch_entry_by_id_returns_none_when_missing() -> None:
    patcher, _ = _patched_session(None)
    with patcher:
        result = await BlackboardQueryService().fetch_entry_by_id("missing-id")
    assert result is None


async def test_fetch_entry_by_id_maps_row_to_dict() -> None:
    created = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
    row = (
        "entry-123",
        "python::linkage.assign_ids::src/body/analyzers/demo_onramp_abc.py",
        "deferred_to_proposal",
        {"proposal_id": "pid-456", "rule": "linkage.assign_ids"},
        created,
    )
    patcher, _ = _patched_session(row)
    with patcher:
        result = await BlackboardQueryService().fetch_entry_by_id("entry-123")

    assert result == {
        "id": "entry-123",
        "subject": "python::linkage.assign_ids::src/body/analyzers/demo_onramp_abc.py",
        "status": "deferred_to_proposal",
        "payload": {"proposal_id": "pid-456", "rule": "linkage.assign_ids"},
        "created_at": created.isoformat(),
    }


async def test_fetch_entry_by_id_handles_string_payload() -> None:
    row = ("entry-789", "some::subject", "open", '{"k": "v"}', None)
    patcher, _ = _patched_session(row)
    with patcher:
        result = await BlackboardQueryService().fetch_entry_by_id("entry-789")

    assert result is not None
    assert result["payload"] == {"k": "v"}
    assert result["created_at"] is None
