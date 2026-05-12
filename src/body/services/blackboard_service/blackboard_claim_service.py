# src/body/services/blackboard_service/blackboard_claim_service.py
"""Atomic claiming methods — FOR UPDATE SKIP LOCKED, return claimed rows."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text


# ID: 9f135870-8e69-4c6b-a733-3c24cb8be8dc
class BlackboardClaimService:
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
