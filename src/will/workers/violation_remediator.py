# src/will/workers/violation_remediator.py
# ID: workers.violation_remediator
"""
ViolationRemediatorWorker - Closes the autonomous audit loop.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/violation_remediator.yaml):
  Consume open audit violation findings from the Blackboard, look up the
  remediating action from .intent/enforcement/mappings/remediation/auto_remediation.yaml
  (via _load_remediation_map), create one Proposal per unique action group,
  and mark each consumed Blackboard entry as resolved.

The autonomous audit loop this closes:

  AuditViolationSensor (sensing)
      posts open findings to Blackboard
          ↓
  ViolationRemediatorWorker (acting)  ← THIS WORKER
      reads open findings from Blackboard
      looks up action via remediation map from .intent/
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

    Reads open audit.violation findings, maps each rule to a remediation
    action via .intent/ remediation map, groups by action, deduplicates
    against active proposals, creates proposals, marks entries resolved.

    Safe proposals (approval_required=False) are created in APPROVED status
    so ProposalConsumerWorker can execute them without a separate approval step.
    """

    declaration_name = "violation_remediator"

    def __init__(
        self, core_context: Any = None, declaration_name: str = "", **kwargs: Any
    ) -> None:
        """Accept daemon kwargs — stores core_context for repo path resolution."""
        super().__init__(declaration_name=declaration_name)
        self._core_context = core_context

    def _get_remediation_map(self) -> dict:
        """Load rule-to-action mappings from .intent/ via PathResolver."""
        from body.autonomy.audit_analyzer import _load_remediation_map
        from shared.path_resolver import PathResolver

        path_resolver = PathResolver(self._core_context.git_service.repo_path)
        return _load_remediation_map(path_resolver)

    # ID: c5d6e7f8-a9b0-1234-cdef-123456789014
    async def run(self) -> None:
        """
        Core work unit:
        1. Load open violation findings from Blackboard
        2. Group by action (via .intent/ remediation map)
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

        # 2. Group by action using .intent/ remediation map
        remediation_map = self._get_remediation_map()

        action_groups: dict[str, list[dict[str, Any]]] = {}
        unmappable: list[dict[str, Any]] = []

        for finding in open_findings:
            rule = finding["payload"].get("check_id") or finding["payload"].get(
                "rule", ""
            )
            entry = remediation_map.get(rule)

            if entry:
                action_id = entry["action"]
                action_groups.setdefault(action_id, [])
                action_groups[action_id].append(finding)
            else:
                unmappable.append(finding)
                logger.debug(
                    "ViolationRemediatorWorker: no remediation mapping for rule '%s'",
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
                resolved = await self._resolve_entries([f["id"] for f in findings])
                entries_resolved += resolved
                logger.info(
                    "ViolationRemediatorWorker: created proposal '%s' for action '%s' "
                    "(%d findings, %d entries resolved)",
                    proposal_id,
                    action_id,
                    len(findings),
                    resolved,
                )

        # 5b. Release unmappable findings back to open so they don't stay claimed
        entries_released = await self._release_unmappable(unmappable)
        if entries_released:
            logger.info(
                "ViolationRemediatorWorker: released %d unmappable findings back to open",
                entries_released,
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
                "entries_released": entries_released,
                "created_actions": proposals_created,
                "skipped_actions": proposals_skipped,
                "unmappable_rules": list(
                    {
                        f["payload"].get("check_id")
                        or f["payload"].get("rule", "unknown")
                        for f in unmappable
                    }
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

        Claims findings atomically, then immediately filters out any whose
        check_id/rule has no entry in the .intent/ remediation map.  Unmappable
        findings are released back to open status so they are not held
        claimed indefinitely.

        Returns only mappable findings (list of dicts with: id, subject, payload).
        """
        from body.services.service_registry import service_registry

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            claimed = await blackboard_service.claim_violation_findings(
                prefix=f"{_FINDING_SUBJECT_PREFIX}%",
                limit=200,
                claimed_by=self._worker_uuid,
            )
        except Exception as e:
            logger.error("ViolationRemediatorWorker: failed to load findings: %s", e)
            return []

        if not claimed:
            return []

        # Post-claim filter: keep only findings with a known remediation mapping.
        remediation_map = self._get_remediation_map()
        mappable: list[dict[str, Any]] = []
        unmappable_ids: list[str] = []

        for finding in claimed:
            rule = finding["payload"].get("check_id") or finding["payload"].get(
                "rule", ""
            )
            if remediation_map.get(rule):
                mappable.append(finding)
            else:
                unmappable_ids.append(finding["id"])

        # Immediately release unmappable findings so they don't stay claimed.
        if unmappable_ids:
            try:
                released = await blackboard_service.release_claimed_entries(
                    unmappable_ids
                )
                logger.info(
                    "ViolationRemediatorWorker: released %d/%d unmappable "
                    "findings at claim time",
                    released,
                    len(unmappable_ids),
                )
            except Exception as e:
                logger.error(
                    "ViolationRemediatorWorker: failed to release "
                    "unmappable findings at claim time: %s",
                    e,
                )

        return mappable

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

        rules = sorted(
            {
                f["payload"].get("check_id") or f["payload"].get("rule", "unknown")
                for f in findings
            }
        )

        proposal = Proposal(
            goal=(
                f"Autonomous remediation: {action_id} "
                f"({len(findings)} violation(s) — rules: {', '.join(rules)})"
            ),
            actions=[
                ProposalAction(
                    action_id=action_id,
                    parameters={
                        "write": True,
                        "file_path": affected_files[0] if affected_files else None,
                    },
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

    # ID: b0c1d2e3-f4a5-6789-bcde-678901234569
    async def _release_unmappable(self, findings: list[dict[str, Any]]) -> int:
        """
        Release claimed findings that have no registered remediation action
        back to open status so another worker or a future registry update
        can pick them up.
        """
        if not findings:
            return 0

        from body.services.service_registry import service_registry

        entry_ids = [f["id"] for f in findings]
        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.release_claimed_entries(entry_ids)
        except Exception as e:
            logger.error(
                "ViolationRemediatorWorker: failed to release unmappable entries: %s", e
            )
            return 0
