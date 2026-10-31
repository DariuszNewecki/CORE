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


# ID: 0fe7a8f3-d75a-46c4-a3fb-fcdf401627dd
async def test_ProcessOrchestrator_run_sequence():
    orch = ProcessOrchestrator()

    component_a = MagicMock()
    component_a.component_id = "comp_a"
    component_a.execute = AsyncMock(
        return_value=MagicMock(
            ok=True,
            confidence=0.9,
            data={"a_out": 1},
            metadata={"meta_a": "x"},
        )
    )

    component_b = MagicMock()
    component_b.component_id = "comp_b"
    component_b.execute = AsyncMock(
        return_value=MagicMock(
            ok=True,
            confidence=0.8,
            data={"b_out": 2},
            metadata={"meta_b": "y"},
        )
    )

    results = await orch.run_sequence(
        [
            (component_a, {"in_a": "foo"}),
            (component_b, {"in_b": "bar"}),
        ]
    )

    assert len(results) == 2
    component_a.execute.assert_awaited_once()
    component_b.execute.assert_awaited_once()

    first_call_kwargs = component_a.execute.await_args.kwargs
    assert first_call_kwargs["in_a"] == "foo"
    assert first_call_kwargs["session_state"] is orch.session_state

    second_call_kwargs = component_b.execute.await_args.kwargs
    assert second_call_kwargs["in_b"] == "bar"
    assert second_call_kwargs["a_out"] == 1

    assert len(orch.execution_history) == 2
    assert orch.session_state == {"meta_a": "x", "meta_b": "y"}



import pytest


@pytest.mark.asyncio
# ID: 3f144516-445e-4b38-87c0-d9f32d72eeee
async def test_ProcessOrchestrator():
    orch = ProcessOrchestrator()

    # ID: fae00ab6-afb4-4464-a19a-d745435a0365
    def make_component(cid: str, result: MagicMock) -> MagicMock:
        comp = MagicMock()
        comp.component_id = cid
        comp.execute = AsyncMock(return_value=result)
        return comp

    result_ok = MagicMock()
    result_ok.ok = True
    result_ok.confidence = 0.9
    result_ok.duration_sec = 1.5
    result_ok.phase = MagicMock()
    result_ok.phase.value = "analysis"
    result_ok.data = {"symbols": ["a", "b"]}
    result_ok.metadata = {"phase_key": "analysis"}
    result_ok.next_suggested = None

    comp1 = make_component("fileanalyzer", result_ok)

    result2 = MagicMock()
    result2.ok = True
    result2.confidence = 0.8
    result2.duration_sec = 0.5
    result2.phase = result_ok.phase
    result2.data = {"tests": ["t1"]}
    result2.metadata = {"phase_key2": "test"}
    result2.next_suggested = None

    comp2 = make_component("teststrategist", result2)

    results = await orch.run_sequence(
        [
            (comp1, {"file_path": "src/models.py"}),
            (comp2, {}),
        ]
    )

    assert results == [result_ok, result2]
    assert len(orch.execution_history) == 2
    comp1.execute.assert_awaited_once()
    comp2.execute.assert_awaited_once()
    # second component should receive accumulated data from first
    _, kwargs2 = comp2.execute.await_args
    assert kwargs2["symbols"] == ["a", "b"]
    assert kwargs2["session_state"] is orch.session_state

    summary = orch.get_workflow_summary()
    assert summary["total_steps"] == 2
    assert summary["successful_steps"] == 2
    assert summary["failed_steps"] == 0
    assert summary["avg_confidence"] == pytest.approx(0.85)

    await orch.run_adaptive(
        initial_component=comp1,
        initial_inputs={"file_path": "src/models.py"},
        max_steps=3,
        confidence_threshold=0.5,
    )
    assert len(orch.execution_history) == 3

    orch.reset()
    assert orch.session_state == {}
    assert orch.execution_history == []
    assert orch.get_workflow_summary()["total_steps"] == 0
