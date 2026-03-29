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
                        SET status = 'claimed', updated_at = now()
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

    # ID: 54c114b0-4c6d-484f-8b20-d9ff5fa24caf
    async def update_entry_status(self, entry_id: str, status: str) -> None:
        """
        Update the status of a single blackboard entry by ID.

        Covers:
          - PromptExtractorWorker._mark_finding
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = :status
                    WHERE id = :id
                    """
                ),
                {"status": status, "id": entry_id},
            )
            await session.commit()
