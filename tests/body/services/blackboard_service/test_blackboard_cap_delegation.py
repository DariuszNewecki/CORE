"""Unit tests for the capped-lineage delegation surface (ADR-104 D9 as amended
2026-10-03): ``delegate_remediation_capped_findings`` and
``query_last_failed_proposal_for_subject``.

No real DB — ServiceRegistry.session is patched to a fake async context
manager (the sibling query-service tests' pattern); the SQL text and binds
are asserted so the transition cannot silently drift back to ``abandoned``
or drop the human co-assignment.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from body.services.blackboard_service import BlackboardService
from body.services.service_registry import ServiceRegistry


@asynccontextmanager
async def _ctx(obj):  # type: ignore[no-untyped-def]
    yield obj


def _session(result: MagicMock) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.begin = MagicMock(return_value=_ctx(None))
    return session


async def test_delegate_moves_capped_findings_to_the_governor() -> None:
    result = MagicMock()
    result.fetchall.return_value = [("e1",), ("e2",)]
    session = _session(result)
    delegation = {"reason": "failure_cap_delegated", "detail": "boom"}
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        got = await BlackboardService().delegate_remediation_capped_findings(
            ["e1", "e2"], 3, delegation
        )
    assert got == ["e1", "e2"]
    sql = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "status = 'indeterminate'" in sql
    assert "resolution_mechanism = 'human'" in sql
    assert "'abandoned'" not in sql
    assert "'{delegation}'" in sql
    assert "status IN ('open', 'claimed')" in sql
    assert params["count"] == 3
    assert json.loads(params["delegation"]) == delegation


async def test_delegate_with_no_ids_touches_nothing() -> None:
    with patch.object(ServiceRegistry, "session") as session:
        assert (
            await BlackboardService().delegate_remediation_capped_findings([], 3, {})
            == []
        )
    session.assert_not_called()


async def test_last_failed_proposal_for_subject() -> None:
    result = MagicMock()
    result.fetchone.return_value = ("pid-1", "Blocked by IntentGuard", [{"a": 1}])
    session = _session(result)
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        got = await BlackboardService().query_last_failed_proposal_for_subject(
            "python::r::f.py"
        )
    assert got == {
        "proposal_id": "pid-1",
        "failure_reason": "Blocked by IntentGuard",
        "actions": [{"a": 1}],
    }
    sql = str(session.execute.await_args.args[0])
    assert "ap.status = 'failed'" in sql
    assert "b.subject = :subject" in sql


async def test_last_failed_proposal_none_when_no_lineage() -> None:
    result = MagicMock()
    result.fetchone.return_value = None
    session = _session(result)
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        assert (
            await BlackboardService().query_last_failed_proposal_for_subject("s")
            is None
        )
