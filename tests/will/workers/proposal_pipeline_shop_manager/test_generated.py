from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: e6e002d8-c5a0-443d-8882-a810115a6d60
async def test_ProposalPipelineShopManager_run() -> None:
    from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager

    manager = ProposalPipelineShopManager()

    manager.post_heartbeat = AsyncMock()
    manager.post_finding = AsyncMock()
    manager.post_report = AsyncMock()
    manager._fetch_existing_findings = AsyncMock(return_value={})
    manager._retire_stuck_proposal = AsyncMock(return_value=False)
    manager._roll_forward_finalizing = AsyncMock(return_value=False)
    manager._redrive_undeferred_findings = AsyncMock(return_value=False)
    manager._reconcile_stuck_deferred_terminal = AsyncMock(return_value=False)

    proposal_svc = MagicMock()
    proposal_svc.fetch_stuck_approved = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_executing = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_finalizing = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_undeferred = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_deferred_terminal = AsyncMock(return_value=[])
    proposal_svc.fetch_repeated_failures = AsyncMock(return_value=[])

    blackboard_svc = MagicMock()
    blackboard_svc.resolve_entries = AsyncMock()
    blackboard_svc.increment_finding_counter = AsyncMock(return_value=0)
    blackboard_svc.escalate_finding_to_governor = AsyncMock(return_value=False)

    registry = MagicMock()
    registry.get_proposal_supervision_service = AsyncMock(return_value=proposal_svc)
    registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with patch("body.services.service_registry.service_registry", registry):
        await manager.run()

    manager.post_heartbeat.assert_awaited_once()
    manager.post_report.assert_awaited_once()
    proposal_svc.fetch_stuck_approved.assert_awaited_once()
    proposal_svc.fetch_stuck_executing.assert_awaited_once()
    proposal_svc.fetch_stuck_finalizing.assert_awaited_once()
    proposal_svc.fetch_stuck_undeferred.assert_awaited_once()
    proposal_svc.fetch_stuck_deferred_terminal.assert_awaited_once()
    proposal_svc.fetch_repeated_failures.assert_awaited_once()
    manager.post_finding.assert_not_awaited()

    report_kwargs = manager.post_report.call_args.kwargs
    assert report_kwargs["subject"] == "proposal_pipeline_shop_manager.run.complete"
    assert report_kwargs["payload"]["flagged"] == 0
    assert report_kwargs["payload"]["resolved"] == 0


from datetime import UTC, datetime

from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager


# ID: 13126e67-46bd-45d3-b647-9ae05389f22b
async def test_ProposalPipelineShopManager() -> None:
    worker = ProposalPipelineShopManager()

    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()
    worker._retire_stuck_proposal = AsyncMock(return_value=False)
    worker._roll_forward_finalizing = AsyncMock(return_value=False)
    worker._reconcile_stuck_deferred_terminal = AsyncMock(return_value=False)
    worker._redrive_undeferred_findings = AsyncMock(return_value=False)

    now = datetime(2024, 1, 1, tzinfo=UTC)

    proposal_svc = MagicMock()
    proposal_svc.fetch_stuck_approved = AsyncMock(
        return_value=[
            {
                "proposal_id": "p-1",
                "approved_at": now,
                "seconds_stuck": 600,
            }
        ]
    )
    proposal_svc.fetch_stuck_executing = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_finalizing = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_undeferred = AsyncMock(return_value=[])
    proposal_svc.fetch_stuck_deferred_terminal = AsyncMock(return_value=[])
    proposal_svc.fetch_repeated_failures = AsyncMock(return_value=[])

    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(return_value=[])
    blackboard_svc.resolve_entries = AsyncMock()
    blackboard_svc.increment_finding_counter = AsyncMock(return_value=0)
    blackboard_svc.escalate_finding_to_governor = AsyncMock(return_value=False)

    registry = MagicMock()
    registry.get_proposal_supervision_service = AsyncMock(return_value=proposal_svc)
    registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with patch("body.services.service_registry.service_registry", registry):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker.post_finding.assert_awaited_once()
    worker.post_report.assert_awaited_once()

    finding_call = worker.post_finding.await_args
    assert finding_call.kwargs["subject"] == "proposal.stuck_approved::p-1"
    assert finding_call.kwargs["payload"]["proposal_id"] == "p-1"

    report_call = worker.post_report.await_args
    assert report_call.kwargs["payload"]["stuck_approved"] == 1
    assert report_call.kwargs["payload"]["flagged"] == 1
    assert report_call.kwargs["payload"]["resolved"] == 0
