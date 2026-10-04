from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.workers.proposal_consumer_worker import ProposalConsumerWorker


# ID: 5e757a19-1cd3-48c2-bc73-4378f99da6e4
async def test_ProposalConsumerWorker_run() -> None:
    worker = ProposalConsumerWorker(core_context=MagicMock())

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker._load_approved_proposals = AsyncMock(return_value=[])

    await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker._load_approved_proposals.assert_awaited_once()
    worker.post_report.assert_awaited_once()

    call_kwargs = worker.post_report.await_args.kwargs
    assert call_kwargs["subject"] == "proposal_consumer_worker.run.complete"
    assert call_kwargs["payload"] == {
        "executed": 0,
        "message": "No approved proposals.",
    }


from unittest.mock import patch


# ID: ff6335f3-cf5a-42df-abc4-403962a0cc8a
def test_ProposalConsumerWorker() -> None:
    import asyncio

    core_context = MagicMock()
    worker = ProposalConsumerWorker(core_context)

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    proposals = [
        {"proposal_id": "p1", "goal": "do something"},
    ]

    worker._load_approved_proposals = AsyncMock(return_value=proposals)

    result = {
        "ok": True,
        "lifecycle_status": "completed",
        "actions_executed": 1,
        "actions_succeeded": 1,
        "actions_failed": 0,
        "duration_sec": 0.5,
        "commit_outcome": "committed",
        "action_results": [],
    }

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=result)

    with (
        patch(
            "will.autonomy.proposal_executor.ProposalExecutor",
            return_value=mock_executor,
        ),
        patch(
            "will.workers.proposal_consumer_worker.apply_success_effects",
            new=AsyncMock(),
        ),
        patch(
            "will.workers.proposal_consumer_worker.report_revival",
            new=AsyncMock(),
        ),
        patch(
            "will.workers.proposal_consumer_worker.revive_and_report",
            new=AsyncMock(),
        ),
        patch(
            "will.workers.proposal_consumer_worker.mark_proposal_failed",
            new=AsyncMock(),
        ),
        patch(
            "will.workers.proposal_consumer_worker.release_executing_proposals",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "will.workers.proposal_consumer_worker.summarize_flow_step_failures",
            return_value=[],
        ),
    ):
        asyncio.run(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    mock_executor.execute.assert_awaited_once_with("p1", worker.worker_uuid, write=True)
    worker.post_report.assert_awaited()
    call_kwargs = worker.post_report.await_args.kwargs
    assert call_kwargs["payload"]["succeeded"] == 1
    assert call_kwargs["payload"]["failed"] == 0
