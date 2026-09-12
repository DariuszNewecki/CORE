# tests/will/autonomy/test_develop_from_goal_worker_shim.py
"""develop_from_goal preserves its (bool, str) return contract now that it
is a thin shim over GoalExecutionWorker (#872, ADR-159 D4).

No real Worker lifecycle here — GoalExecutionWorker itself is mocked at its
import site; its own lifecycle/evidence behavior is covered by
tests/will/workers/test_goal_execution_worker.py. This file only proves the
shim's contract: same construction, same (bool, str) shape, exceptions from
start() still translate to (False, "Execution error: ...").
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from will.autonomy.autonomous_developer import develop_from_goal


def _fake_worker(result: PhaseWorkflowResult, run_id: str = "rid-1") -> MagicMock:
    worker = MagicMock()
    worker.start = AsyncMock()
    worker.result = result
    worker.run_id = run_id
    return worker


async def test_success_return_contract_includes_run_id() -> None:
    result = PhaseWorkflowResult(ok=True, phase_results=[PhaseResult(name="execution", ok=True)])
    worker = _fake_worker(result)

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ) as worker_cls:
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
            write=True,
            task_id="task-1",
        )

    assert ok is True
    assert "completed successfully" in message
    assert "run_id=rid-1" in message
    worker_cls.assert_called_once()
    _, kwargs = worker_cls.call_args
    assert kwargs["goal"] == "Improve modularity of demo.py"
    assert kwargs["workflow_type"] == "refactor_modularity"
    assert kwargs["write"] is True
    assert kwargs["task_id"] == "task-1"


async def test_failure_return_contract_names_failed_phase() -> None:
    result = PhaseWorkflowResult(
        ok=False,
        phase_results=[
            PhaseResult(name="interpret", ok=True),
            PhaseResult(name="audit", ok=False, error="canary failed"),
        ],
    )
    worker = _fake_worker(result, run_id="rid-2")

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ):
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
        )

    assert ok is False
    assert "audit" in message
    assert "run_id=rid-2" in message


async def test_worker_start_exception_returns_false_with_error_message() -> None:
    worker = MagicMock()
    worker.start = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "will.autonomy.autonomous_developer.GoalExecutionWorker",
        return_value=worker,
    ):
        ok, message = await develop_from_goal(
            context=MagicMock(),
            goal="Improve modularity of demo.py",
            workflow_type="refactor_modularity",
        )

    assert ok is False
    assert message == "Execution error: boom"
