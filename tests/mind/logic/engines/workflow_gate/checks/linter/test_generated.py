from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.checks.linter import LinterComplianceCheck


# ID: 79749754-a683-404b-81d1-6380cf76132a
async def test_LinterComplianceCheck_verify():
    check = LinterComplianceCheck.__new__(LinterComplianceCheck)
    check.check_type = "linter"

    # ID: 65ec4ab5-853d-492f-aec7-3a79e266851e
    async def fake_subprocess_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"", b""))
        return proc

    with patch(
        "mind.logic.engines.workflow_gate.checks.linter.asyncio.create_subprocess_exec",
        side_effect=fake_subprocess_exec,
    ):
        violations = await LinterComplianceCheck.verify(check, Path("src/foo.py"), {})

    assert violations == []
