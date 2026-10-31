from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock


# ID: a8a91081-ae8a-4984-9d99-ed2f5bb2e4f1
def test_DevSyncWorkflow():
    from will.workflows.dev_sync_workflow import DevSyncWorkflow

    context = MagicMock()
    workflow = DevSyncWorkflow(context)

    def _make_action(action_id: str) -> MagicMock:
        action = MagicMock()
        action.action_id = action_id
        action.ok = True
        action.data = {}
        action.duration_sec = 0.1
        return action

    async def _fake_execute(*, action_id: str, write: bool) -> MagicMock:
        return _make_action(action_id)

    workflow.executor = MagicMock()
    workflow.executor.execute = AsyncMock(side_effect=_fake_execute)

    result = asyncio.run(workflow.run(write=False))

    assert result.ok is True
    assert result.workflow_type == "dev_sync"
    assert [p.name for p in result.phase_results] == ["fix", "sync"]
    assert all(p.ok for p in result.phase_results)

    executed_ids = [
        c.kwargs["action_id"] for c in workflow.executor.execute.await_args_list
    ]
    assert executed_ids == [
        "fix.headers",
        "fix.ids",
        "fix.format",
        "sync.db",
        "sync.vectors_code",
    ]
    assert all(
        c.kwargs["write"] is False for c in workflow.executor.execute.await_args_list
    )



from will.workflows.dev_sync_workflow import DevSyncWorkflow


# ID: e48f62e5-069c-4b5e-b125-7daef00edd91
def test_DevSyncWorkflow_run():
    context = MagicMock()
    workflow = DevSyncWorkflow(context)

    fix_phase = MagicMock()
    fix_phase.ok = True
    sync_phase = MagicMock()
    sync_phase.ok = True

    workflow._run_fix_phase = AsyncMock(return_value=fix_phase)
    workflow._run_sync_phase = AsyncMock(return_value=sync_phase)

    final_result = MagicMock()
    final_result.ok = True
    workflow._build_result = MagicMock(return_value=final_result)

    import asyncio

    result = asyncio.run(workflow.run(write=True))

    workflow._run_fix_phase.assert_awaited_once_with(write=True)
    workflow._run_sync_phase.assert_awaited_once_with(write=True)
    workflow._build_result.assert_called_once_with([fix_phase, sync_phase])
    assert result is final_result
