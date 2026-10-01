from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine


@pytest.mark.asyncio
# ID: 9064e5e7-77ed-4180-aaf0-cf4d35dcbf02
async def test_WorkflowGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    expected_result = MagicMock()
    engine._verify_async = AsyncMock(return_value=expected_result)

    file_path = Path("src/example.py")
    params: dict[str, Any] = {"some": "param"}

    result = await engine.verify(file_path, params)

    assert result is expected_result
    engine._verify_async.assert_awaited_once_with(file_path, params)
