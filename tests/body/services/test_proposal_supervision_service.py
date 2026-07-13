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
