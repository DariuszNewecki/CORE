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


# ID: c4a5b6d7-8e9f-4a1b-9c2d-3e4f5a6b7c8d
class CommitReachabilityAuditor(Worker):
    """
    Sensing worker. Checks every post_execution_sha in
    core.proposal_consequences for branch reachability. Posts
    governance.edge5.orphan_sha::{proposal_id} findings for any
    unreachable commit.

    Runs hourly (schedule.max_interval: 3600 in YAML).
    """

    declaration_name = ""

    def __init__(self, core_context: Any, declaration_name: str) -> None:
        super().__init__(declaration_name=declaration_name)
        self._core_context = core_context

    # ID: d5b6c7e8-9f0a-4b2c-8d3e-4f5a6b7c8d9e
    async def run(self) -> None:
        await self.post_heartbeat()

        consequence_svc = (
            await self._core_context.registry.get_consequence_log_service()
        )
        pairs = await consequence_svc.get_all_shas()

        repo_path = str(self._core_context.git_service.repo_path)

        checked = 0
        orphans = 0

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
                logger.warning(
                    "CommitReachabilityAuditor: orphan SHA %s for proposal %s",
                    sha,
                    proposal_id,
                )
                await self.post_finding(
                    subject=f"governance.edge5.orphan_sha::{proposal_id}",
                    payload={
                        "proposal_id": proposal_id,
                        "orphan_sha": sha,
                        "detected_at": datetime.now(UTC).isoformat(),
                    },
                )

        await self.post_report(
            subject="commit_reachability_auditor.run.complete",
            payload={
                "checked": checked,
                "orphans_detected": orphans,
            },
        )
        logger.info(
            "CommitReachabilityAuditor: checked=%d orphans=%d",
            checked,
            orphans,
        )
