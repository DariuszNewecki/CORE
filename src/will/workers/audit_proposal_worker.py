# src/will/workers/audit_proposal_worker.py
# ID: workers.audit_proposal_worker
"""
AuditProposalWorker — Bridge between audit findings and autonomous proposals.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/audit_proposal_worker.yaml):
  Read latest audit findings, identify fixable violations, deduplicate
  against active proposals, create one Proposal per action group.

Design constraints:
- No LLM calls
- No direct file writes (proposals go to DB via ProposalRepository)
- Deduplication: never create a proposal for an action that already has
  an active (DRAFT/PENDING/APPROVED/EXECUTING) proposal
- Confidence gate: only propose actions with confidence >= MIN_CONFIDENCE
  (enforced by AuditAnalyzer)
- One proposal per action — not one per finding
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.autonomy.audit_analyzer import AuditAnalyzer
from shared.config import settings
from shared.logger import getLogger
from shared.workers.base import Worker
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)


logger = getLogger(__name__)

# Statuses that mean "a proposal for this action is already in flight"
_ACTIVE_STATUSES: frozenset[ProposalStatus] = frozenset(
    {
        ProposalStatus.DRAFT,
        ProposalStatus.PENDING,
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
    }
)


# ID: a3b4c5d6-e7f8-9012-abcd-ef1234567891
class AuditProposalWorker(Worker):
    """
    Acting worker that converts audit findings into governed proposals.

    Runs after the constitutional audit. For each auto-fixable action group:
    1. Checks if an active proposal already exists for that action → skip if yes
    2. Creates a Proposal with the action and affected file scope
    3. Persists via ProposalRepository
    4. Posts a blackboard report

    The execution machinery (ProposalExecutor) is a separate concern —
    this worker only proposes, never executes.
    """

    declaration_name = "audit_proposal_worker"

    def __init__(self, cognitive_service=None) -> None:
        """Accept cognitive_service from runner — not used, this worker needs no LLM."""
        super().__init__()

    # ID: b4c5d6e7-f8a9-0123-bcde-f12345678902
    async def run(self) -> None:
        """
        Core work unit: findings → deduplication → proposals → blackboard report.
        """
        repo_root = Path(settings.REPO_PATH)

        # 1. Analyse findings
        analyzer = AuditAnalyzer(repo_root=repo_root)
        analysis = analyzer.analyze_findings()

        if analysis["status"] != "success":
            await self.post_report(
                subject="audit_proposal_worker.skipped",
                payload={
                    "reason": analysis.get("message", analysis["status"]),
                    "auto_fixable_count": 0,
                    "proposals_created": 0,
                },
            )
            logger.info(
                "AuditProposalWorker: skipped — %s",
                analysis.get("message", analysis["status"]),
            )
            return

        fixable_by_action: dict[str, list[dict[str, Any]]] = analysis[
            "fixable_by_action"
        ]

        if not fixable_by_action:
            await self.post_report(
                subject="audit_proposal_worker.nothing_to_propose",
                payload={
                    "total_findings": analysis["total_findings"],
                    "auto_fixable_count": 0,
                    "proposals_created": 0,
                },
            )
            logger.info("AuditProposalWorker: no fixable findings — nothing to propose")
            return

        # 2. Get active proposals to deduplicate
        active_action_ids = await self._get_active_proposal_action_ids()

        # 3. Create proposals for new action groups
        proposals_created: list[str] = []
        proposals_skipped: list[str] = []

        for action_id, findings in fixable_by_action.items():
            if action_id in active_action_ids:
                logger.info(
                    "AuditProposalWorker: skipping '%s' — active proposal exists",
                    action_id,
                )
                proposals_skipped.append(action_id)
                continue

            proposal_id = await self._create_proposal(action_id, findings)
            if proposal_id:
                proposals_created.append(action_id)
                logger.info(
                    "AuditProposalWorker: created proposal for '%s' (%d findings)",
                    action_id,
                    len(findings),
                )

        # 4. Post blackboard report (mandatory — silence is a constitutional violation)
        await self.post_report(
            subject="audit_proposal_worker.completed",
            payload={
                "total_findings": analysis["total_findings"],
                "auto_fixable_count": analysis["auto_fixable_count"],
                "proposals_created": len(proposals_created),
                "proposals_skipped_dedup": len(proposals_skipped),
                "created_actions": proposals_created,
                "skipped_actions": proposals_skipped,
                "summary": analysis.get("summary_by_action", []),
            },
        )

        logger.info(
            "AuditProposalWorker: done — %d proposals created, %d skipped (dedup)",
            len(proposals_created),
            len(proposals_skipped),
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    # ID: c5d6e7f8-a9b0-1234-cdef-123456789013
    async def _get_active_proposal_action_ids(self) -> set[str]:
        """
        Return the set of action IDs that already have an active proposal.

        Queries all DRAFT/PENDING/APPROVED/EXECUTING proposals and extracts
        the action IDs they contain. Used for deduplication.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_repository import ProposalRepository

        active_action_ids: set[str] = set()

        try:
            async with service_registry.session() as session:
                repo = ProposalRepository(session)
                for status in _ACTIVE_STATUSES:
                    proposals = await repo.list_by_status(status, limit=200)
                    for proposal in proposals:
                        for action in proposal.actions:
                            active_action_ids.add(action.action_id)
        except Exception as e:
            # Fail open — if we can't check, we'll create duplicates rather than
            # silently skip everything. Duplicates are recoverable; silence is not.
            logger.warning(
                "AuditProposalWorker: could not load active proposals for dedup (%s). "
                "Proceeding without deduplication.",
                e,
            )

        return active_action_ids

    # ID: d6e7f8a9-b0c1-2345-defa-234567890124
    async def _create_proposal(
        self,
        action_id: str,
        findings: list[dict[str, Any]],
    ) -> str | None:
        """
        Create and persist a single Proposal for the given action and findings.

        Returns the proposal_id on success, None on failure.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_repository import ProposalRepository

        # Collect affected files for scope declaration
        affected_files: list[str] = sorted(
            {
                f.get("file_path") or f.get("file", "")
                for f in findings
                if f.get("file_path") or f.get("file")
            }
        )

        finding_summary = f"{len(findings)} finding(s) of type {findings[0].get('check_id', 'unknown')}"

        proposal = Proposal(
            goal=(
                f"Autonomous remediation: {action_id} "
                f"({len(findings)} violation(s))"
            ),
            actions=[
                ProposalAction(
                    action_id=action_id,
                    parameters={"write": True},
                    order=0,
                )
            ],
            scope=ProposalScope(files=affected_files),
            created_by="audit_proposal_worker",
            constitutional_constraints={
                "source": "audit_findings",
                "finding_summary": finding_summary,
                "affected_files_count": len(affected_files),
            },
        )

        # Compute risk and set approval requirement
        risk = proposal.compute_risk()
        proposal.approval_required = risk.overall_risk in ("high", "critical")

        # Validate before persisting
        is_valid, errors = proposal.validate()
        if not is_valid:
            logger.warning(
                "AuditProposalWorker: proposal for '%s' failed validation: %s",
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
                "AuditProposalWorker: failed to persist proposal for '%s': %s",
                action_id,
                e,
            )
            return None
