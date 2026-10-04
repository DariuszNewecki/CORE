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
