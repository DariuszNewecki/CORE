# tests/body/services/blackboard_service/test_blackboard_query_service_max_attempt_count_by_subject.py
"""Unit tests for BlackboardQueryService.query_max_attempt_count_by_subject.

Third shape of the ADR-104 D9 counter-inheritance read (#901): the highest
``remediation_attempt_count`` among *abandoned* findings carrying exactly
one subject. No real DB — ServiceRegistry.session is patched to a fake
async context manager whose session.execute() returns a canned scalar row,
mirroring the sibling query-service tests; the SQL text and bind
parameters are asserted so the predicate (finding, abandoned, exact
subject) cannot silently widen.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
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


def _patched_session(row: tuple | None) -> tuple[AsyncMock, object]:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult(row))
    return session, patch.object(
        ServiceRegistry, "session", return_value=_session_ctx(session)
    )


_SUBJECT = "python::architecture.channels.logic_no_terminal_rendering::src/x.py"


# ID: 8980031d-d9b1-4f2a-be0b-22470d23ae8d
async def test_returns_the_max_count_for_the_subject() -> None:
    session, ctx = _patched_session((3,))
    with ctx:
        got = await BlackboardQueryService().query_max_attempt_count_by_subject(
            _SUBJECT
        )
    assert got == 3
    sql = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "status = 'abandoned'" in sql
    assert "entry_type = 'finding'" in sql
    assert "subject = :subject" in sql
    assert params == {"subject": _SUBJECT}


# ID: e98b5775-b317-4098-97b1-1f29c2f71d44
async def test_returns_zero_when_no_abandoned_lineage_exists() -> None:
    _, ctx = _patched_session((0,))
    with ctx:
        assert (
            await BlackboardQueryService().query_max_attempt_count_by_subject(_SUBJECT)
            == 0
        )


# ID: 37fc1a26-3674-4341-ad70-3f5a35d40a2b
async def test_returns_zero_on_a_null_row() -> None:
    _, ctx = _patched_session(None)
    with ctx:
        assert (
            await BlackboardQueryService().query_max_attempt_count_by_subject(_SUBJECT)
            == 0
        )
