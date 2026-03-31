# src/will/workers/violation_remediator.py
# ID: workers.violation_remediator
"""
ViolationRemediatorWorker - Closes the autonomous audit loop.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/violation_remediator.yaml):
  Consume open audit violation findings from the Blackboard, look up the
  remediating action from the atomic action registry (via the remediates
  field), create one Proposal per unique action group, and mark each
  consumed Blackboard entry as resolved.

The autonomous audit loop this closes:

  AuditViolationSensor (sensing)
      posts open findings to Blackboard
          ↓
  ViolationRemediatorWorker (acting)  ← THIS WORKER
      reads open findings from Blackboard
      looks up action via action_registry.get_by_check_id(rule)
      creates Proposal (one per action group)
      marks finding resolved
          ↓
  ProposalConsumerWorker
      executes APPROVED proposals via ProposalExecutor
          ↓
  AuditViolationSensor runs again
      confirms violation gone or re-opens

Design constraints:
- No LLM calls
- No direct file writes
- Never creates a proposal if an active one exists for the same action
- Marks Blackboard entries resolved AFTER proposal is persisted (not before)
- One proposal per action ID (not one per finding)
- Safe proposals (approval_required=False) are created in APPROVED status
  so ProposalConsumerWorker can pick them up immediately
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)


logger = getLogger(__name__)

_FINDING_SUBJECT_PREFIX = "audit.violation::"

_ACTIVE_STATUSES: frozenset[ProposalStatus] = frozenset(
    {
        ProposalStatus.DRAFT,
        ProposalStatus.PENDING,
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
    }
)


# ID: b4c5d6e7-f8a9-0123-bcde-f12345678904
class ViolationRemediatorWorker(Worker):
    """
    Acting worker that converts Blackboard violation findings into proposals.

    Reads open audit.violation findings, maps each rule to a registered
    atomic action via action_registry.get_by_check_id(), groups by action,
    deduplicates against active proposals, creates proposals, marks entries
    resolved.

    Safe proposals (approval_required=False) are created in APPROVED status
    so ProposalConsumerWorker can execute them without a separate approval step.
    """

    declaration_name = "violation_remediator"

    def __init__(
        self, core_context: Any = None, declaration_name: str = "", **kwargs: Any
    ) -> None:
        """Accept daemon kwargs — core_context and cognitive_service not used, no LLM calls."""
        super().__init__(declaration_name=declaration_name)

    # ID: c5d6e7f8-a9b0-1234-cdef-123456789014
    async def run(self) -> None:
        """
        Core work unit:
        1. Load open violation findings from Blackboard
        2. Group by action (via registry.get_by_check_id)
        3. Deduplicate against active proposals
        4. Create proposals for new action groups
        5. Mark consumed Blackboard entries resolved
        6. Post blackboard report
        """
        # 1. Load open findings
        open_findings = await self._load_open_findings()

        if not open_findings:
            await self.post_heartbeat()
            logger.info("ViolationRemediatorWorker: no open violation findings")
            return

        logger.info(
            "ViolationRemediatorWorker: %d open findings to process",
            len(open_findings),
        )

        # 2. Group by action using registry
        from body.atomic.registry import action_registry

        action_groups: dict[str, list[dict[str, Any]]] = {}
        unmappable: list[dict[str, Any]] = []

        for finding in open_findings:
            rule = finding["payload"].get("rule", "")
            definition = action_registry.get_by_check_id(rule)

            if definition:
                action_groups.setdefault(definition.action_id, [])
                action_groups[definition.action_id].append(finding)
            else:
                unmappable.append(finding)
                logger.debug(
                    "ViolationRemediatorWorker: no action registered for rule '%s'",
                    rule,
                )

        # 3. Deduplicate against active proposals
        active_action_ids = await self._get_active_proposal_action_ids()

        # 4. Create proposals + 5. Mark entries resolved
        proposals_created: list[str] = []
        proposals_skipped: list[str] = []
        entries_resolved: int = 0

        for action_id, findings in action_groups.items():
            if action_id in active_action_ids:
                logger.info(
                    "ViolationRemediatorWorker: skipping '%s' — active proposal exists",
                    action_id,
                )
                proposals_skipped.append(action_id)
                continue

            proposal_id = await self._create_proposal(action_id, findings)

            if proposal_id:
                proposals_created.append(action_id)
                # Mark all findings for this action as resolved
                resolved = await self._resolve_entries(
                    [f["entry_id"] for f in findings]
                )
                entries_resolved += resolved
                logger.info(
                    "ViolationRemediatorWorker: created proposal '%s' for action '%s' "
                    "(%d findings, %d entries resolved)",
                    proposal_id,
                    action_id,
                    len(findings),
                    resolved,
                )

        # 6. Post blackboard report
        await self.post_report(
            subject="violation_remediator.completed",
            payload={
                "open_findings": len(open_findings),
                "unmappable": len(unmappable),
                "action_groups": len(action_groups),
                "proposals_created": len(proposals_created),
                "proposals_skipped_dedup": len(proposals_skipped),
                "entries_resolved": entries_resolved,
                "created_actions": proposals_created,
                "skipped_actions": proposals_skipped,
                "unmappable_rules": list(
                    {f["payload"].get("rule", "unknown") for f in unmappable}
                ),
            },
        )

        logger.info(
            "ViolationRemediatorWorker: done — %d proposals created, "
            "%d skipped (dedup), %d unmappable findings",
            len(proposals_created),
            len(proposals_skipped),
            len(unmappable),
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    # ID: d6e7f8a9-b0c1-2345-defa-234567890125
    async def _load_open_findings(self) -> list[dict[str, Any]]:
        """
        Query Blackboard for open audit violation findings.

        Returns list of dicts with: entry_id, subject, payload.
        """
        from body.services.service_registry import service_registry

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.fetch_open_findings(
                prefix=f"{_FINDING_SUBJECT_PREFIX}%", limit=200
            )
        except Exception as e:
            logger.error("ViolationRemediatorWorker: failed to load findings: %s", e)
            return []

    # ID: e7f8a9b0-c1d2-3456-efab-345678901236
    async def _get_active_proposal_action_ids(self) -> set[str]:
        """
        Return action IDs that already have an active proposal.
        Fail open — if unavailable, proceed without dedup.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_repository import ProposalRepository

        active: set[str] = set()
        try:
            async with service_registry.session() as session:
                repo = ProposalRepository(session)
                for status in _ACTIVE_STATUSES:
                    proposals = await repo.list_by_status(status, limit=200)
                    for proposal in proposals:
                        for action in proposal.actions:
                            active.add(action.action_id)
        except Exception as e:
            logger.warning(
                "ViolationRemediatorWorker: could not load active proposals (%s). "
                "Proceeding without deduplication.",
                e,
            )
        return active

    # ID: f8a9b0c1-d2e3-4567-fabc-456789012347
    async def _create_proposal(
        self,
        action_id: str,
        findings: list[dict[str, Any]],
    ) -> str | None:
        """Create and persist a Proposal for the given action and findings.

        Safe proposals (approval_required=False) are created in APPROVED status
        so ProposalConsumerWorker can execute them without a separate approval step.
        Proposals requiring human approval are created in DRAFT.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_repository import ProposalRepository

        affected_files: list[str] = sorted(
            {
                f["payload"].get("file_path", "")
                for f in findings
                if f["payload"].get("file_path")
            }
        )

        rules = sorted({f["payload"].get("rule", "unknown") for f in findings})

        proposal = Proposal(
            goal=(
                f"Autonomous remediation: {action_id} "
                f"({len(findings)} violation(s) — rules: {', '.join(rules)})"
            ),
            actions=[
                ProposalAction(
                    action_id=action_id,
                    parameters={"write": True},
                    order=0,
                )
            ],
            scope=ProposalScope(files=affected_files),
            created_by="violation_remediator_worker",
            constitutional_constraints={
                "source": "blackboard_findings",
                "rules": rules,
                "affected_files_count": len(affected_files),
            },
        )

        # compute_risk() sets approval_required correctly based on CORE's actual
        # risk model: "safe" / "moderate" / "dangerous". The previous code compared
        # against "high"/"critical" which don't exist — approval_required was always
        # stuck at False regardless of actual risk level.
        proposal.compute_risk()

        # Skip the DRAFT→PENDING→APPROVED ceremony for proposals that don't need
        # human sign-off. ProposalConsumerWorker only picks up APPROVED proposals,
        # so anything left in DRAFT would never execute.
        if not proposal.approval_required:
            proposal.status = ProposalStatus.APPROVED
            logger.info(
                "ViolationRemediatorWorker: proposal for '%s' auto-approved "
                "(risk=%s, approval_required=False)",
                action_id,
                proposal.risk.overall_risk if proposal.risk else "unknown",
            )
        else:
            logger.info(
                "ViolationRemediatorWorker: proposal for '%s' requires human approval "
                "(risk=%s) — created in DRAFT",
                action_id,
                proposal.risk.overall_risk if proposal.risk else "unknown",
            )

        is_valid, errors = proposal.validate()
        if not is_valid:
            logger.warning(
                "ViolationRemediatorWorker: proposal for '%s' failed validation: %s",
                action_id,
                errors,
            )
            return None

        try:
            async with service_registry.session() as session:
                repo = ProposalRepository(session)
                proposal_id = await repo.create(proposal)
                await session.commit()
            return proposal_id
        except Exception as e:
            logger.error(
                "ViolationRemediatorWorker: failed to persist proposal for '%s': %s",
                action_id,
                e,
            )
            return None

    # ID: a9b0c1d2-e3f4-5678-abcd-567890123458
    async def _resolve_entries(self, entry_ids: list[str]) -> int:
        """
        Mark Blackboard entries as resolved.
        Returns count of entries successfully resolved.
        """
        from body.services.service_registry import service_registry

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.resolve_entries(entry_ids)
        except Exception as e:
            logger.error("ViolationRemediatorWorker: failed to resolve entries: %s", e)
            return 0
