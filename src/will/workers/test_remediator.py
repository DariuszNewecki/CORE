# src/will/workers/test_remediator.py
# ID: workers.test_remediator
"""
TestRemediatorWorker - Routes test signals to autonomous test generation.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/test_remediator.yaml):
  Consume open test.missing and test.failure findings from the Blackboard
  and create a build.tests proposal that drives autonomous test generation
  for the affected source files. Every claimed finding is routed to the
  single 'build.tests' action — no remediation map lookup, no unmappable
  or delegate split.

The autonomous test loop this participates in:

  TestRunnerSensor (sensing)
      posts test.missing::<source_file> and
            test.failure::<test_file>::<test_name> findings
          ↓
  TestRemediatorWorker (acting)  ← THIS WORKER
      reads open findings from Blackboard
      groups every finding under the 'build.tests' action
      creates a Proposal (deduped against active)
      marks findings resolved
          ↓
  ProposalConsumerWorker
      executes APPROVED proposals via ProposalExecutor
          ↓
  TestRunnerSensor runs again
      confirms the test is now present / passing

Design constraints:
- No LLM calls
- No direct file writes
- Never creates a proposal if an active 'build.tests' one exists
- Marks Blackboard entries resolved AFTER proposal is persisted (not before)
- Routes every claimed finding to a single 'build.tests' action group
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

_MISSING_SUBJECT_PREFIX = "test.missing::"
_FAILURE_SUBJECT_PREFIX = "test.failure::"
_TARGET_ACTION_ID = "build.tests"
_TARGET_RULES: list[str] = ["test.missing", "test.failure"]

_ACTIVE_STATUSES: frozenset[ProposalStatus] = frozenset(
    {
        ProposalStatus.DRAFT,
        ProposalStatus.PENDING,
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
    }
)


# ID: e9f2a4b6-c1d8-4e3f-9a5b-7c8d1e2f3a4b
class TestRemediatorWorker(Worker):
    """
    Acting worker that converts Blackboard test findings into build.tests proposals.

    Claims open test.missing and test.failure findings (two prefixes, merged),
    routes every finding to the single 'build.tests' action, deduplicates
    against active proposals, creates one proposal, marks entries resolved.
    """

    declaration_name = "test_remediator"

    def __init__(
        self, core_context: Any = None, declaration_name: str = "", **kwargs: Any
    ) -> None:
        """Accept daemon kwargs — stores core_context for symmetry with siblings."""
        super().__init__(declaration_name=declaration_name)
        self._core_context = core_context

    # ID: f1a3b5c7-d2e4-4f6a-8b9c-1d2e3f4a5b6c
    async def run(self) -> None:
        """
        Core work unit:
        1. Claim open test.missing + test.failure findings from Blackboard
        2. Route every finding to the single 'build.tests' action group
        3. Deduplicate against active proposals
        4. Create proposal (or release on dedup skip)
        5. Mark consumed Blackboard entries resolved
        6. Post blackboard report
        """
        open_findings = await self._load_open_findings()

        if not open_findings:
            await self.post_heartbeat()
            logger.info("TestRemediatorWorker: no open test findings")
            return

        logger.info(
            "TestRemediatorWorker: %d open findings to process",
            len(open_findings),
        )

        active_action_ids = await self._get_active_proposal_action_ids()

        proposals_created: list[str] = []
        proposals_skipped: list[str] = []
        entries_resolved: int = 0
        entries_released: int = 0

        if _TARGET_ACTION_ID in active_action_ids:
            logger.info(
                "TestRemediatorWorker: skipping '%s' — active proposal exists",
                _TARGET_ACTION_ID,
            )
            proposals_skipped.append(_TARGET_ACTION_ID)
            entries_released = await self._release_entries(
                [f["id"] for f in open_findings]
            )
        else:
            proposal_id = await self._create_proposal(_TARGET_ACTION_ID, open_findings)

            if proposal_id:
                proposals_created.append(_TARGET_ACTION_ID)
                entries_resolved = await self._resolve_entries(
                    [f["id"] for f in open_findings]
                )
                logger.info(
                    "TestRemediatorWorker: created proposal '%s' for action '%s' "
                    "(%d findings, %d entries resolved)",
                    proposal_id,
                    _TARGET_ACTION_ID,
                    len(open_findings),
                    entries_resolved,
                )

        await self.post_report(
            subject="test_remediator.completed",
            payload={
                "open_findings": len(open_findings),
                "proposals_created": len(proposals_created),
                "proposals_skipped_dedup": len(proposals_skipped),
                "entries_resolved": entries_resolved,
                "entries_released": entries_released,
                "created_actions": proposals_created,
                "skipped_actions": proposals_skipped,
            },
        )

        logger.info(
            "TestRemediatorWorker: done — %d proposals created, "
            "%d skipped (dedup), %d entries resolved, %d entries released",
            len(proposals_created),
            len(proposals_skipped),
            entries_resolved,
            entries_released,
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _load_open_findings(self) -> list[dict[str, Any]]:
        """
        Claim open test.missing and test.failure findings from the Blackboard.

        Two separate claim_violation_findings calls (one per prefix) whose
        results are merged. Findings without a source_file in payload are
        released immediately so they do not stay claimed indefinitely.
        """
        from body.services.service_registry import service_registry

        merged: list[dict[str, Any]] = []

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            for prefix in (_MISSING_SUBJECT_PREFIX, _FAILURE_SUBJECT_PREFIX):
                claimed = await blackboard_service.claim_violation_findings(
                    prefix=f"{prefix}%",
                    limit=200,
                    claimed_by=self._worker_uuid,
                )
                merged.extend(claimed)
        except Exception as e:
            logger.error("TestRemediatorWorker: failed to load findings: %s", e)
            return []

        if not merged:
            return []

        valid: list[dict[str, Any]] = []
        invalid_ids: list[str] = []
        for finding in merged:
            payload = finding.get("payload") or {}
            if payload.get("source_file"):
                valid.append(finding)
            else:
                invalid_ids.append(finding["id"])

        if invalid_ids:
            try:
                blackboard_service = await service_registry.get_blackboard_service()
                released = await blackboard_service.release_claimed_entries(invalid_ids)
                logger.info(
                    "TestRemediatorWorker: released %d/%d findings missing "
                    "source_file at claim time",
                    released,
                    len(invalid_ids),
                )
            except Exception as e:
                logger.error(
                    "TestRemediatorWorker: failed to release invalid "
                    "findings at claim time: %s",
                    e,
                )

        return valid

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
                "TestRemediatorWorker: could not load active proposals (%s). "
                "Proceeding without deduplication.",
                e,
            )
        return active

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
                f["payload"].get("source_file", "")
                for f in findings
                if f["payload"].get("source_file")
            }
        )

        primary_source_file = affected_files[0] if affected_files else None

        proposal = Proposal(
            goal=(
                f"Autonomous test remediation: {action_id} "
                f"({len(findings)} finding(s) — rules: {', '.join(_TARGET_RULES)})"
            ),
            actions=[
                ProposalAction(
                    action_id=action_id,
                    parameters={
                        "source_file": primary_source_file,
                        "write": True,
                    },
                    order=0,
                )
            ],
            scope=ProposalScope(files=affected_files),
            created_by="test_remediator_worker",
            constitutional_constraints={
                "source": "blackboard_findings",
                "rules": list(_TARGET_RULES),
                "affected_files_count": len(affected_files),
            },
        )

        proposal.compute_risk()

        if not proposal.approval_required:
            proposal.status = ProposalStatus.APPROVED
            logger.info(
                "TestRemediatorWorker: proposal for '%s' auto-approved "
                "(risk=%s, approval_required=False)",
                action_id,
                proposal.risk.overall_risk if proposal.risk else "unknown",
            )
        else:
            logger.info(
                "TestRemediatorWorker: proposal for '%s' requires human approval "
                "(risk=%s) — created in DRAFT",
                action_id,
                proposal.risk.overall_risk if proposal.risk else "unknown",
            )

        is_valid, errors = proposal.validate()
        if not is_valid:
            logger.warning(
                "TestRemediatorWorker: proposal for '%s' failed validation: %s",
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
                "TestRemediatorWorker: failed to persist proposal for '%s': %s",
                action_id,
                e,
            )
            return None

    async def _resolve_entries(self, entry_ids: list[str]) -> int:
        """
        Mark Blackboard entries as resolved.
        Returns count of entries successfully resolved.
        """
        from body.services.service_registry import service_registry

        if not entry_ids:
            return 0

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.resolve_entries(entry_ids)
        except Exception as e:
            logger.error("TestRemediatorWorker: failed to resolve entries: %s", e)
            return 0

    async def _release_entries(self, entry_ids: list[str]) -> int:
        """
        Release claimed findings back to open status.
        Used when proposal creation is skipped by dedup.
        """
        from body.services.service_registry import service_registry

        if not entry_ids:
            return 0

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.release_claimed_entries(entry_ids)
        except Exception as e:
            logger.error("TestRemediatorWorker: failed to release entries: %s", e)
            return 0
