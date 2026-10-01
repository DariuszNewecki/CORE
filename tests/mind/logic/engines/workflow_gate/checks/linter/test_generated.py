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


import pytest


@pytest.mark.asyncio
# ID: e674297e-1a79-4806-9f9e-5bf1c68efbc8
async def test_LinterComplianceCheck_verify() -> None:
    check = LinterComplianceCheck()

    good_process = MagicMock()
    good_process.returncode = 0
    good_process.communicate = AsyncMock(return_value=(b"", b""))

    with (
        patch(
            "mind.logic.engines.workflow_gate.checks.linter.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=good_process),
        ) as mock_exec,
        patch(
            "mind.logic.engines.workflow_gate.checks.linter.asyncio.wait_for",
            new=AsyncMock(return_value=(b"", b"")),
        ),
    ):
        violations = await check.verify(Path("src/mind/logic/foo.py"), {})

    assert violations == []
    assert mock_exec.await_count == 2





# ID: c291e5ed-35b3-410b-80e3-36f17d22520e
async def test_LinterComplianceCheck_verify():
    check = LinterComplianceCheck.__new__(LinterComplianceCheck)
    check.check_type = "linter"

    fake_process = MagicMock()
    fake_process.returncode = 0
    fake_process.communicate = AsyncMock(return_value=(b"", b""))

    with (
        patch(
            "mind.logic.engines.workflow_gate.checks.linter.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=fake_process),
        ) as mock_exec,
        patch(
            "mind.logic.engines.workflow_gate.checks.linter.asyncio.wait_for",
            new=AsyncMock(return_value=(b"", b"")),
        ),
    ):
        result = await LinterComplianceCheck.verify(check, Path("src/example.py"), {})

    assert result == []
    assert mock_exec.await_count == 2
