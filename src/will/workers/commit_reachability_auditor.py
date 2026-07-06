# src/will/workers/commit_reachability_auditor.py
"""
CommitReachabilityAuditor — Edge 5 orphan-commit detection sensor.

Reads post_execution_sha values from core.proposal_consequences via
ConsequenceLogService and verifies each commit is reachable from a git
branch. Posts a blackboard finding for each orphan detected.

Constitutional standing:
- Declaration: .intent/workers/commit_reachability_auditor.yaml
- Class: sensing
- Phase: audit
- Permitted tools: none (no LLM calls)
- Approval: false

DB access via Body service registry only (ADR-019 D1).
Git operations via GitService async methods (shared sanctuary; no direct
subprocess in Will per governance.dangerous_execution_primitives).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: c4a5b6d7-8e9f-4a1b-9c2d-3e4f5a6b7c8d
class CommitReachabilityAuditor(Worker):
    """
    Sensing worker. Checks every post_execution_sha in
    core.proposal_consequences for branch reachability. Posts
    governance.edge5.orphan_sha::{proposal_id} findings for any
    unreachable commit.

    Runs hourly (schedule.max_interval: 3600 in YAML).
    """

    declaration_name = "commit_reachability_auditor"

    def __init__(self, core_context: Any) -> None:
        super().__init__()
        self._core_context = core_context

    # ID: d5b6c7e8-9f0a-4b2c-8d3e-4f5a6b7c8d9e
    async def run(self) -> None:
        """Scan all post_execution_sha values and post findings for orphan commits."""
        await self.post_heartbeat()

        from body.services.service_registry import service_registry

        blackboard_service = await service_registry.get_blackboard_service()
        _prefix = "governance.edge5.orphan_sha::%"
        # Orphaned commits can never become reachable again, so governor
        # resolutions and worker abandons are both permanent skips — include
        # resolved and abandoned subjects in the dedup set alongside active ones.
        _active, _resolved, _abandoned = await asyncio.gather(
            blackboard_service.fetch_active_finding_subjects_by_prefix(_prefix),
            blackboard_service.fetch_resolved_finding_subjects_by_prefix(_prefix),
            blackboard_service.fetch_abandoned_finding_subjects_by_prefix(_prefix),
        )
        existing = _active | _resolved | _abandoned

        consequence_svc = (
            await self._core_context.registry.get_consequence_log_service()
        )
        triples = await consequence_svc.get_all_shas_with_status()

        git_service = self._core_context.git_service

        checked = 0
        orphans = 0
        suppressed = 0

        for proposal_id, sha, proposal_status in triples:
            checked += 1
            is_reachable = await git_service.is_commit_on_branch(sha)
            if is_reachable:
                continue

            subject = f"governance.edge5.orphan_sha::{proposal_id}"

            if subject in existing:
                suppressed += 1
                logger.debug(
                    "CommitReachabilityAuditor: %s already active/resolved/abandoned, skipping.",
                    subject,
                )
                continue

            orphans += 1
            logger.warning(
                "CommitReachabilityAuditor: orphan SHA %s for proposal %s (status=%s)",
                sha,
                proposal_id,
                proposal_status,
            )
            # #658: capture the dangling commit's metadata now, before
            # git gc prunes it — so the finding is self-describing and the
            # audit trail survives even after the sha points at nothing.
            meta = await git_service.get_commit_meta(sha)
            await self.post_observation(
                subject=subject,
                payload={
                    "proposal_id": proposal_id,
                    "orphan_sha": sha,
                    "proposal_status": proposal_status,
                    "detected_at": datetime.now(UTC).isoformat(),
                    **meta,
                },
                status="indeterminate",
            )

        await self.post_report(
            subject="commit_reachability_auditor.run.complete",
            payload={
                "checked": checked,
                "orphans_detected": orphans,
                "suppressed": suppressed,
            },
        )
        logger.info(
            "CommitReachabilityAuditor: checked=%d orphans=%d suppressed=%d",
            checked,
            orphans,
            suppressed,
        )
