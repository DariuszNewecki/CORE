from __future__ import annotations


import asyncio
from unittest.mock import AsyncMock, MagicMock

from mind.logic.engines.workflow_gate.checks.tests import TestVerificationCheck


# ID: 89ace442-359b-4282-8b36-814c67f70b95
def test_TestVerificationCheck_verify():
    check = TestVerificationCheck()

    mock_row = (True, None)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    context = MagicMock()
    context.db_session = mock_session

    params = {"_context": context}

    result = asyncio.run(check.verify(None, params))

    assert result == []
    mock_session.execute.assert_awaited_once()
