# tests/will/workflows/test_dev_sync_workflow.py

"""Tests for DevSyncWorkflow — PhaseWorkflowResult migration (#805).

Mocks ActionExecutor; asserts phase folding, early-exit semantics, the
`.ok` contract consumers rely on, and write-flag propagation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from shared.models.workflow_models import PhaseWorkflowResult
from will.workflows.dev_sync_workflow import DevSyncWorkflow


@dataclass
class _FakeActionResult:
    action_id: str
    ok: bool = True
    duration_sec: float = 0.5
    data: dict[str, Any] = field(default_factory=dict)


def _make_workflow(results_by_action: dict[str, _FakeActionResult]):
    """Build a DevSyncWorkflow whose executor returns canned results."""
    executor = MagicMock()

    async def _execute(*, action_id: str, write: bool) -> _FakeActionResult:
        return results_by_action[action_id]

    executor.execute = AsyncMock(side_effect=_execute)
    with patch("will.workflows.dev_sync_workflow.ActionExecutor", return_value=executor):
        workflow = DevSyncWorkflow(MagicMock())
    return workflow, executor


_ALL_OK = {
    "fix.headers": _FakeActionResult("fix.headers"),
    "fix.ids": _FakeActionResult("fix.ids"),
    "fix.format": _FakeActionResult("fix.format"),
    "sync.db": _FakeActionResult("sync.db"),
    "sync.vectors_code": _FakeActionResult("sync.vectors_code"),
}


async def test_happy_path_returns_ok_phase_workflow_result():
    workflow, _ = _make_workflow(dict(_ALL_OK))

    result = await workflow.run(write=False)

    assert isinstance(result, PhaseWorkflowResult)
    assert result.ok is True
    assert result.workflow_type == "dev_sync"
    assert [p.name for p in result.phase_results] == ["fix", "sync"]
    assert result.total_duration == 5 * 0.5
    fix_actions = result.phase_results[0].data["actions"]
    assert set(fix_actions) == {"fix.headers", "fix.ids", "fix.format"}


async def test_fix_phase_failure_skips_sync_phase():
    results = dict(_ALL_OK)
    results["fix.ids"] = _FakeActionResult(
        "fix.ids", ok=False, data={"error": "boom"}
    )
    workflow, executor = _make_workflow(results)

    result = await workflow.run(write=False)

    assert result.ok is False
    assert [p.name for p in result.phase_results] == ["fix"]
    assert "fix.ids: boom" in result.phase_results[0].error
    executed = {c.kwargs["action_id"] for c in executor.execute.await_args_list}
    assert "sync.db" not in executed


async def test_sync_db_failure_skips_vectorization():
    results = dict(_ALL_OK)
    results["sync.db"] = _FakeActionResult("sync.db", ok=False)
    workflow, executor = _make_workflow(results)

    result = await workflow.run(write=False)

    assert result.ok is False
    sync_phase = result.phase_results[1]
    assert sync_phase.ok is False
    assert "sync.db" in sync_phase.error
    executed = {c.kwargs["action_id"] for c in executor.execute.await_args_list}
    assert "sync.vectors_code" not in executed


async def test_write_flag_propagates_to_every_action():
    workflow, executor = _make_workflow(dict(_ALL_OK))

    await workflow.run(write=True)

    assert executor.execute.await_count == 5
    assert all(c.kwargs["write"] is True for c in executor.execute.await_args_list)
