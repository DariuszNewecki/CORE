# src/body/services/blackboard_service.py
"""
BlackboardService - Centralised data-access layer for core.blackboard_entries.

All blackboard DB operations that Will workers previously performed with
direct get_session() calls are expressed here as named methods.  Workers
must call these methods instead of opening sessions themselves.

Constitutional standing:
- Layer:  body/services — infrastructure service
- Phase:  N/A (shared read/write operations)
- No LLM calls.  No file writes.  Pure data access.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)

# SLA tiers in seconds — must stay in sync with blackboard_auditor constants.
_SLA: dict[str, int] = {
    "heartbeat": 600,
    "finding": 3600,
    "report": 7200,
    "proposal": 1800,
}
_SLA_DEFAULT = 3600


# ID: c397c621-083f-49c8-85a5-4c2b862729e0
class BlackboardService:
    """
    Body layer service.  Exposes named methods for every
    core.blackboard_entries database operation used by Will workers.
    All sessions are opened via ServiceRegistry.session().
    """

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    # ID: b980a1a9-eca8-4268-b8ba-86fbcf94b6ce
    async def fetch_open_finding_subjects_by_prefix(self, prefix: str) -> set[str]:
        """
        Return subjects of non-terminal finding entries whose subject matches
        *prefix* (SQL LIKE pattern — caller supplies the trailing wildcard).

        Covers:
          - AuditViolationSensor._fetch_existing_subjects
          - BlackboardAuditor._fetch_existing_findings
          - IntentInspector._fetch_existing_subjects
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT subject FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status NOT IN ('resolved', 'abandoned')
                    """
                ),
                {"prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}

    # ID: 1b8e7a4c-3f2d-4c5b-9a01-8e6d2f9b0a31
    async def fetch_active_finding_subjects_by_prefix(self, prefix: str) -> set[str]:
        """
        Return subjects of finding entries whose subject matches *prefix*
        that are NOT yet resolved.

        Includes abandoned entries — unlike fetch_open_finding_subjects_by_prefix.
        Use this for sensor deduplication: a finding should not be re-posted
        if an abandoned entry for the same subject already exists.

        Status exclusion: 'resolved' only.
        All other statuses (open, claimed, deferred_to_proposal, indeterminate,
        abandoned) are included — subjects in any of those states are
        considered "already represented on the blackboard" and must not be
        re-posted by a sensor.

        Covers:
          - AuditViolationSensor._fetch_existing_subjects
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT subject FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status NOT IN ('resolved')
                    """
                ),
                {"prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}

    # ID: 6d2f0c8a-9e3b-4a51-b7c8-14e5d6f2a0b9
    async def resolve_dry_run_entries_for_namespace(self, namespace_prefix: str) -> int:
        """
        Resolve all open audit.remediation.dry_run entries whose subject
        matches the given namespace prefix.

        Called by AuditViolationSensor when it completes a cycle with zero
        violations — confirming that any dry-run entries for this namespace
        describe violations that no longer exist.

        Only resolves entries in 'open' status. Returns count of rows updated.

        Subject pattern matched: 'audit.remediation.dry_run::<namespace_prefix>%'
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'resolved',
                            resolved_at = now(),
                            updated_at = now()
                        WHERE entry_type = 'finding'
                          AND subject LIKE 'audit.remediation.dry_run::'
                                            || :namespace_prefix || '%'
                          AND status = 'open'
                        """
                    ),
                    {"namespace_prefix": namespace_prefix},
                )
                return result.rowcount or 0

    # ID: d98fae16-259d-4993-9e10-4b18c7ea7a70
    async def fetch_open_finding_subjects_by_worker(
        self, worker_uuid: str, prefix: str
    ) -> set[str]:
        """
        Return subjects of non-terminal finding entries posted by *worker_uuid*
        whose subject matches *prefix*.

        Covers:
          - AuditIngestWorker._fetch_existing_subjects
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT subject FROM core.blackboard_entries
                    WHERE worker_uuid = :worker_uuid
                      AND entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status NOT IN ('resolved', 'abandoned')
                    """
                ),
                {"worker_uuid": worker_uuid, "prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}

    # ID: e38d5bb0-ad45-4d45-9350-28ca7d92f8de
    async def fetch_stale_entries(self) -> list[dict[str, Any]]:
        """
        Return blackboard entries whose age exceeds their constitutional SLA tier.
        Excludes self-referential stale-finding and silent-worker subjects.

        Covers:
          - BlackboardAuditor._fetch_stale_entries
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id,
                        entry_type,
                        subject,
                        worker_uuid,
                        status,
                        EXTRACT(EPOCH FROM (now() - created_at))::int AS age_seconds,
                        CASE entry_type
                            WHEN 'heartbeat' THEN CAST(:sla_heartbeat AS INT)
                            WHEN 'finding'   THEN CAST(:sla_finding AS INT)
                            WHEN 'report'    THEN CAST(:sla_report AS INT)
                            WHEN 'proposal'  THEN CAST(:sla_proposal AS INT)
                            ELSE CAST(:sla_default AS INT)
                        END AS sla_seconds
                    FROM core.blackboard_entries
                    WHERE status NOT IN ('resolved', 'abandoned')
                      AND subject NOT LIKE 'blackboard.entry_stale::%'
                      AND subject NOT LIKE 'worker.silent::%'
                      AND EXTRACT(EPOCH FROM (now() - created_at)) >
                        CASE entry_type
                            WHEN 'heartbeat' THEN CAST(:sla_heartbeat AS INT)
                            WHEN 'finding'   THEN CAST(:sla_finding AS INT)
                            WHEN 'report'    THEN CAST(:sla_report AS INT)
                            WHEN 'proposal'  THEN CAST(:sla_proposal AS INT)
                            ELSE CAST(:sla_default AS INT)
                        END
                    ORDER BY age_seconds DESC
                    """
                ),
                {
                    "sla_heartbeat": _SLA["heartbeat"],
                    "sla_finding": _SLA["finding"],
                    "sla_report": _SLA["report"],
                    "sla_proposal": _SLA["proposal"],
                    "sla_default": _SLA_DEFAULT,
                },
            )
            return [
                {
                    "id": row[0],
                    "entry_type": row[1],
                    "subject": row[2],
                    "worker_uuid": row[3],
                    "status": row[4],
                    "age_seconds": row[5] or 0,
                    "sla_seconds": row[6],
                }
                for row in result.fetchall()
            ]

    # ID: cdfba0a0-a746-4e3c-97a8-cc0a0eff2c59
    async def count_active_entries(self) -> int:
        """
        Count total non-terminal blackboard entries.

        Covers:
          - BlackboardAuditor._count_active_entries
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE status NOT IN ('resolved', 'abandoned')
                    """
                )
            )
            return result.scalar() or 0

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    # ID: 39ffce8c-7f06-40c0-b8e6-16183b788a56
    async def claim_open_findings(
        self, subject_prefix: str, limit: int
    ) -> list[dict[str, Any]]:
        """
        Atomically claim up to *limit* open findings whose subject matches
        *subject_prefix*.  Uses FOR UPDATE SKIP LOCKED to prevent
        double-claiming across concurrent worker instances.

        Returns list of dicts with keys: id, subject, payload.

        Covers:
          - PromptExtractorWorker._claim_open_findings
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'claimed',
                            claimed_at = now(),
                            updated_at = now()
                        WHERE id IN (
                            SELECT id FROM core.blackboard_entries
                            WHERE entry_type = 'finding'
                              AND subject LIKE :prefix
                              AND status = 'open'
                            ORDER BY created_at ASC
                            LIMIT :limit
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, subject, payload
                        """
                    ),
                    {"prefix": subject_prefix, "limit": limit},
                )
                rows = result.fetchall()

        findings = []
        for row in rows:
            raw_payload = row[2]
            payload = (
                raw_payload
                if isinstance(raw_payload, dict)
                else json.loads(raw_payload)
            )
            findings.append(
                {
                    "id": str(row[0]),
                    "subject": row[1],
                    "payload": payload,
                }
            )
        return findings

    # ID: f3a8d1c2-7e45-4b09-a3f6-9d2c0e5b1a87
    async def claim_violation_findings(
        self, prefix: str, limit: int, claimed_by: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        """
        Atomically claim up to *limit* open findings whose subject matches
        *prefix*, ordered by severity (critical first) then creation time.
        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming across
        concurrent worker instances.

        Returns list of dicts with keys: id, subject, payload.

        Covers:
          - ViolationRemediator._claim_open_findings
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'claimed',
                            claimed_by = :claimed_by,
                            claimed_at = now(),
                            updated_at = now()
                        WHERE id IN (
                            SELECT id FROM core.blackboard_entries
                            WHERE entry_type = 'finding'
                              AND subject LIKE :prefix
                              AND status = 'open'
                            ORDER BY
                                CASE (payload->>'severity')
                                    WHEN 'critical' THEN 1
                                    WHEN 'error'    THEN 2
                                    WHEN 'warning'  THEN 3
                                    WHEN 'info'     THEN 4
                                    ELSE 5
                                END ASC,
                                created_at ASC
                            LIMIT :limit
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, subject, payload
                        """
                    ),
                    {
                        "prefix": prefix,
                        "limit": limit,
                        "claimed_by": str(claimed_by) if claimed_by else None,
                    },
                )
                rows = result.fetchall()

        findings = []
        for row in rows:
            raw_payload = row[2]
            payload = (
                raw_payload
                if isinstance(raw_payload, dict)
                else json.loads(raw_payload)
            )
            findings.append(
                {
                    "id": str(row[0]),
                    "subject": row[1],
                    "payload": payload,
                }
            )
        return findings

    # ID: 7e4f9a1b-2c3d-4e5f-8a6b-7c8d9e0f1a2b
    async def fetch_open_findings(
        self, prefix: str, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return up to *limit* open finding entries whose subject matches *prefix*,
        ordered oldest-first.  Payload is always returned as a dict.

        Covers:
          - ViolationRemediatorWorker._load_open_findings
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, subject, payload
                    FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status = 'open'
                    ORDER BY created_at ASC
                    LIMIT :limit
                    """
                ),
                {"prefix": prefix, "limit": limit},
            )
            rows = result.fetchall()

        findings = []
        for row in rows:
            raw_payload = row[2]
            payload = (
                raw_payload
                if isinstance(raw_payload, dict)
                else json.loads(raw_payload)
            )
            findings.append(
                {
                    "id": str(row[0]),
                    "subject": row[1],
                    "payload": payload or {},
                }
            )
        return findings

    # ID: 3d4e5f6a-7b8c-9d0e-1f2a-3b4c5d6e7f8a
    async def resolve_entries(self, entry_ids: list[str]) -> int:
        """
        Mark each entry in *entry_ids* as resolved, provided it is still in
        a non-terminal status ('open' or 'claimed').

        Historically the WHERE clause filtered status = 'open' only, which
        silently no-op'd the claim→resolve path used by workers that claim
        findings before acting on them. This left every such caller leaking
        claims — the entries_resolved counters in their reports were always
        zero because the UPDATE never matched.

        The predicate now accepts either 'open' or 'claimed' so two caller
        patterns are both correct:
          - fetch_open_findings → resolve_entries  (TestRunnerSensor)
          - claim_violation_findings → ... → resolve_entries
              (ViolationRemediatorWorker dedup-subsume path, TestRemediatorWorker)

        All updates run inside a single transaction. Returns the count of
        rows actually updated (entries already terminalized or missing are
        not counted).

        Scope note: as of ADR-010, the ViolationRemediatorWorker happy path
        (proposal created successfully) no longer calls this method. That
        path now calls defer_entries_to_proposal so the Finding→Proposal
        linkage §7/§7a of CORE-Finding.md specifies is preserved. This
        method remains in use by the dedup-subsume path and by
        TestRemediatorWorker / TestRunnerSensor.

        Covers:
          - ViolationRemediatorWorker._resolve_entries (dedup branch only)
          - TestRemediatorWorker._resolve_entries
          - TestRunnerSensor (direct)
        """
        from body.services.service_registry import ServiceRegistry

        resolved_count = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'resolved',
                                resolved_at = now(),
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status IN ('open', 'claimed')
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    resolved_count += result.rowcount
        return resolved_count

    # ID: a7b2c8d3-e4f5-6789-abcd-ef0123456789
    async def release_claimed_entries(self, entry_ids: list[str]) -> int:
        """
        Reset claimed entries back to open status and clear claimed_by.

        Used when a worker claims findings but cannot act on them (e.g.
        unmappable violations with no registered remediation action).
        Releasing prevents them from staying claimed forever.

        Only updates entries currently in 'claimed' status.
        Returns the count of rows actually updated.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        released = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'open',
                                claimed_by = NULL,
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status = 'claimed'
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    released += result.rowcount
        return released

    # ID: 8b1e6f3a-d42c-4e7a-9f05-b3c8a71d2e94
    async def claim_unmapped_violation_findings(
        self,
        mapped_rule_ids: set[str],
        limit: int,
        claimed_by: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Atomically claim open audit.violation findings whose rule is NOT
        in the mapped_rule_ids set. Used by ViolationExecutorWorker (Will)
        to claim findings that RemediatorWorker left unclaimed.

        Returns a list of dicts: {id, subject, payload}.
        """
        from body.services.service_registry import ServiceRegistry

        if mapped_rule_ids:
            rule_filter = "AND payload->>'rule' != ALL(:mapped_rules)"
            params: dict[str, Any] = {
                "limit": limit,
                "claimed_by": str(claimed_by),
                "mapped_rules": list(mapped_rule_ids),
            }
        else:
            rule_filter = ""
            params = {
                "limit": limit,
                "claimed_by": str(claimed_by),
            }

        sql = f"""
            WITH to_claim AS (
                SELECT id
                FROM core.blackboard_entries
                WHERE entry_type = 'finding'
                  AND subject LIKE 'audit.violation::%%'
                  AND status = 'open'
                  {rule_filter}
                ORDER BY created_at ASC
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            )
            UPDATE core.blackboard_entries
            SET status = 'claimed',
                claimed_by = cast(:claimed_by as uuid),
                claimed_at = now(),
                updated_at = now()
            WHERE id IN (SELECT id FROM to_claim)
            RETURNING id, subject, payload
        """

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(text(sql), params)
                rows = result.fetchall()

        findings = []
        for row in rows:
            raw_payload = row[2]
            payload = (
                raw_payload
                if isinstance(raw_payload, dict)
                else json.loads(raw_payload)
            )
            findings.append(
                {
                    "id": str(row[0]),
                    "subject": row[1],
                    "payload": payload,
                }
            )
        return findings

    # ID: 4c7a9e2f-b518-4d63-a0e1-d6f3b82c5a10
    async def abandon_entries(self, entry_ids: list[str]) -> int:
        """
        Mark entries as abandoned. Terminal state — no worker reclaims them.
        Only updates entries currently in 'claimed' status.
        Returns the count of rows actually updated.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        abandoned = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'abandoned',
                                resolved_at = now(),
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status = 'claimed'
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    abandoned += result.rowcount
        return abandoned

    # ID: d3a1f7b2-8c4e-4a9d-b6e5-1f0c3d7a2e89
    async def mark_indeterminate(self, entry_ids: list[str]) -> int:
        """
        Mark claimed entries as indeterminate.

        Used when a worker claims findings but reaches an inconclusive
        outcome — the entry is neither resolved nor releasable back to
        open.  Only updates entries currently in 'claimed' status.
        Returns the count of rows actually updated.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        updated = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'indeterminate',
                                resolved_at = now(),
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status = 'claimed'
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    updated += result.rowcount
        return updated

    # ID: 54c114b0-4c6d-484f-8b20-d9ff5fa24caf
    async def update_entry_status(self, entry_id: str, status: str) -> None:
        """
        Update the status of a single blackboard entry by ID.

        Covers:
          - PromptExtractorWorker._mark_finding

        Sets resolved_at on transition to a terminal status (resolved, abandoned,
        indeterminate), matching the hygiene rule established by commit 59ff25be
        and the pattern used by the direct-SQL _mark_findings / _mark_finding
        paths. Without this clause, callers routing through this method
        (ProposalConsumerWorker._mark_finding, ViolationRemediator._mark_finding)
        produced terminal rows with NULL resolved_at, distorting any query that
        uses resolved_at as a temporal filter. Discovered 2026-04-27 during
        Band B verification sweep: 26/26 abandoned rows post-59ff25be carried
        NULL resolved_at, all attributable to this path.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = :status,
                        resolved_at = CASE
                            WHEN :status IN ('resolved', 'abandoned', 'indeterminate')
                                THEN now()
                            ELSE resolved_at
                        END,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"status": status, "id": entry_id},
            )
            await session.commit()

    # ------------------------------------------------------------------
    # Finding ↔ Proposal contract (CORE-Finding.md §7 / §7a, ADR-010)
    # ------------------------------------------------------------------

    # ID: 7f2a3c51-b9d0-48e4-9d2b-4a6f1e8c0b52
    async def defer_entries_to_proposal(
        self, entry_ids: list[str], proposal_id: str
    ) -> int:
        """
        Transition findings to 'deferred_to_proposal' terminal status and
        write the proposal_id into each finding's payload.

        Implements CORE-Finding.md §7 row 4:
          > The rule has an active RemediationMap entry. A Proposal has been
          > created. The `proposal_id` field in the payload MUST be set to
          > the created Proposal's ID.

        Only transitions entries currently in 'open' or 'claimed' — matches
        the predicate used by resolve_entries. Entries in any other status
        are left untouched and not counted.

        Sets resolved_at because 'deferred_to_proposal' is terminal per
        the blackboard_entry_status enum declaration in
        .intent/META/enums.json.

        Payload merge uses the 'payload = payload || jsonb_build_object(...)'
        idiom already established elsewhere in this service. If an earlier
        proposal_id was written (e.g. in unusual retry flows), this call
        overwrites it with the current value — last-writer-wins, which
        matches the semantic "this finding is now linked to THIS proposal."

        Returns the count of rows actually updated.

        Covers:
          - ViolationRemediatorWorker._defer_to_proposal
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        deferred_count = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'deferred_to_proposal',
                                resolved_at = now(),
                                updated_at = now(),
                                payload = payload || jsonb_build_object(
                                    'proposal_id', cast(:proposal_id as text)
                                )
                            WHERE id = cast(:entry_id as uuid)
                              AND status IN ('open', 'claimed')
                            """
                        ),
                        {"entry_id": entry_id, "proposal_id": proposal_id},
                    )
                    deferred_count += result.rowcount
        return deferred_count

    # ID: e1c4b8a7-6f03-4d29-b8a2-9c5d7e0f3a14
    async def revive_findings_for_failed_proposal(
        self, proposal_id: str, failure_reason: str
    ) -> dict[str, Any] | None:
        """
        Restore findings that were deferred to a now-failed proposal back
        to 'open' status, and return the revival outcome.

        Implements CORE-Finding.md §7a steps 1-2 (state transition only).
        §7a step 3 (posting a `report` entry recording the revival) is the
        calling Worker's responsibility per ADR-011 — this method is
        UPDATE-only. The Worker consumes this method's return value and
        posts the revival report via self.post_report() so the entry
        carries Worker attribution.

        The UPDATE filter restricts to status = 'deferred_to_proposal'. This
        protects against retry races and against findings that drifted to
        some other status (abandoned, indeterminate) for unrelated reasons
        — only findings still parked on this proposal's deferral are
        revived. resolved_at is cleared so the row's terminal-state marker
        matches its new non-terminal status (ADR-010 hygiene rule, tracking
        the Option A+ convention from 2026-04-22).

        Returns:
          None if no findings were revived (revived_count == 0) — nothing
          to report.
          dict with keys ``proposal_id``, ``failure_reason``,
          ``revived_count``, ``revived_finding_ids``, ``revived_subjects``
          when one or more rows were revived. Both id and subject lists
          are returned — IDs for precise downstream queries, subjects for
          human-readable audit trails in the revival report payload.

        The caller MUST NOT rely on this method raising on partial failure.
        Zero rows revived is a legitimate outcome when the failed proposal
        had no findings deferred to it (e.g. proposals created by paths
        other than ViolationRemediatorWorker); the caller receives None
        and skips posting a revival report.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                # §7a steps 1+2: query-and-reset in one UPDATE ... RETURNING.
                # RETURNING id, subject so the Worker can persist both in
                # the revival report payload (IDs for queries, subjects for
                # audit trails).
                update_result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'open',
                            claimed_by = NULL,
                            claimed_at = NULL,
                            resolved_at = NULL,
                            updated_at = now()
                        WHERE entry_type = 'finding'
                          AND status = 'deferred_to_proposal'
                          AND payload->>'proposal_id' = :proposal_id
                        RETURNING id, subject
                        """
                    ),
                    {"proposal_id": proposal_id},
                )
                rows = update_result.fetchall()
                revived_ids = [str(row[0]) for row in rows]
                revived_subjects = [str(row[1]) for row in rows]

        logger.info(
            "Revived %d finding(s) for failed proposal %s (reason: %s)",
            len(revived_ids),
            proposal_id,
            failure_reason,
        )

        if not revived_ids:
            return None

        return {
            "proposal_id": proposal_id,
            "failure_reason": failure_reason,
            "revived_count": len(revived_ids),
            "revived_finding_ids": revived_ids,
            "revived_subjects": revived_subjects,
        }
