from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.governance.llm_resource_runner import run_author_llm_resource


@pytest.mark.asyncio
# ID: ee0adac1-9be4-450a-8d9d-9f2b7334e9f4
async def test_run_author_llm_resource():
    context = MagicMock()
    definition = {"name": "example", "foo": "bar"}
    expected = MagicMock()

    mock_executor_instance = MagicMock()
    mock_executor_instance.execute = AsyncMock(return_value=expected)

    with patch(
        "body.atomic.executor.ActionExecutor",
        return_value=mock_executor_instance,
    ) as mock_executor_cls:
        result = await run_author_llm_resource(context, True, definition)

    mock_executor_cls.assert_called_once_with(context)
    mock_executor_instance.execute.assert_awaited_once_with(
        "author.llm_resource", write=True, definition=definition
    )
    assert result is expected
