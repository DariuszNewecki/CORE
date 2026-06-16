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
Git shell-out via subprocess to self.core_context.git_service.repo_path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


async def _capture_commit_meta(repo_path: str, sha: str) -> dict[str, str]:
    """Capture an orphan commit's metadata before git gc erases it (#658).

    ``git show -s`` still resolves a *dangling* (branch-unreachable) commit
    until ``git gc`` prunes the object, so the orphan finding can carry the
    commit subject / author / date. This lets the governor resolve a
    ``governance.edge5.orphan_sha`` finding from the finding itself rather
    than via manual git archaeology — and preserves the audit trail past the
    point where the sha would otherwise point at nothing. Returns a sentinel
    subject when the object is already gone.
    """
    proc = await asyncio.create_subprocess_exec(
        "git",
        "show",
        "-s",
        "--format=%s%n%an%n%cI",
        sha,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=repo_path,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return {"commit_subject": "<object not in store — gc'd before reconcile>"}
    lines = out.decode().splitlines()
    return {
        "commit_subject": lines[0] if len(lines) > 0 else "",
        "commit_author": lines[1] if len(lines) > 1 else "",
        "commit_date": lines[2] if len(lines) > 2 else "",
    }


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
        """
        Performs a commit reachability audit to identify and report orphan SHA proposals.

        Scans the repository for commits that are not contained in any branches and logs them as findings,
        ensuring governance of edge5 architectural integrity through constitutional enforcement.

        Args:
            None

        Returns:
            None

        Raises:
            None"""
        await self.post_heartbeat()

        from body.services.service_registry import service_registry

        blackboard_service = await service_registry.get_blackboard_service()
        existing = await blackboard_service.fetch_active_finding_subjects_by_prefix(
            "governance.edge5.orphan_sha::%"
        )

        consequence_svc = (
            await self._core_context.registry.get_consequence_log_service()
        )
        pairs = await consequence_svc.get_all_shas()

        repo_path = str(self._core_context.git_service.repo_path)

        checked = 0
        orphans = 0
        suppressed = 0

        for proposal_id, sha in pairs:
            checked += 1
            proc = await asyncio.create_subprocess_exec(
                "git",
                "branch",
                "--contains",
                sha,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )
            stdout, _ = await proc.communicate()
            if not stdout.decode().strip():
                orphans += 1
                subject = f"governance.edge5.orphan_sha::{proposal_id}"
                if subject in existing:
                    suppressed += 1
                    logger.debug(
                        "CommitReachabilityAuditor: %s already open, skipping.",
                        subject,
                    )
                    continue
                logger.warning(
                    "CommitReachabilityAuditor: orphan SHA %s for proposal %s",
                    sha,
                    proposal_id,
                )
                # #658: capture the dangling commit's metadata now, before
                # git gc prunes it — so the finding is self-describing and the
                # audit trail survives even after the sha points at nothing.
                meta = await _capture_commit_meta(repo_path, sha)
                await self.post_observation(
                    subject=subject,
                    payload={
                        "proposal_id": proposal_id,
                        "orphan_sha": sha,
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
            },
        )
        logger.info(
            "CommitReachabilityAuditor: checked=%d orphans=%d suppressed=%d",
            checked,
            orphans,
            suppressed,
        )
