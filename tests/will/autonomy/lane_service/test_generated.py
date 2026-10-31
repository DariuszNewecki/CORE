from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.lane_service import LaneService


# ID: ba82b21c-f606-4269-b6df-71a1a812369d
async def test_LaneService_propose_validated_diff():
    service = LaneService()

    bb_service = MagicMock()
    bb_service.fetch_delegated_finding = AsyncMock(
        return_value={"payload": {"rule": "rule-x"}}
    )

    candidate = MagicMock()
    candidate.production_set = ["a.py", "b.py"]
    candidate.candidate_id = "cand-1"

    proposal = MagicMock()
    proposal_model = MagicMock()

    with (
        patch(
            "will.autonomy.lane_service.service_registry.get_blackboard_service",
            AsyncMock(return_value=bb_service),
        ),
        patch(
            "will.autonomy.lane_service.build_validated_candidate",
            AsyncMock(return_value=candidate),
        ),
        patch(
            "will.autonomy.lane_service.build_assisted_lane_proposal",
            MagicMock(return_value=proposal),
        ),
        patch(
            "will.autonomy.lane_service.ProposalMapper.to_db_model",
            MagicMock(return_value=proposal_model),
        ),
        patch(
            "will.autonomy.lane_service.submit_assisted_lane_proposal",
            AsyncMock(return_value="prop-123"),
        ),
    ):
        proposal_id, production_set = await service.propose_validated_diff(
            finding_id="finding-1",
            patch="diff --git ...",
            validation_run_id="run-42",
        )

    assert proposal_id == "prop-123"
    assert production_set == ["a.py", "b.py"]
    bb_service.fetch_delegated_finding.assert_awaited_once_with("finding-1")


import pytest


@pytest.mark.asyncio
# ID: 3c78ebc0-9f8c-41a6-8222-4f1bf5d72382
async def test_LaneService_claim_delegated_finding():
    # Import symbol via its module path (class method)
    from will.autonomy.lane_service import LaneService

    instance = object.__new__(LaneService)

    mock_bb_service = AsyncMock()
    mock_bb_service.claim_delegated_finding = AsyncMock(return_value=1)

    mock_registry = AsyncMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb_service)

    # Local import inside the method -> patch at defining module
    with patch(
        "body.services.service_registry.service_registry.get_blackboard_service",
        new=mock_registry.get_blackboard_service,
    ):
        result = await LaneService.claim_delegated_finding(
            instance, "finding-abc", "agent-x"
        )

    assert result is True
    mock_bb_service.claim_delegated_finding.assert_awaited_once_with(
        "finding-abc", "agent-x"
    )


# ID: 477b4fe6-76f2-41f2-85f8-bb77169f027d
async def test_list_delegated_findings():
    findings = [
        {"id": "f1", "status": "indeterminate"},
        {"id": "f2", "status": "human"},
    ]

    bb_service = MagicMock()
    bb_service.fetch_delegated_findings = AsyncMock(return_value=findings)

    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)

    service = LaneService()
    with patch("will.autonomy.lane_service.service_registry", registry):
        result = await service.list_delegated_findings(limit=50)

    assert result == findings
    registry.get_blackboard_service.assert_awaited_once_with()
    bb_service.fetch_delegated_findings.assert_awaited_once_with(limit=50)


# ID: c07e5421-cb6c-4cb6-80d8-eb201bf90b0e
def test_LaneService():
    from will.autonomy.lane_service import LaneService

    service = LaneService()

    finding = {"id": "f-1", "payload": {"rule": "rule-1"}}
    findings = [finding]

    mock_bb = AsyncMock()
    mock_bb.fetch_delegated_findings = AsyncMock(return_value=findings)
    mock_bb.fetch_delegated_finding = AsyncMock(return_value=finding)

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb)

    ref = MagicMock()
    ref.content = {"rationale": "because reasons"}

    mock_intent_repo = MagicMock()
    mock_intent_repo.get_rule = MagicMock(return_value=ref)

    with (
        patch("will.autonomy.lane_service.service_registry", mock_registry),
        patch(
            "will.autonomy.lane_service.get_intent_repository",
            return_value=mock_intent_repo,
        ),
        patch(
            "will.autonomy.lane_service.load_remediation_guidance",
            return_value={"hint": "do the thing"},
        ),
    ):
        import asyncio

        result = asyncio.run(service.list_delegated_findings(limit=10))

    assert result == findings
    mock_bb.fetch_delegated_findings.assert_awaited_once_with(limit=10)
    mock_registry.get_blackboard_service.assert_awaited_once()


from will.autonomy.lane_service import LaneProposeError


# ID: be75e045-d7fb-48c9-b2af-5f68a97d125c
def test_LaneProposeError():
    message = "finding is not a live lane item"
    error = LaneProposeError(message)

    assert isinstance(error, Exception)
    assert str(error) == message
    assert error.args == (message,)

    raised = False
    try:
        raise LaneProposeError(message)
    except LaneProposeError as exc:
        raised = True
        assert str(exc) == message
    assert raised


# ID: 0bc8f62c-5c2f-4374-b3a1-c167c8a86bd7
def test_LaneService_get_delegated_finding():
    from will.autonomy.lane_service import LaneService

    service = LaneService()
    expected = {"id": "f-123", "status": "delegated"}

    mock_bb = MagicMock()
    mock_bb.fetch_delegated_finding = AsyncMock(return_value=expected)

    with patch(
        "body.services.service_registry.service_registry.get_blackboard_service",
        AsyncMock(return_value=mock_bb),
    ):
        import asyncio

        result = asyncio.run(service.get_delegated_finding("f-123"))

    assert result == expected




# ID: c8d79014-46b2-46ef-a61f-a891ad9d502f
async def test_LaneService_get_finding_bundle():
    service = LaneService.__new__(LaneService)
    finding = {"id": "f-1", "data": "x"}
    bundled = {"finding": finding, "bundle": {"context": []}}
    service.get_delegated_finding = AsyncMock(return_value=finding)
    service._with_bundle = MagicMock(return_value=bundled)

    result = await LaneService.get_finding_bundle(service, "f-1")

    assert result == bundled
    service.get_delegated_finding.assert_awaited_once_with("f-1")
    service._with_bundle.assert_called_once_with(finding)
