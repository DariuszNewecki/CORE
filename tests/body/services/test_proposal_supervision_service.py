"""Tests for ProposalSupervisionService.fetch_completed_without_consequence
(ADR-148 D5, #763).

No real DB required — ServiceRegistry.session is mocked; the SQL text
itself is exercised at the integration level by CommitAuthorshipAuditWorker
in production, not here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from body.services.proposal_supervision_service import ProposalSupervisionService


@asynccontextmanager
async def _session_ctx(session: MagicMock):  # type: ignore[no-untyped-def]
    yield session


def _mock_session(rows: list[tuple]) -> MagicMock:
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


async def test_fetch_completed_without_consequence_maps_rows() -> None:
    """Rows returned by the query are mapped into the expected dict shape."""
    completed_at = datetime(2026, 7, 13, 1, 0, 0, tzinfo=UTC)
    updated_at = datetime(2026, 7, 13, 1, 0, 5, tzinfo=UTC)
    session = _mock_session([("pid-1", completed_at, updated_at)])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_completed_without_consequence(limit=100)

    assert result == [
        {
            "proposal_id": "pid-1",
            "execution_completed_at": completed_at,
            "updated_at": updated_at,
        }
    ]


async def test_fetch_completed_without_consequence_passes_barrier_cutoff() -> None:
    """The query binds the ADR-148 barrier-live-at cutoff, not an open-ended scan."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        await svc.fetch_completed_without_consequence(limit=50)

    call_args = session.execute.await_args
    params = call_args.args[1]
    assert params["limit"] == 50
    assert params["barrier_live_at"] == svc._ADR_148_BARRIER_LIVE_AT
    assert svc._ADR_148_BARRIER_LIVE_AT == datetime(
        2026, 7, 12, 20, 25, 34, tzinfo=UTC
    )


async def test_fetch_completed_without_consequence_checks_row_existence_not_marker() -> (
    None
):
    """#789: the query must verify the actual core.proposal_consequences row
    is absent (NOT EXISTS), not merely that consequence_recorded_at is NULL —
    a marker-only check would pass even if a future bug set the timestamp
    without writing the row, defeating the audit's purpose."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        await svc.fetch_completed_without_consequence(limit=100)

    call_args = session.execute.await_args
    query_text = str(call_args.args[0])
    assert "NOT EXISTS" in query_text
    assert "core.proposal_consequences" in query_text


async def test_fetch_completed_without_consequence_empty_result() -> None:
    """No violating rows returns an empty list."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_completed_without_consequence(limit=100)

    assert result == []


async def test_fetch_stuck_undeferred_maps_rows() -> None:
    """Rows returned by the query are mapped into the expected dict shape,
    including the finding_ids array (#764)."""
    created_at = datetime(2026, 7, 13, 1, 0, 0, tzinfo=UTC)
    session = _mock_session(
        [("pid-undeferred-1", ["fid-a", "fid-b"], created_at, 300)]
    )

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_stuck_undeferred(sla_sec=120, limit=100)

    assert result == [
        {
            "proposal_id": "pid-undeferred-1",
            "finding_ids": ["fid-a", "fid-b"],
            "created_at": created_at,
            "seconds_stuck": 300,
        }
    ]


async def test_fetch_stuck_undeferred_null_finding_ids_becomes_empty_list() -> None:
    """A NULL finding_ids column (shouldn't happen given the WHERE clause,
    but defensively) maps to an empty list, not None."""
    created_at = datetime(2026, 7, 13, 1, 0, 0, tzinfo=UTC)
    session = _mock_session([("pid-1", None, created_at, 200)])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_stuck_undeferred(sla_sec=120, limit=100)

    assert result[0]["finding_ids"] == []


async def test_fetch_stuck_undeferred_passes_sla_cutoff() -> None:
    """The query binds sla_sec and limit as provided by the caller."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        await svc.fetch_stuck_undeferred(sla_sec=120, limit=75)

    call_args = session.execute.await_args
    params = call_args.args[1]
    assert params["limit"] == 75
    assert "cutoff" in params


async def test_fetch_stuck_undeferred_empty_result() -> None:
    """No stuck rows returns an empty list."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_stuck_undeferred(sla_sec=120, limit=100)

    assert result == []
