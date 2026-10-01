from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from mind.logic.engines.workflow_gate.checks.import_resolution import (
    ImportResolutionCheck,
)


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
