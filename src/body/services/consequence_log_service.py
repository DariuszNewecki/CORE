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

from sqlalchemy import Integer, String, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG_CL = load_operational_config().consequence_log


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
        declared_production: list[str] | None = None,
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
            declared_production: ADR-129 D2 — union of _sandbox_target_paths
                and files_produced; the paths commit_paths was authorized to
                commit. Empty list for pre-ADR-129 rows (worker skips them).
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    "INSERT INTO core.proposal_consequences "
                    "(proposal_id, pre_execution_sha, "
                    "post_execution_sha, files_changed, "
                    "findings_resolved, authorized_by_rules, "
                    "declared_production) "
                    "VALUES (:pid, :pre, :post, :files, "
                    ":findings, :rules, :declared) "
                    "ON CONFLICT (proposal_id) DO UPDATE SET "
                    "files_changed = EXCLUDED.files_changed, "
                    "findings_resolved = EXCLUDED.findings_resolved, "
                    "authorized_by_rules = EXCLUDED.authorized_by_rules, "
                    "post_execution_sha = EXCLUDED.post_execution_sha, "
                    "declared_production = EXCLUDED.declared_production"
                ),
                {
                    "pid": proposal_id,
                    "pre": pre_execution_sha,
                    "post": post_execution_sha,
                    "files": json.dumps(files_changed),
                    "findings": json.dumps(findings_resolved),
                    "rules": json.dumps(authorized_by_rules),
                    "declared": json.dumps(declared_production or []),
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
        lookback_seconds: int = _CFG_CL.default_lookback_seconds,
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

        Notes:
            The ``bindparams(...)`` call is required. Without explicit
            parameter types, ``jsonb_build_object`` (which accepts
            ``"any"``) and ``make_interval(secs => ...)`` (named-argument
            syntax) leave Postgres unable to infer the parameter types at
            prepare time, raising
            ``IndeterminateDatatypeError: could not determine data type
            of parameter $1`` under asyncpg. SQL-level ``::text`` /
            ``::int`` casts are not a viable alternative — SQLAlchemy's
            ``text()`` parser collides with the ``::`` syntax during
            ``:name`` → ``$N`` translation and produces a
            ``PostgresSyntaxError``. ``bindparams`` declares the types at
            the SQLAlchemy layer; semantics are unchanged.
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
                ).bindparams(
                    bindparam("file_path", type_=String),
                    bindparam("lookback_seconds", type_=Integer),
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

    # ID: a2f610da-3b85-4c67-9d12-8e7f5a4b3c21
    async def get_recent_for_audit(self, lookback_days: int = 7) -> list[dict]:
        """
        Return consequence rows with a post-commit SHA from the last N days.

        Used by CommitAuthorshipAuditWorker (ADR-129 D4) to cross-check
        declared_production against the actual git diff without the worker
        touching the git object store directly. Returns dicts with keys:
        proposal_id, post_execution_sha, files_changed, declared_production.

        Rows where declared_production is [] are pre-ADR-129 rows; the
        caller skips them (empty list means "unverifiable", not "no files").
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    "SELECT proposal_id, pre_execution_sha, "
                    "post_execution_sha, files_changed, declared_production "
                    "FROM core.proposal_consequences "
                    "WHERE post_execution_sha IS NOT NULL "
                    "AND recorded_at >= NOW() - "
                    "make_interval(days => :lookback_days)"
                ).bindparams(bindparam("lookback_days", type_=Integer)),
                {"lookback_days": lookback_days},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": row.proposal_id,
                "pre_execution_sha": row.pre_execution_sha,
                "post_execution_sha": row.post_execution_sha,
                "files_changed": row.files_changed or [],
                "declared_production": row.declared_production or [],
            }
            for row in rows
        ]

    # ID: 01083b24-5d71-460e-a5f7-a09d9930ff69
    async def get_chain_for_proposal(
        self, proposal_id: str, session: AsyncSession
    ) -> dict | None:
        """
        Return the full governance chain for a proposal using a caller-supplied session.

        Joins core.autonomous_proposals (LEFT JOIN core.proposal_consequences) and
        separately fetches linked core.blackboard_entries where
        payload->>'proposal_id' = proposal_id. Returns None when no proposal row
        exists. consequence is None when the proposal has not yet been executed.
        """
        proposal_row = (
            await session.execute(
                text(
                    "SELECT ap.proposal_id, ap.goal, ap.status, ap.risk, "
                    "ap.approval_authority, ap.approved_by, ap.approved_at, "
                    "ap.execution_results, ap.created_by, ap.created_at, "
                    "ap.failure_reason, "
                    "pc.pre_execution_sha, pc.post_execution_sha, "
                    "pc.files_changed, pc.findings_resolved, "
                    "pc.authorized_by_rules, pc.recorded_at AS consequence_recorded_at "
                    "FROM core.autonomous_proposals ap "
                    "LEFT JOIN core.proposal_consequences pc "
                    "  ON pc.proposal_id = ap.proposal_id "
                    "WHERE ap.proposal_id = :proposal_id"
                ),
                {"proposal_id": proposal_id},
            )
        ).first()

        if proposal_row is None:
            return None

        findings_rows = (
            await session.execute(
                text(
                    "SELECT id::text AS entry_id, subject, payload, "
                    "status, created_at "
                    "FROM core.blackboard_entries "
                    "WHERE entry_type = 'finding' "
                    "AND payload->>'proposal_id' = :proposal_id "
                    "ORDER BY created_at"
                ),
                {"proposal_id": proposal_id},
            )
        ).fetchall()

        has_consequence = proposal_row.consequence_recorded_at is not None
        return {
            "proposal": {
                "proposal_id": proposal_row.proposal_id,
                "goal": proposal_row.goal,
                "status": proposal_row.status,
                "risk": proposal_row.risk,
                "approval_authority": proposal_row.approval_authority,
                "approved_by": proposal_row.approved_by,
                "approved_at": (
                    proposal_row.approved_at.isoformat()
                    if proposal_row.approved_at
                    else None
                ),
                "execution_results": proposal_row.execution_results,
                "created_by": proposal_row.created_by,
                "created_at": proposal_row.created_at.isoformat(),
                "failure_reason": proposal_row.failure_reason,
            },
            "findings": [
                {
                    "entry_id": r.entry_id,
                    "subject": r.subject,
                    "status": r.status,
                    "check_id": (r.payload or {}).get("check_id"),
                    "rule_id": (r.payload or {}).get("rule_id"),
                    "file_path": (r.payload or {}).get("file_path"),
                    "severity": (r.payload or {}).get("severity"),
                    "evidence": (r.payload or {}).get("context"),
                    "evidence_class": (r.payload or {}).get("evidence_class"),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in findings_rows
            ],
            "consequence": {
                "pre_execution_sha": proposal_row.pre_execution_sha,
                "post_execution_sha": proposal_row.post_execution_sha,
                "files_changed": proposal_row.files_changed or [],
                "findings_resolved": proposal_row.findings_resolved or [],
                "authorized_by_rules": proposal_row.authorized_by_rules or [],
                "recorded_at": proposal_row.consequence_recorded_at.isoformat(),
            }
            if has_consequence
            else None,
        }

    # ID: ef53e3b4-6668-49a5-a712-491a6fef4514
    async def get_finding_proposal_link(
        self, entry_id: str, session: AsyncSession
    ) -> str | None:
        """
        Read payload->>'proposal_id' from a blackboard entry.

        Returns the linked proposal_id string, or None when the entry does not
        exist or has no proposal_id in its payload.
        """
        row = (
            await session.execute(
                text(
                    "SELECT payload->>'proposal_id' AS proposal_id "
                    "FROM core.blackboard_entries "
                    "WHERE id = cast(:entry_id as uuid)"
                ),
                {"entry_id": entry_id},
            )
        ).first()

        if row is None:
            return None
        return row.proposal_id  # may be None if key absent

    # ID: 8e67aa3b-5ac7-4fc3-8874-6c7876e2531e
    async def get_all_shas_with_status(self) -> list[tuple[str, str, str | None]]:
        """
        Return all (proposal_id, post_execution_sha, proposal_status) triples
        by joining core.proposal_consequences with core.autonomous_proposals.

        proposal_status is None when no matching proposal row exists.
        Used by CommitReachabilityAuditor (ADR-019 D1) to include proposal_status
        in orphan-commit findings so the governor has full context.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    "SELECT pc.proposal_id, pc.post_execution_sha, "
                    "ap.status AS proposal_status "
                    "FROM core.proposal_consequences pc "
                    "LEFT JOIN core.autonomous_proposals ap "
                    "  ON ap.proposal_id = pc.proposal_id "
                    "WHERE pc.post_execution_sha IS NOT NULL"
                )
            )
            return [
                (row.proposal_id, row.post_execution_sha, row.proposal_status)
                for row in result.fetchall()
            ]
