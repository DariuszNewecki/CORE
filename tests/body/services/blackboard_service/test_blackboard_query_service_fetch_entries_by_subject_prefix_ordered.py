# tests/body/services/blackboard_service/test_blackboard_query_service_fetch_entries_by_subject_prefix_ordered.py
"""Unit tests for BlackboardQueryService.fetch_entries_by_subject_prefix_ordered.

The sequence-reconstruction query for one correlated run (GoalExecutionWorker's
`goal_run.<run_id>.%` subjects). No real DB required — ServiceRegistry.session
is patched to a fake async context manager whose session.execute() returns
canned rows, mirroring test_blackboard_query_service_fetch_entry_by_id.py.
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
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


@asynccontextmanager
async def _session_ctx(session: AsyncMock):
    yield session


def _patched_session(rows: list[tuple]):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult(rows))
    return patch.object(ServiceRegistry, "session", return_value=_session_ctx(session))


async def test_returns_empty_list_when_no_entries_match() -> None:
    with _patched_session([]):
        result = await BlackboardQueryService().fetch_entries_by_subject_prefix_ordered(
            "goal_run.rid-missing.%"
        )
    assert result == []


async def test_maps_rows_preserving_creation_order() -> None:
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 12, 10, 0, 5, tzinfo=UTC)
    rows = [
        (
            "entry-1",
            "report",
            "goal_run.rid-1.start",
            "resolved",
            {"run_id": "rid-1", "goal": "demo"},
            t0,
        ),
        (
            "entry-2",
            "report",
            "goal_run.rid-1.outcome",
            "resolved",
            {"run_id": "rid-1", "ok": True},
            t1,
        ),
    ]

    with _patched_session(rows):
        result = await BlackboardQueryService().fetch_entries_by_subject_prefix_ordered(
            "goal_run.rid-1.%"
        )

    assert [e["subject"] for e in result] == [
        "goal_run.rid-1.start",
        "goal_run.rid-1.outcome",
    ]
    assert result[0] == {
        "id": "entry-1",
        "entry_type": "report",
        "subject": "goal_run.rid-1.start",
        "status": "resolved",
        "payload": {"run_id": "rid-1", "goal": "demo"},
        "created_at": t0.isoformat(),
    }


async def test_handles_string_payload_and_null_created_at() -> None:
    rows = [
        ("entry-9", "finding", "goal_run.rid-9.outcome", "abandoned", '{"k": "v"}', None),
    ]

    with _patched_session(rows):
        result = await BlackboardQueryService().fetch_entries_by_subject_prefix_ordered(
            "goal_run.rid-9.%"
        )

    assert result[0]["payload"] == {"k": "v"}
    assert result[0]["created_at"] is None
