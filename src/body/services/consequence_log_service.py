# src/body/services/consequence_log_service.py
"""
ConsequenceLogService - Body layer persistence for proposal execution consequences.

Records the causality chain required for legal traceability:
  Proposal -> Approval -> Execution -> File Changes -> New Findings

Constitutional standing:
- Layer:  body/services — infrastructure service
- No LLM calls. No file writes. Pure data access.
- Session opened via ServiceRegistry.session().
"""

from __future__ import annotations

import json

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 27090aa7-2f6b-4261-ad36-9a19e739c2ad
class ConsequenceLogService:
    """
    Body layer service. Persists execution consequences for every completed proposal.

    One row per proposal in core.proposal_consequences.
    ON CONFLICT DO UPDATE ensures idempotent writes (safe to retry).
    """

    # ID: 51609561-7e96-4ffe-8f41-e5daed71c42d
    async def record(
        self,
        proposal_id: str,
        pre_execution_sha: str | None,
        post_execution_sha: str | None,
        files_changed: list[dict],
        findings_resolved: list,
        authorized_by_rules: list,
    ) -> None:
        """
        Upsert consequence record for a completed proposal.

        Args:
            proposal_id: The proposal that was executed.
            pre_execution_sha: Git HEAD before execution began.
            post_execution_sha: Git HEAD after execution and commit.
            files_changed: List of {"path": str} dicts for each modified file.
            findings_resolved: Finding IDs that this proposal addressed.
            authorized_by_rules: Policy/rule IDs that authorized execution.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    "INSERT INTO core.proposal_consequences "
                    "(proposal_id, pre_execution_sha, "
                    "post_execution_sha, files_changed, "
                    "findings_resolved, authorized_by_rules) "
                    "VALUES (:pid, :pre, :post, :files, "
                    ":findings, :rules) "
                    "ON CONFLICT (proposal_id) DO UPDATE SET "
                    "files_changed = EXCLUDED.files_changed, "
                    "findings_resolved = EXCLUDED.findings_resolved, "
                    "authorized_by_rules = EXCLUDED.authorized_by_rules, "
                    "post_execution_sha = EXCLUDED.post_execution_sha"
                ),
                {
                    "pid": proposal_id,
                    "pre": pre_execution_sha,
                    "post": post_execution_sha,
                    "files": json.dumps(files_changed),
                    "findings": json.dumps(findings_resolved),
                    "rules": json.dumps(authorized_by_rules),
                },
            )
            await session.commit()

        logger.info(
            "Consequence recorded for %s: %d files changed, post_sha=%s",
            proposal_id,
            len(files_changed),
            post_execution_sha,
        )
