from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.checks.linter import LinterComplianceCheck
from shared.utils.subprocess_utils import SubprocessResult


# ID: 52b0ab60-ce54-491a-993a-47e38e72ab74
async def test_LinterComplianceCheck_verify():
    """Both tools run through the sanctioned subprocess surface."""
    check = LinterComplianceCheck()
    check.check_type = "linter"

    with patch(
        "mind.logic.engines.workflow_gate.checks.linter.run_command_async",
        new=AsyncMock(
            return_value=SubprocessResult(stdout="", stderr="", returncode=0)
        ),
    ) as mock_run:
        violations = await check.verify(Path("src/foo.py"), {})

    assert violations == []
    assert [c.args[0] for c in mock_run.await_args_list] == [
        ["ruff", "check", "src/foo.py"],
        ["black", "--check", "src/foo.py"],
    ]


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
