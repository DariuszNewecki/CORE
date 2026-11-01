from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.deciders.governance_decider import GovernanceDecider


# ID: 920d100b-c38d-4536-a5ef-afaa78c110e9
async def test_GovernanceDecider_execute():
    decider = GovernanceDecider()
    decider.tracer = MagicMock()

    result = MagicMock()
    result.component_id = "some_validator"
    result.ok = True
    result.confidence = 0.9
    result.data = {}
    result.metadata = {}

    evaluation_results = [result]

    with patch("will.deciders.governance_decider.time.time", return_value=1000.0):
        out = await decider.execute(evaluation_results, risk_tier="STANDARD")

    assert out.ok is True
    assert out.data["decision"] == "PROCEED"
    assert out.data["can_proceed"] is True
    assert out.data["blockers"] == []
    assert out.data["authorization_token"] is not None
    decider.tracer.record.assert_called_once()



import pytest


@pytest.mark.asyncio
# ID: 5aeec669-1a2e-46bb-8f7e-45eb3c9dbc68
async def test_GovernanceDecider():
    decider = GovernanceDecider()
    decider.tracer = MagicMock()

    ok_result = MagicMock()
    ok_result.component_id = "some_evaluator"
    ok_result.ok = True
    ok_result.confidence = 0.9
    ok_result.data = {}
    ok_result.metadata = {"violation_count": 0}

    result = await decider.execute(
        evaluation_results=[ok_result],
        risk_tier="STANDARD",
    )

    assert result.ok is True
    assert result.data["decision"] == "PROCEED"
    assert result.data["can_proceed"] is True
    assert result.data["authorization_token"] is not None
    assert result.data["blockers"] == []
    assert result.data["critical_blocks"] == []
    decider.tracer.record.assert_called_once()
