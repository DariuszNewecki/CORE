from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mind.logic.engines.workflow_gate.checks.audit import AuditHistoryCheck


# ID: 38b651b4-882f-4347-8d5d-1d20c1c1f73f
async def test_AuditHistoryCheck_verify():
    check = AuditHistoryCheck()

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_context = MagicMock()
    mock_context.db_session = mock_session

    params = {"_context": mock_context}

    result = await check.verify(file_path=None, params=params)

    assert result == []
    mock_session.execute.assert_awaited_once()


import pytest


@pytest.mark.asyncio
# ID: 7b3e4616-74ac-4046-8e7e-819a8b5138bc
async def test_AuditHistoryCheck() -> None:
    check = AuditHistoryCheck()

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    context = MagicMock()
    context.db_session = mock_session

    result = await check.verify(None, {"_context": context})

    assert result == []
    mock_session.execute.assert_awaited_once()
