from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.checks.linter import LinterComplianceCheck


# ID: 52b0ab60-ce54-491a-993a-47e38e72ab74
async def test_LinterComplianceCheck_verify():
    check = LinterComplianceCheck()
    check.check_type = "linter"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with (
        patch(
            "mind.logic.engines.workflow_gate.checks.linter.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_process),
        ) as mock_exec,
        patch(
            "mind.logic.engines.workflow_gate.checks.linter.asyncio.wait_for",
            new=AsyncMock(return_value=(b"", b"")),
        ),
    ):
        violations = await check.verify(Path("src/foo.py"), {})

    assert violations == []
    assert mock_exec.await_count == 2





# ID: 2453298a-21c0-430f-90ce-505768a720ab
async def test_LinterComplianceCheck():
    check = LinterComplianceCheck()

    ruff_process = MagicMock()
    ruff_process.returncode = 0
    ruff_process.communicate = AsyncMock(return_value=(b"", b""))

    black_process = MagicMock()
    black_process.returncode = 0
    black_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.linter.asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=[ruff_process, black_process]),
    ) as mock_exec:
        violations = await check.verify(Path("src/foo.py"), {})

    assert violations == []
    assert mock_exec.await_count == 2
