from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.autonomy.violation_remediator_proposal import (
    get_active_proposal_id_by_action_file,
)


@pytest.mark.asyncio
# ID: 6edae55a-a5c9-4091-a740-e39d74558500
async def test_get_active_proposal_id_by_action_file():
    earlier = datetime(2024, 1, 1, 0, 0, 0)
    later = datetime(2024, 1, 2, 0, 0, 0)

    action_a = SimpleNamespace(ref_id="act-1", parameters={"file_path": "a.py"})
    action_b = SimpleNamespace(ref_id="act-2", parameters=None)
    proposal_one = SimpleNamespace(
        proposal_id="prop-1",
        created_at=earlier,
        actions=[action_a, action_b],
    )

    action_c = SimpleNamespace(ref_id="act-1", parameters={"file_path": "a.py"})
    action_d = SimpleNamespace(ref_id="flow-9", parameters={"file_path": "d.py"})
    proposal_two = SimpleNamespace(
        proposal_id="prop-2",
        created_at=later,
        actions=[action_c, action_d],
    )

    repo = MagicMock()
    repo.list_by_status = AsyncMock(return_value=[proposal_one, proposal_two])

    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    registry = MagicMock()
    registry.session = MagicMock(return_value=session_cm)

    original_registry_mod = None
    import body.services.service_registry as registry_mod

    original_registry_mod = registry_mod.service_registry
    registry_mod.service_registry = registry

    import will.autonomy.proposal_repository as repo_mod

    original_repo_cls = repo_mod.ProposalRepository
    repo_mod.ProposalRepository = MagicMock(return_value=repo)

    try:
        result = await get_active_proposal_id_by_action_file()
    finally:
        registry_mod.service_registry = original_registry_mod
        repo_mod.ProposalRepository = original_repo_cls

    assert result[("act-1", "a.py")] == "prop-1"
    assert result[("act-2", None)] == "prop-1"
    assert result[("flow-9", "d.py")] == "prop-2"
    assert len(result) == 3


import uuid
from unittest.mock import patch

import pytest

from will.autonomy.violation_remediator_proposal import create_proposal


@pytest.mark.asyncio
# ID: 9184a782-0415-4fbf-ab4b-24170f6b2780
async def test_create_proposal():
    claimed_by = uuid.uuid4()
    findings = [
        {
            "id": "finding-1",
            "payload": {
                "file_path": "src/foo.py",
                "check_id": "some_rule",
            },
        },
        {
            "entry_id": "finding-2",
            "payload": {
                "file_path": "src/bar.py",
                "rule": "other_rule",
            },
        },
    ]

    mock_proposal = MagicMock()
    mock_proposal.approval_required = True
    mock_proposal.risk = MagicMock(overall_risk="low")
    mock_proposal.validate.return_value = (True, [])
    mock_proposal.compute_risk = MagicMock()

    mock_proposal_cls = MagicMock(return_value=mock_proposal)
    mock_proposal_scope = MagicMock()
    mock_proposal_action = MagicMock()
    mock_proposal_provenance = MagicMock()

    mock_mapper = MagicMock()
    mock_mapper.to_db_model.return_value = MagicMock(name="proposal_model")

    submission_result = MagicMock(name="submission_result")
    mock_submit = AsyncMock(return_value=submission_result)

    with (
        patch(
            "body.services.proposal_submission_service.submit_mapped_proposal",
            mock_submit,
        ),
        patch(
            "body.services.proposal_submission_service.ProposalSubmissionError",
            Exception,
        ),
        patch(
            "shared.infrastructure.database.models.autonomous_proposals.AutonomousProposal",
            MagicMock(),
        ),
        patch(
            "will.autonomy.proposal_mapper.ProposalMapper",
            mock_mapper,
        ),
        patch(
            "will.autonomy.proposal_state_manager.ProposalStateManager",
            MagicMock(),
        ),
        patch(
            "will.autonomy.violation_remediator_proposal.Proposal",
            mock_proposal_cls,
        ),
        patch(
            "will.autonomy.violation_remediator_proposal.ProposalScope",
            mock_proposal_scope,
        ),
        patch(
            "will.autonomy.violation_remediator_proposal.ProposalAction",
            mock_proposal_action,
        ),
        patch(
            "will.autonomy.violation_remediator_proposal.ProposalProvenance",
            mock_proposal_provenance,
        ),
    ):
        result = await create_proposal(
            ref_id="rule_xyz",
            ref_kind="action",
            findings=findings,
            claimed_by=claimed_by,
        )

    assert result is submission_result
    mock_proposal.validate.assert_called_once()
    mock_submit.assert_awaited_once()
    call_kwargs = mock_submit.await_args.kwargs
    assert call_kwargs["finding_ids"] == ["finding-1", "finding-2"]
    assert call_kwargs["expected_worker_uuid"] == claimed_by
    assert call_kwargs["approval_step"] is None


import asyncio

from will.autonomy.violation_remediator_proposal import check_circuit_breaker


# ID: 22927261-c591-45ab-b73b-3f2089d4c594
def test_check_circuit_breaker():
    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    async def _run():
        with (
            patch("body.services.service_registry.service_registry") as mock_registry,
            patch(
                "will.autonomy.violation_remediator_proposal.recent_consecutive_identical_count",
                new=AsyncMock(return_value=(3, "a" * 40, "b" * 40, "c" * 40)),
            ) as mock_count,
        ):
            mock_registry.session.return_value = session_cm

            result = await check_circuit_breaker(
                ref_id="ref-1",
                ref_kind="violation",
                file_path="src/foo.py",
                config=MagicMock(),
            )

            assert result == (3, "a" * 40, "b" * 40, "c" * 40)
            mock_registry.session.assert_called_once()
            mock_count.assert_awaited_once()

    asyncio.run(_run())
