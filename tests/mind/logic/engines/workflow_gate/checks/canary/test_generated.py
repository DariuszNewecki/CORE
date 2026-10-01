from __future__ import annotations

from pathlib import Path

import pytest

from mind.logic.engines.workflow_gate.checks.canary import CanaryDeploymentCheck


@pytest.mark.asyncio
# ID: 708c5369-44ec-4e6c-b0f1-85f19bce6280
async def test_CanaryDeploymentCheck() -> None:
    check = CanaryDeploymentCheck()

    violations = await check.verify(None, {"canary_passed": True})
    assert violations == []

    violations = await check.verify(Path("/tmp/whatever.md"), {"canary_passed": False})
    assert len(violations) == 1
    assert "Canary audit required" in violations[0]


import asyncio

import pytest


# ID: 9158f894-3ae4-42db-b8da-790c60b5c65e
def test_CanaryDeploymentCheck_verify() -> None:
    check = CanaryDeploymentCheck()
    result = asyncio.get_event_loop().run_until_complete(
        check.verify(None, {"canary_passed": True})
    )
    assert result == []

    result_fail = asyncio.get_event_loop().run_until_complete(
        check.verify(None, {"canary_passed": False})
    )
    assert len(result_fail) == 1
    assert "Canary audit required" in result_fail[0]
