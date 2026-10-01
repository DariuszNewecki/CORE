from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.checks.ruff_format import RuffFormatCheck


# ID: 41f97b50-f8db-4818-8457-fbb60a998068
async def test_RuffFormatCheck_verify() -> None:
    # Build an instance without invoking a real constructor contract.
    check = RuffFormatCheck.__new__(RuffFormatCheck)
    check.check_type = "ruff_format"

    # Fake subprocess handle returned by asyncio.create_subprocess_exec.
    process = MagicMock()
    process.returncode = 0
    process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.ruff_format.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=process),
    ) as mock_exec:
        violations = await RuffFormatCheck.verify(check, Path("src/foo.py"), {})

    assert violations == []

    # Verify ruff was invoked in format --check mode on the target file.
    called_args = mock_exec.await_args.args
    assert "ruff" in called_args
    assert "format" in called_args
    assert "--check" in called_args
