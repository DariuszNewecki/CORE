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


from pathlib import Path
from unittest.mock import patch


# ID: 7b64a660-3b13-4f9a-a6a2-90befdd9ecac
async def test_ImportResolutionCheck() -> None:
    check = ImportResolutionCheck()
    specs = [{"tool": "import-linter", "args": ["--check"]}]

    with patch.object(
        ImportResolutionCheck,
        "_run_tool",
        new=AsyncMock(return_value=[]),
    ) as mock_run_tool:
        result = await check.verify(Path("src"), {"tools": specs})

    assert list(result) == []
    mock_run_tool.assert_awaited_once()
    called_spec, called_target = mock_run_tool.await_args.args
    assert called_spec == specs[0]
    assert called_target == "src"


import asyncio


# ID: a14cc808-155e-4a15-92a9-2483f42a2eaf
def test_ImportResolutionCheck_verify() -> None:
    check = ImportResolutionCheck.__new__(ImportResolutionCheck)
    check.check_type = "import_resolution"
    check._run_tool = AsyncMock(return_value=["some violation"])

    params = {"tools": [{"tool": "ruff", "args": ["check"]}]}
    result = asyncio.run(check.verify(None, params))

    assert list(result) == ["some violation"]
    check._run_tool.assert_awaited_once()
    called_spec, called_target = check._run_tool.await_args.args
    assert called_spec == {"tool": "ruff", "args": ["check"]}
    assert called_target == "src"





# ID: ebfb984e-dc39-47dc-9d1a-1e09f560ced4
def test_ImportResolutionCheck_verify():
    check = ImportResolutionCheck.__new__(ImportResolutionCheck)
    check.check_type = "import_resolution"

    spec = {"tool": "ruff", "args": ["check"]}
    params = {"tools": [spec]}

    check._run_tool = AsyncMock(return_value=["violation one", "violation two"])

    result = asyncio.run(check.verify(Path("src/foo.py"), params))

    assert list(result) == ["violation one", "violation two"]
    check._run_tool.assert_awaited_once_with(spec, "src/foo.py")
