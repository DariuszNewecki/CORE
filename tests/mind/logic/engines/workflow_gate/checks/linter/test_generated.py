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


import asyncio


# ID: 20664ff6-1b47-42a1-b6d2-cc63cd403ef0
def test_LinterComplianceCheck_verify():
    check_instance = LinterComplianceCheck()

    fake_process = MagicMock()
    fake_process.returncode = 0
    fake_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.linter.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=fake_process),
    ):
        violations = asyncio.run(check_instance.verify(Path("src/foo.py"), {}))

    assert violations == []
