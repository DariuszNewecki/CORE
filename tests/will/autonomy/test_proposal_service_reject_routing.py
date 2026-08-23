# tests/will/autonomy/test_proposal_service_reject_routing.py

"""ProposalService.reject routes revival by proposal lineage (ADR-109 D4,
ADR-154 D3).

An assisted-lane proposal carries ``constitutional_constraints['assisted_lane']``
and its deferred finding is ``resolution_mechanism='human'`` — which the generic
``revive_findings_for_failed_proposal`` predicate (``='reaudit'``) would never
match, stranding the finding. A ceremony proposal carries
``constitutional_constraints['proposal_origin'] == 'ceremony'`` and its deferred
finding is ``resolution_mechanism='reaudit'`` — the OPPOSITE mismatch: the
assisted-lane helper's predicate (``='human'``) would never match it either.
reject() must therefore route each lineage to its own revival operation, all
three landing a rejected proposal's findings at indeterminate+human (the
ceremony and assisted-lane destinations are the same STATE, reached via
different Body operations because their source resolution_mechanism differs)
except the plain autonomous lineage, which goes to the generic
awaiting_reaudit path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.proposal import Proposal
from will.autonomy.proposal_service import ProposalService


def _service_with(proposal: Proposal | None) -> tuple[ProposalService, AsyncMock]:
    svc = ProposalService(session=MagicMock())
    svc._state_manager = AsyncMock()
    svc._repository = AsyncMock()
    svc._repository.get = AsyncMock(return_value=proposal)

    bb = AsyncMock()
    bb.revive_delegated_findings_for_rejected_proposal = AsyncMock(
        return_value={"revived_count": 1}
    )
    bb.revive_ceremony_findings_for_rejected_proposal = AsyncMock(
        return_value={"revived_count": 2}
    )
    bb.revive_findings_for_failed_proposal = AsyncMock(
        return_value={"revived_count": 3}
    )
    return svc, bb


async def test_reject_assisted_lane_routes_to_lane_revival():
    proposal = Proposal(constitutional_constraints={"assisted_lane": True})
    svc, bb = _service_with(proposal)

    with patch(
        "will.autonomy.proposal_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb),
    ):
        out = await svc.reject("p-1", "needs a different approach")

    assert out == 1
    svc._state_manager.reject.assert_awaited_once_with(
        "p-1", "needs a different approach"
    )
    bb.revive_delegated_findings_for_rejected_proposal.assert_awaited_once_with(
        proposal_id="p-1", reason="needs a different approach"
    )
    bb.revive_findings_for_failed_proposal.assert_not_called()


async def test_reject_ceremony_routes_to_ceremony_revival_not_assisted_or_generic():
    """ADR-154 D3, the trap the governor specifically flagged: rejecting a
    ceremony proposal must land at indeterminate+human via the DEDICATED
    ceremony revival operation — not the assisted-lane helper (whose
    predicate requires resolution_mechanism='human', which a ceremony
    finding never has) and not the generic awaiting_reaudit path (which
    would silently re-enter the autonomous loop after an explicit human
    rejection)."""
    proposal = Proposal(constitutional_constraints={"proposal_origin": "ceremony"})
    svc, bb = _service_with(proposal)

    with patch(
        "will.autonomy.proposal_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb),
    ):
        out = await svc.reject("p-ceremony-1", "candidate not architecturally sound")

    assert out == 2
    bb.revive_ceremony_findings_for_rejected_proposal.assert_awaited_once_with(
        proposal_id="p-ceremony-1", reason="candidate not architecturally sound"
    )
    bb.revive_delegated_findings_for_rejected_proposal.assert_not_called()
    bb.revive_findings_for_failed_proposal.assert_not_called()


async def test_reject_autonomous_routes_to_generic_revival():
    proposal = Proposal(constitutional_constraints={})  # no assisted_lane marker
    svc, bb = _service_with(proposal)

    with patch(
        "will.autonomy.proposal_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb),
    ):
        out = await svc.reject("p-2", "stale")

    assert out == 3
    bb.revive_findings_for_failed_proposal.assert_awaited_once_with(
        proposal_id="p-2", failure_reason="rejected: stale"
    )
    bb.revive_delegated_findings_for_rejected_proposal.assert_not_called()


async def test_reject_missing_proposal_falls_back_to_generic():
    """If the proposal row cannot be loaded, default to the generic path
    rather than assuming assisted-lane lineage."""
    svc, bb = _service_with(None)

    with patch(
        "will.autonomy.proposal_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb),
    ):
        out = await svc.reject("p-3", "gone")

    assert out == 3
    bb.revive_findings_for_failed_proposal.assert_awaited_once()
    bb.revive_delegated_findings_for_rejected_proposal.assert_not_called()
