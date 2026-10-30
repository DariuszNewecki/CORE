from __future__ import annotations

from unittest.mock import MagicMock

from will.orchestration.process_orchestrator import evaluate_workflow_result


# ID: e88094d1-c6cb-4471-b6ff-2c2404795273
def test_evaluate_workflow_result():
    result = MagicMock()
    result.ok = True
    result.confidence = 0.9
    result.data = {"file_type": "python", "complexity": 3}

    success, reason = evaluate_workflow_result(
        result,
        expected_keys=["file_type", "complexity"],
        min_confidence=0.7,
    )

    assert success is True
    assert reason == "Success"


from unittest.mock import patch

from will.orchestration.process_orchestrator import ProcessOrchestrator


# ID: 63a201f4-f129-4f67-9d6d-18a7125e3417
def test_ProcessOrchestrator_reset():
    orchestrator = ProcessOrchestrator()
    orchestrator.session_state = {"key": "value"}
    orchestrator.execution_history = [MagicMock()]

    with patch("will.orchestration.process_orchestrator.logger") as mock_logger:
        orchestrator.reset()

    assert orchestrator.session_state == {}
    assert orchestrator.execution_history == []
    mock_logger.debug.assert_called_once_with("ProcessOrchestrator state reset")


# ID: d071d0c9-a3bc-4e6b-974f-539584b98933
def test_ProcessOrchestrator_get_workflow_summary():
    orchestrator = ProcessOrchestrator()

    phase_a = MagicMock()
    phase_a.value = "analysis"
    phase_b = MagicMock()
    phase_b.value = "implementation"

    r1 = MagicMock()
    r1.ok = True
    r1.duration_sec = 1.5
    r1.confidence = 0.9
    r1.phase = phase_a

    r2 = MagicMock()
    r2.ok = False
    r2.duration_sec = 0.5
    r2.confidence = 0.5
    r2.phase = phase_b

    orchestrator.execution_history = [r1, r2]

    summary = orchestrator.get_workflow_summary()

    assert summary["total_steps"] == 2
    assert summary["successful_steps"] == 1
    assert summary["failed_steps"] == 1
    assert summary["total_duration"] == 2.0
    assert summary["avg_confidence"] == 0.7
    assert set(summary["phases_used"]) == {"analysis", "implementation"}


from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
# ID: 2c1279dc-36ff-4595-97b5-ce89300bda2c
async def test_ProcessOrchestrator_run_adaptive():
    orchestrator = ProcessOrchestrator()

    initial_result = MagicMock()
    initial_result.ok = True
    initial_result.confidence = 0.9
    initial_result.next_suggested = None
    initial_result.data = {"key": "value"}
    initial_result.metadata = {"meta": 1}

    initial_component = MagicMock()
    initial_component.component_id = "initial"
    initial_component.execute = AsyncMock(return_value=initial_result)

    result = await orchestrator.run_adaptive(
        initial_component=initial_component,
        initial_inputs={"input": 1},
        max_steps=3,
        confidence_threshold=0.5,
    )

    assert result is initial_result
    initial_component.execute.assert_awaited_once()
    call_kwargs = initial_component.execute.await_args.kwargs
    assert call_kwargs["input"] == 1
    assert call_kwargs["session_state"] is orchestrator.session_state
    assert orchestrator.execution_history == [initial_result]
    assert orchestrator.session_state == {"meta": 1}
