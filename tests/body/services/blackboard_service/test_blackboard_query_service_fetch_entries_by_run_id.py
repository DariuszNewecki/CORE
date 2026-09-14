# tests/body/services/blackboard_service/test_blackboard_query_service_fetch_entries_by_run_id.py
"""Unit tests for BlackboardQueryService.fetch_entries_by_run_id (#893).

The full-row retrieval leg of the run export. No real DB — ServiceRegistry.
session is patched to a fake async context manager whose session.execute()
returns canned rows, mirroring the sibling
test_blackboard_query_service_fetch_entries_by_subject_prefix_ordered.py.
Beyond row mapping, these pin the SQL contract the export's header promises
to the reader: both identity legs bound, total order by (created_at, id).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from body.services.blackboard_service.blackboard_query_service import (
    BlackboardQueryService,
)
from body.services.service_registry import ServiceRegistry


RID = "48bd49bf-c02d-4ec9-bf56-4cdaa3631615"


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
    return session, patch.object(
        ServiceRegistry, "session", return_value=_session_ctx(session)
    )


async def test_returns_empty_list_when_nothing_matches() -> None:
    _, patcher = _patched_session([])
    with patcher:
        result = await BlackboardQueryService().fetch_entries_by_run_id(RID)
    assert result == []


async def test_binds_both_identity_legs_and_orders_by_created_at_then_id() -> None:
    session, patcher = _patched_session([])
    with patcher:
        await BlackboardQueryService().fetch_entries_by_run_id(RID)
    (stmt, params), _ = session.execute.call_args
    sql = " ".join(str(stmt).split())
    assert "subject LIKE :subject_prefix" in sql
    assert "payload->>'run_id' = :run_id" in sql
    assert "ORDER BY created_at ASC, id ASC" in sql
    assert params == {"subject_prefix": f"goal_run.{RID}.%", "run_id": RID}


async def test_maps_full_rows_with_string_ids_and_iso_timestamps() -> None:
    entry_id = uuid.UUID("11111111-2222-4333-8444-555555555555")
    worker_id = uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
    t0 = datetime(2026, 9, 13, 11, 24, 36, 969586, tzinfo=UTC)
    rows = [
        (
            entry_id,
            worker_id,
            "report",
            "execution",
            "resolved",
            f"goal_run.{RID}.start",
            f'{{"run_id": "{RID}"}}',  # jsonb may arrive as text
            None,
            None,
            None,
            None,
            None,
            t0,
            t0,
            t0,
            1,
            0,
        )
    ]
    _, patcher = _patched_session(rows)
    with patcher:
        result = await BlackboardQueryService().fetch_entries_by_run_id(RID)
    assert result == [
        {
            "id": str(entry_id),
            "worker_uuid": str(worker_id),
            "entry_type": "report",
            "phase": "execution",
            "status": "resolved",
            "subject": f"goal_run.{RID}.start",
            "payload": {"run_id": RID},
            "first_payload": None,
            "resolution_mechanism": None,
            "claimed_by": None,
            "claimed_at": None,
            "resolved_at": None,
            "created_at": t0.isoformat(),
            "updated_at": t0.isoformat(),
            "last_seen_at": t0.isoformat(),
            "occurrence_count": 1,
            "orphan_release_count": 0,
        }
    ]
