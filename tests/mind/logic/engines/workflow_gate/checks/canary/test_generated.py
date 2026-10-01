from __future__ import annotations

from mind.logic.engines.workflow_gate.checks.canary import CanaryDeploymentCheck


# ID: 1c69dc38-ae33-4e72-83dd-37540140de89
async def test_CanaryDeploymentCheck_verify() -> None:
    check = CanaryDeploymentCheck()
    result = await check.verify(file_path=None, params={"canary_passed": True})
    assert result == []
