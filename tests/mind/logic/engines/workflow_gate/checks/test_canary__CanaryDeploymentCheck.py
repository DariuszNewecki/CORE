"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/workflow_gate/checks/canary.py
- Symbol: CanaryDeploymentCheck
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:40:57
"""

from pathlib import Path

import pytest

from mind.logic.engines.workflow_gate.checks.canary import CanaryDeploymentCheck


# Detected return type: list[str] (empty list for success, list with violation message for failure)
# Function is async: all test functions must be async and use await


@pytest.mark.asyncio
async def test_canary_passed_true():
    """Test when canary_passed is True - should return empty list."""
    check = CanaryDeploymentCheck()
    result = await check.verify(
        file_path=Path("/full/path/to/file.txt"), params={"canary_passed": True}
    )
    assert result == []


@pytest.mark.asyncio
async def test_canary_passed_false():
    """Test when canary_passed is False - should return violation message."""
    check = CanaryDeploymentCheck()
    result = await check.verify(
        file_path=Path("/full/path/to/file.txt"), params={"canary_passed": False}
    )
    assert result == [
        "Canary audit required: Operation must pass in staging/isolation first."
    ]


@pytest.mark.asyncio
async def test_canary_passed_missing():
    """Test when canary_passed key is missing - should return violation message."""
    check = CanaryDeploymentCheck()
    result = await check.verify(
        file_path=Path("/full/path/to/file.txt"), params={"other_param": "value"}
    )
    assert result == [
        "Canary audit required: Operation must pass in staging/isolation first."
    ]


@pytest.mark.asyncio
async def test_canary_passed_explicit_false():
    """Test when canary_passed is explicitly set to False."""
    check = CanaryDeploymentCheck()
    result = await check.verify(file_path=None, params={"canary_passed": False})
    assert result == [
        "Canary audit required: Operation must pass in staging/isolation first."
    ]


@pytest.mark.asyncio
async def test_canary_passed_with_none_file_path():
    """Test with None file_path parameter."""
    check = CanaryDeploymentCheck()
    result = await check.verify(file_path=None, params={"canary_passed": True})
    assert result == []


@pytest.mark.asyncio
async def test_canary_passed_false_with_additional_params():
    """Test when canary_passed is False with additional parameters."""
    check = CanaryDeploymentCheck()
    result = await check.verify(
        file_path=Path("/another/full/path.json"),
        params={
            "canary_passed": False,
            "environment": "production",
            "version": "1.2.3",
        },
    )
    assert result == [
        "Canary audit required: Operation must pass in staging/isolation first."
    ]


@pytest.mark.asyncio
async def test_canary_passed_true_with_additional_params():
    """Test when canary_passed is True with additional parameters."""
    check = CanaryDeploymentCheck()
    result = await check.verify(
        file_path=Path("/full/path/config.yaml"),
        params={
            "canary_passed": True,
            "environment": "staging",
            "rollback_enabled": True,
        },
    )
    assert result == []
