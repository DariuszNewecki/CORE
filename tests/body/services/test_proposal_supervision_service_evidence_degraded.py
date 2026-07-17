"""Tests for ProposalSupervisionService.fetch_completed_with_degraded_consequence
(ADR-148 D7, #790).

No real DB required — ServiceRegistry.session is mocked; the SQL text
itself is exercised at the integration level by CommitAuthorshipAuditWorker
in production, not here. Sibling to
test_proposal_supervision_service.py's fetch_completed_without_consequence tests.
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


async def test_fetch_completed_with_degraded_consequence_maps_rows() -> None:
    """Rows returned by the query are mapped into the expected dict shape."""
    completed_at = datetime(2026, 7, 17, 1, 0, 0, tzinfo=UTC)
    updated_at = datetime(2026, 7, 17, 1, 0, 5, tzinfo=UTC)
    session = _mock_session([("pid-1", completed_at, updated_at)])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_completed_with_degraded_consequence(limit=100)

    assert result == [
        {
            "proposal_id": "pid-1",
            "execution_completed_at": completed_at,
            "updated_at": updated_at,
        }
    ]


async def test_fetch_completed_with_degraded_consequence_selects_on_source_column() -> (
    None
):
    """The query must select strictly on consequence_source =
    'reaper_reconstructed' — never on SHA nullness, since capture_git_sha()
    already returns None fail-soft on the normal execution path."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        await svc.fetch_completed_with_degraded_consequence(limit=100)

    call_args = session.execute.await_args
    query_text = str(call_args.args[0])
    assert "consequence_source" in query_text
    assert "reaper_reconstructed" in query_text
    assert "pre_execution_sha" not in query_text


async def test_fetch_completed_with_degraded_consequence_passes_limit() -> None:
    """The limit param is bound through to the query."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        await svc.fetch_completed_with_degraded_consequence(limit=42)

    call_args = session.execute.await_args
    params = call_args.args[1]
    assert params["limit"] == 42


async def test_fetch_completed_with_degraded_consequence_empty_result() -> None:
    """No degraded rows returns an empty list."""
    session = _mock_session([])

    svc = ProposalSupervisionService()
    with patch(
        "body.services.service_registry.ServiceRegistry.session",
        MagicMock(return_value=_session_ctx(session)),
    ):
        result = await svc.fetch_completed_with_degraded_consequence(limit=100)

    assert result == []
