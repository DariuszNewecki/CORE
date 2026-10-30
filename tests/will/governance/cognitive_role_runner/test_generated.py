from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.governance.cognitive_role_runner import run_project_cognitive_roles


@pytest.mark.asyncio
# ID: 58981ef1-9a1e-4758-a8b5-00ad537dcddb
async def test_run_project_cognitive_roles():
    mock_context = MagicMock(name="CoreContext")
    expected_result = MagicMock(name="ActionResult")

    mock_executor = MagicMock(name="ActionExecutorInstance")
    mock_executor.execute = AsyncMock(return_value=expected_result)

    with patch(
        "body.atomic.executor.ActionExecutor", return_value=mock_executor
    ) as mock_executor_cls:
        result = await run_project_cognitive_roles(mock_context, write=True)

    mock_executor_cls.assert_called_once_with(mock_context)
    mock_executor.execute.assert_awaited_once_with(
        "project.cognitive_roles", write=True
    )
    assert result is expected_result
