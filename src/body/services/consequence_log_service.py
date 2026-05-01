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

    # ID: b3f4a8c2-7e5d-4f91-9a2b-6c8d4e1f7a3c
    async def find_cause_for_file(
        self,
        file_path: str,
        lookback_seconds: int = 3600,
    ) -> dict[str, str | None]:
        """
        Heuristic lookup: most recent proposal that touched ``file_path`` within window.

        Returns the proposal_id and post_execution_sha of the most recent
        ``core.proposal_consequences`` row whose ``files_changed`` jsonb
        contains a ``{"path": file_path}`` object AND whose ``recorded_at`` is
        within ``lookback_seconds`` of NOW().

        Implements ADR-015 D5 (sensor cause attribution via proposal_consequences
        lookup) for the URS Q6.F / Q6.R read paths. The match is a heuristic —
        multiple recent proposals can touch the same file; most-recent wins.

        Args:
            file_path: Repo-relative file path as written into ``files_changed``
                       (e.g. "src/will/workers/audit_violation_sensor.py").
            lookback_seconds: Recency window. Defaults to 3600 (one hour).

        Returns:
            ``{"causing_proposal_id": str, "causing_commit_sha": str | None}``
            on match; both keys ``None`` when no row matches the file/window.
            ``causing_commit_sha`` may be ``None`` even on match (the column
            is nullable in ``core.proposal_consequences``).
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    "SELECT proposal_id, post_execution_sha "
                    "FROM core.proposal_consequences "
                    "WHERE files_changed @> jsonb_build_array("
                    "jsonb_build_object('path', :file_path)) "
                    "AND recorded_at >= NOW() - "
                    "make_interval(secs => :lookback_seconds) "
                    "ORDER BY recorded_at DESC LIMIT 1"
                ),
                {
                    "file_path": file_path,
                    "lookback_seconds": lookback_seconds,
                },
            )
            row = result.first()

        if row is None:
            return {"causing_proposal_id": None, "causing_commit_sha": None}

        return {
            "causing_proposal_id": row.proposal_id,
            "causing_commit_sha": row.post_execution_sha,
        }

    # ID: e6c7d8f9-0a1b-4c3d-9e4f-5a6b7c8d9e0f
    async def get_all_shas(self) -> list[tuple[str, str]]:
        """
        Return all (proposal_id, post_execution_sha) pairs from
        core.proposal_consequences where post_execution_sha is not null.

        Used by CommitReachabilityAuditor (ADR-019 D1) to verify commit
        reachability without querying git history from a Will worker directly.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    "SELECT proposal_id, post_execution_sha "
                    "FROM core.proposal_consequences "
                    "WHERE post_execution_sha IS NOT NULL"
                )
            )
            return [
                (row.proposal_id, row.post_execution_sha) for row in result.fetchall()
            ]
