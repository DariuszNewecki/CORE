from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: c2e7bbe3-4beb-428c-8885-774817193383
async def test_run_and_record_probes():
    from will.orchestration.goal_run_probes import run_and_record_probes

    worker = MagicMock()
    worker._context = MagicMock()
    worker.goal = "some-goal"
    worker.workflow_type = "goal_run"
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.probe_records = None

    records = [
        {"probe": "alpha", "passed": True},
        {"probe": "beta", "passed": True},
    ]

    with (
        patch(
            "will.orchestration.goal_run_probes.run_apparatus_probes",
            new=AsyncMock(return_value=records),
        ) as mock_run_probes,
        patch(
            "will.orchestration.goal_run_probes.blackboard_safe",
            side_effect=lambda r: r,
        ),
    ):
        result = await run_and_record_probes(worker, "run-123")

    assert result is True
    mock_run_probes.assert_awaited_once_with(worker._context, "run-123")
    assert worker.probe_records == records
    assert worker.post_report.await_count == 2
    worker.post_observation.assert_not_awaited()


import pytest

from will.orchestration.goal_run_probes import run_apparatus_probes


@pytest.mark.asyncio
# ID: 44d0b910-167f-44f9-bcbd-80e83aa59e69
async def test_run_apparatus_probes():
    context = object()
    run_id = "run-123"

    record_i5 = {"probe": "I-5", "run_id": run_id, "passed": True}
    record_i6 = {"probe": "I-6", "run_id": run_id, "passed": True}

    mock_i5 = AsyncMock(return_value=record_i5)
    mock_i6 = AsyncMock(return_value=record_i6)

    with (
        patch("will.orchestration.goal_run_probes.run_probe_i5", mock_i5),
        patch("will.orchestration.goal_run_probes.run_probe_i6", mock_i6),
    ):
        result = await run_apparatus_probes(context, run_id)

    assert result == [record_i5, record_i6]
    mock_i5.assert_awaited_once_with(context, run_id)
    mock_i6.assert_awaited_once_with(context, run_id)


import pytest

from will.orchestration.goal_run_probes import run_probe_i6


@pytest.mark.asyncio
# ID: 36d4f47e-1fc1-41b4-9ca6-32c2a0f7e2cc
async def test_run_probe_i6():
    from will.autonomy.proposal import ProposalStatus
    from will.autonomy.safe_auto_approval_envelope import SafeAutoApprovalDeniedError

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    service_registry = MagicMock()
    service_registry.session = MagicMock(return_value=session_ctx)

    repo = MagicMock()
    repo.create = AsyncMock(return_value="proposal-123")

    # Build the denial error via the real class signature (single message arg).
    denial_exc = SafeAutoApprovalDeniedError("denied by safe auto-approval envelope")

    manager = MagicMock()
    manager.approve = AsyncMock(side_effect=denial_exc)

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository", return_value=repo
        ),
        patch(
            "will.autonomy.proposal_state_manager.ProposalStateManager",
            return_value=manager,
        ),
        patch(
            "will.orchestration.goal_run_probes._proposal_status",
            AsyncMock(return_value=ProposalStatus.PENDING.value),
        ),
        patch(
            "will.orchestration.goal_run_probes.rule_in_bound_law",
            return_value={"loaded": True},
        ),
    ):
        result = await run_probe_i6(context=MagicMock(), run_id="run-abc")

    assert result["proposal_id"] == "proposal-123"
    assert result["result"]["approved"] is False
    assert result["result"]["denial"] is not None
    assert result["result"]["proposal_status_after"] == ProposalStatus.PENDING.value
