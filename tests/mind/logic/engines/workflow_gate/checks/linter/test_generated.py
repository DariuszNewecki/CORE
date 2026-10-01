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
