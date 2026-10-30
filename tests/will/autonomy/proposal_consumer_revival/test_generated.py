from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal_consumer_revival import release_executing_proposals


# ID: d94aad05-0425-4823-a47a-e470cf23aa29
async def test_release_executing_proposals() -> None:
    worker = MagicMock()
    worker_uuid = uuid.uuid4()

    row1 = (uuid.uuid4(),)
    row2 = (uuid.uuid4(),)

    result = MagicMock()
    result.fetchall = MagicMock(return_value=[row1, row2])

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    service_registry = MagicMock()
    service_registry.session = MagicMock(return_value=session_cm)

    mark_failed = AsyncMock()
    revive = AsyncMock()

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "will.autonomy.proposal_consumer_revival.mark_proposal_failed", mark_failed
        ),
        patch("will.autonomy.proposal_consumer_revival.revive_and_report", revive),
    ):
        released = await release_executing_proposals(worker, worker_uuid)

    assert released == 2
    session.execute.assert_awaited_once()
    assert mark_failed.await_count == 2
    assert revive.await_count == 2
    mark_failed.assert_any_await(
        str(row1[0]), "worker terminated during execution (finally-block release)"
    )
    revive.assert_any_await(
        worker,
        str(row2[0]),
        "worker terminated during execution (finally-block release)",
    )


import pytest

from will.autonomy.proposal_consumer_revival import mark_proposal_failed


@pytest.mark.asyncio
# ID: 66cdb831-33a5-44d0-964a-2f3f0014934b
async def test_mark_proposal_failed():
    mock_session = MagicMock()

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)

    mock_registry = MagicMock()
    mock_registry.session.return_value = mock_session_cm

    mock_state_manager = MagicMock()
    mock_state_manager.mark_failed = AsyncMock(return_value=None)

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "will.autonomy.proposal_state_manager.ProposalStateManager",
            return_value=mock_state_manager,
        ),
    ):
        await mark_proposal_failed("prop-123", "boom")

    mock_state_manager.mark_failed.assert_awaited_once_with("prop-123", "boom")


import pytest

from will.autonomy.proposal_consumer_revival import report_revival


@pytest.mark.asyncio
# ID: c3ac8e56-a7dd-4f0c-aeee-e0d042ee7d13
async def test_report_revival():
    worker = MagicMock()
    worker.post_observation = AsyncMock()
    worker.post_report = AsyncMock()

    revival = {
        "proposal_id": "prop-123",
        "failure_reason": "some_failure",
        "revived_count": 2,
        "revived_subjects": ["subj-a", "subj-b"],
        "delegated_count": 1,
        "delegated_finding_ids": ["fid-1"],
        "delegated_subjects": ["subj-delegated"],
        "cap_reason": "failure_cap_delegated",
    }

    operational_config = MagicMock()
    operational_config.blackboard.remediation_cap_n = 3

    with patch(
        "shared.infrastructure.intent.operational_config.load_operational_config",
        return_value=operational_config,
    ):
        await report_revival(
            worker,
            "prop-123",
            revival,
            report_subject_family="proposal.failure.revival",
        )

    worker.post_observation.assert_awaited_once_with(
        subject="blackboard.remediation_cap_reached::subj-delegated",
        payload={
            "entry_id": "fid-1",
            "finding_subject": "subj-delegated",
            "finding_status": "indeterminate",
            "proposal_id": "prop-123",
            "failure_reason": "some_failure",
            "reason": "failure_cap_delegated",
            "remediation_cap_n": 3,
        },
        status="abandoned",
    )

    worker.post_report.assert_awaited_once_with(
        subject="proposal.failure.revival::prop-123",
        payload={
            "proposal_id": "prop-123",
            "failure_reason": "some_failure",
            "revived_count": 2,
            "revived_subjects": ["subj-a", "subj-b"],
            "delegated_count": 1,
            "delegated_subjects": ["subj-delegated"],
        },
    )


import pytest

from will.autonomy.proposal_consumer_revival import revive_and_report


@pytest.mark.asyncio
# ID: 2f46d9f2-93d6-4e49-91f2-bc7b7d3ad5ce
async def test_revive_and_report():
    worker = MagicMock()

    revival = {"finding-1": {"subject": "finding-1"}}

    with (
        patch(
            "will.autonomy.proposal_consumer_revival._proposal_revival_lineage",
            new=AsyncMock(return_value="autonomous"),
        ) as mock_lineage,
        patch(
            "will.autonomy.proposal_consumer_revival._revive_autonomous",
            new=AsyncMock(return_value=revival),
        ) as mock_revive,
        patch(
            "will.autonomy.proposal_consumer_revival.report_revival",
            new=AsyncMock(),
        ) as mock_report,
    ):
        await revive_and_report(worker, "proposal-1", "failed")

    mock_lineage.assert_awaited_once_with("proposal-1")
    mock_revive.assert_awaited_once_with("proposal-1", "failed")
    mock_report.assert_awaited_once_with(worker, "proposal-1", revival)
