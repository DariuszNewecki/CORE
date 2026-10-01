from __future__ import annotations

from mind.logic.engines.workflow_gate.checks.canary import CanaryDeploymentCheck


# ID: 1c69dc38-ae33-4e72-83dd-37540140de89
async def test_CanaryDeploymentCheck_verify() -> None:
    check = CanaryDeploymentCheck()
    result = await check.verify(file_path=None, params={"canary_passed": True})
    assert result == []


from pathlib import Path

import pytest


@pytest.mark.asyncio
# ID: 708c5369-44ec-4e6c-b0f1-85f19bce6280
async def test_CanaryDeploymentCheck() -> None:
    check = CanaryDeploymentCheck()

    violations = await check.verify(None, {"canary_passed": True})
    assert violations == []

    violations = await check.verify(Path("/tmp/whatever.md"), {"canary_passed": False})
    assert len(violations) == 1
    assert "Canary audit required" in violations[0]
