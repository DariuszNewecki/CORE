from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from mind.logic.engines.workflow_gate.checks.import_resolution import (
    ImportResolutionCheck,
)


@pytest.mark.asyncio
# ID: 6208dc95-6022-43d6-af50-8f7729bae9df
async def test_ImportResolutionCheck_verify() -> None:
    check = ImportResolutionCheck.__new__(ImportResolutionCheck)
    check.check_type = "import_resolution"

    check._run_tool = AsyncMock(return_value=["some violation"])

    params: dict[str, Any] = {
        "tools": [
            {"tool": "some_tool", "args": ["--flag"]},
        ]
    }

    result = await ImportResolutionCheck.verify(check, None, params)

    check._run_tool.assert_awaited_once_with(
        {"tool": "some_tool", "args": ["--flag"]}, "src"
    )
    assert list(result) == ["some violation"]
