# src/will/autonomy/lane_service.py

"""
Assisted Remediation Lane service (ADR-109 D1/D5, issue #652).

Will-layer facade for the external-agent contract. The lane lets a delegated
finding (`indeterminate` + `human`) be worked by an external agent + governor
through human-gated multi-file proposals, instead of rotting in the inbox.

This service is the API↔Body seam for the lane: the API routes through it
(API → Will), and it delegates the actual blackboard reads/writes to Body via
the service_registry — the pattern `must_delegate_to_body` endorses and that
ProposalService already uses. Keeping lane logic here (rather than in API
handlers) is also what the gate-location decision (#652) requires: the API
surface stays thin, orchestration lives in Will.

Covers the read side (`list_delegated_findings` / `get_delegated_finding`) and
the propose orchestration (`propose_validated_diff`). The `claim` and
reject-revival seams land here in subsequent increments.
"""

from __future__ import annotations

from typing import Any

from body.services.service_registry import service_registry
from shared.logger import getLogger
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)
from will.autonomy.proposal_service import ProposalService


logger = getLogger(__name__)

# The action-level check the assisted-lane proposal declares. The approval
# gate (proposal_state_manager.approve, ADR-109 #654) refuses approval until
# this check is recorded passing in validation_results.
_VALIDATION_CHECK = "assisted.validate_diff"


# ID: de400506-977d-4a2f-9703-d44ee8a62a71
class LaneProposeError(Exception):
    """Raised when a delegated finding cannot be turned into a proposal.

    Signals a precondition failure the caller should surface verbatim (finding
    is not a live lane item, or the validation verdict does not authorize a
    proposal) rather than a server fault.
    """


# ID: 2b0af18e-484a-449f-af56-5cace4e6efee
class LaneService:
    """Facade over the assisted-lane work queue and proposal lifecycle.

    Stateless: each call acquires the BlackboardService from the registry,
    which owns its own session. Mirrors ProposalService's delegation shape.
    """

    # ID: 2a9692eb-9b24-448b-a1de-4cd586846289
    async def list_delegated_findings(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the delegated findings awaiting assisted remediation.

        Delegates to the canonical governor-inbox predicate
        (`indeterminate` + `human`) on the BlackboardService query layer, so
        the lane queue cannot drift from the dashboard inbox panel.
        """
        bb_service = await service_registry.get_blackboard_service()
        return await bb_service.fetch_delegated_findings(limit=limit)

    # ID: d6633aba-9040-466e-9879-58cd16d775d2
    async def get_delegated_finding(self, finding_id: str) -> dict[str, Any] | None:
        """Return a single delegated finding by id, or None if not a live lane item.

        Same governor-inbox predicate as the list surface; a finding already
        worked (deferred/resolved) or never delegated returns None.
        """
        bb_service = await service_registry.get_blackboard_service()
        return await bb_service.fetch_delegated_finding(finding_id)

    # ID: 504fdfe1-cc1a-4da9-beee-c1161d480c84
    async def next_delegated_finding(self) -> dict[str, Any] | None:
        """Return the oldest delegated finding (the FIFO head), or None if empty.

        The lane's "pull the next piece of work" surface. The rich context
        bundle (related files, guidance, rule text) is the deferred #653
        exporter; for now this returns the raw finding the same shape as the
        list.
        """
        findings = await self.list_delegated_findings(limit=1)
        return findings[0] if findings else None

    # ID: 04b486b9-7d1a-432f-8fc5-a434ec1b8e58
    async def claim_delegated_finding(self, finding_id: str, agent: str) -> bool:
        """Mark a delegated finding as being worked by *agent* (ADR-109 §2).

        Returns True if the finding was a live lane item and is now stamped
        claimed; False if it is not a live delegated finding.
        """
        bb_service = await service_registry.get_blackboard_service()
        updated = await bb_service.claim_delegated_finding(finding_id, agent)
        return updated > 0

    # ID: 16bde5bd-d258-419a-9a55-f621de9e1020
    async def propose_validated_diff(
        self,
        finding_id: str,
        patch: str,
        production_set: list[str],
    ) -> str:
        """Turn a validated agent diff into a human-gated proposal (ADR-109 D3/D4).

        Orchestration only — validation already ran (CLI-triggered
        ``assisted.validate_diff``) and the route verified its persisted verdict
        before calling this; ``production_set`` is the touched-file set the gate
        reported (ADR-101 D2 commit set). This method:

        1. confirms the finding is still a live delegated lane item (and reads
           its rule for the proposal's goal + constitutional constraints);
        2. creates a DRAFT proposal that, on approval, runs ``assisted.apply_diff``
           with the patch — ``approval_required=True`` is mandatory for the
           multi-file assisted lane (ADR-109 D3, the human gate licenses the
           ADR-035 multi-file exception), and ``validation_checks`` engages the
           approval gate (#654) which is satisfied by the recorded
           ``validation_results``;
        3. defers the finding to the proposal (``indeterminate+human`` →
           ``deferred_to_proposal``), moving it out of the inbox into tracked.

        Returns the new proposal id.

        Raises:
            LaneProposeError: the finding is not a live delegated lane item.
        """
        bb_service = await service_registry.get_blackboard_service()
        finding = await bb_service.fetch_delegated_finding(finding_id)
        if finding is None:
            raise LaneProposeError(
                f"Finding {finding_id!r} is not a live delegated lane item "
                "(already worked, resolved, or never delegated)."
            )

        payload = finding.get("payload") or {}
        rule = payload.get("rule") or payload.get("rule_id") or "unknown"

        proposal = Proposal(
            goal=(
                f"Assisted remediation of {rule} "
                f"({len(production_set)} file(s)) via agent-authored diff"
            ),
            actions=[
                ProposalAction(
                    action_id="assisted.apply_diff",
                    parameters={"patch": patch, "write": True},
                    order=0,
                )
            ],
            scope=ProposalScope(files=list(production_set)),
            status=ProposalStatus.DRAFT,
            created_by="assisted-lane",
            # The validation gate (#654): declared check + recorded pass. The
            # route confirmed the persisted verdict before this call, so the
            # recorded result reflects a real assisted.validate_diff run.
            validation_checks=[_VALIDATION_CHECK],
            validation_results={_VALIDATION_CHECK: True},
            # ADR-109 D3 — the human gate is the precondition that licenses the
            # multi-file exception; mandatory regardless of computed risk.
            approval_required=True,
            constitutional_constraints={
                "finding_ids": [finding_id],
                "rules": [rule],
                # Marks the proposal as assisted-lane so reject revives the
                # finding to indeterminate+human (ADR-109 D4), not the
                # autonomous awaiting_reaudit path.
                "assisted_lane": True,
            },
        )

        async with ProposalService.open() as proposals:
            proposal_id = await proposals.create(proposal)

        deferred = await bb_service.defer_delegated_finding_to_proposal(
            finding_id, proposal_id
        )
        logger.info(
            "Assisted lane: finding %s -> proposal %s (deferred=%d, files=%d)",
            finding_id,
            proposal_id,
            deferred,
            len(production_set),
        )
        return proposal_id
