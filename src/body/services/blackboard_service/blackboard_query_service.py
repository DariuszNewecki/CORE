# src/body/services/blackboard_service/blackboard_query_service.py
"""Pure-read query methods — SELECT only, no mutations."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from shared.infrastructure.intent.operational_config import load_operational_config


_SLA: dict[str, int] = {
    "heartbeat": 600,
    "finding": 3600,
    "report": 7200,
    "proposal": 1800,
}

_CFG = load_operational_config().blackboard


# ID: 0f7e0bf6-9fba-44b1-9605-b7dcadf97fac
class BlackboardQueryService:
    # ID: b980a1a9-eca8-4268-b8ba-86fbcf94b6ce
    async def fetch_open_finding_subjects_by_prefix(self, prefix: str) -> set[str]:
        """
        Return subjects of non-terminal finding entries whose subject matches
        *prefix* (SQL LIKE pattern — caller supplies the trailing wildcard).

        'suppressed' is treated as terminal and excluded — suppressed entries
        are not "open" by any definition. (See #263 for the suppressed/abandoned
        split: only ``fetch_active_finding_subjects_by_prefix`` keeps suppressed
        in its result set, because dedup-vs-permanent-skip is its purpose.)

        'awaiting_reaudit' (ADR-045) is NOT excluded — those rows are
        non-terminal and represent unresolved work that has not yet been
        adjudicated by the audit sensor's release pass.

        Covers:
          - AuditViolationSensor._fetch_existing_subjects
          - BlackboardShopManager._fetch_existing_findings
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
                      AND status NOT IN (
                          'resolved',
                          'abandoned',
                          'suppressed',
                          'dry_run_complete',
                          'deferred_to_proposal',
                          'indeterminate'
                      )
                    """
                ),
                {"prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}

    # ID: 9c4e1f7a-2b3d-4e85-a6f7-90bc8d1e2f43
    async def fetch_awaiting_reaudit_subjects_by_prefix(self, prefix: str) -> set[str]:
        """
        Return subjects of awaiting_reaudit finding entries matching *prefix*.

        Used by quarantine drainers (ADR-072) to determine the scope of
        work for the current drain cycle — e.g. TestRunnerSensor uses this
        to enumerate test_files referenced by quarantined
        `python::test.runner.failure::*` rows so it can re-run pytest only
        for what is actually parked.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT subject FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND status = 'awaiting_reaudit'
                      AND subject LIKE :prefix
                    """
                ),
                {"prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}

    # ID: 1b8e7a4c-3f2d-4c5b-9a01-8e6d2f9b0a31
    async def fetch_active_finding_subjects_by_prefix(self, prefix: str) -> set[str]:
        """
        Return subjects of finding entries whose subject matches *prefix*
        that should be treated as "still on the board" for sensor dedup.

        Sensor-dedup contract (see #263 for the rationale):

        - 'resolved' is excluded: the issue is closed; the sensor MAY re-post
          if it re-detects the same subject (re-emergence is meaningful).
        - 'abandoned' is excluded: workers gave up on this entry without
          resolving the underlying issue, so a fresh detection deserves a
          fresh entry — re-emit is correct.
        - 'suppressed' is INTENTIONALLY KEPT in the result set: it is the
          governor's deliberate "do not surface this again" signal. Its
          subject must remain in the dedup set so sensors skip it
          permanently.
        - All other statuses (open, claimed, deferred_to_proposal,
          indeterminate, awaiting_reaudit per ADR-045) are included —
          those subjects are still on the board (active or quarantined)
          and a sensor must not pile on duplicates.

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

        'suppressed' is treated as terminal and excluded — see #263.

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
                      AND status NOT IN (
                          'resolved',
                          'abandoned',
                          'suppressed',
                          'dry_run_complete',
                          'deferred_to_proposal',
                          'indeterminate'
                      )
                    """
                ),
                {"worker_uuid": worker_uuid, "prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}

    # ID: 8b732034-7e6f-435e-ad4b-1f09eb248878
    async def fetch_open_findings_by_patterns(
        self, patterns: list[str], limit: int
    ) -> list[dict[str, Any]]:
        """Return up to *limit* open finding entries matching any of *patterns*.

        Mirrors ``fetch_open_findings`` but accepts a list of SQL LIKE patterns
        — each pattern joined under ``LIKE ANY(:patterns)``. Used by ADR-091
        D5 Phase 3 consumers (`violation_remediator` chain) whose subject
        discriminator is the predicate-derived `audit_violation_like_patterns()`,
        not a single static prefix.

        An empty *patterns* list returns no rows without executing SQL.
        """
        if not patterns:
            return []

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, subject, payload
                    FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE ANY(:patterns)
                      AND status = 'open'
                    ORDER BY created_at ASC
                    LIMIT :limit
                    """
                ),
                {"patterns": patterns, "limit": limit},
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

    # ID: e38d5bb0-ad45-4d45-9350-28ca7d92f8de
    async def fetch_stale_entries(self) -> list[dict[str, Any]]:
        """
        Return blackboard entries whose age exceeds their constitutional SLA tier.

        Stale detection is for non-terminal stuck entries only. Every declared
        terminal status is excluded because terminal entries cannot be acted
        on further and must not trigger stale alerts. Per the canonical
        ``blackboard_entry_status`` enum (.intent/META/enums.json), the
        terminal set is:

          * resolved
          * abandoned
          * suppressed             (#263)
          * dry_run_complete       (#265 — historical; no new writers)
          * deferred_to_proposal
          * indeterminate

        Excludes self-referential stale-finding and silent-worker subjects.

        Covers:
          - BlackboardShopManager._fetch_stale_entries
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
                    WHERE status NOT IN (
                            'resolved',
                            'abandoned',
                            'suppressed',
                            'dry_run_complete',
                            'deferred_to_proposal',
                            'indeterminate'
                          )
                      AND entry_type IN ('finding', 'proposal')
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
                    "sla_default": _CFG.sla_default_seconds,
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
          - BlackboardShopManager._count_active_entries
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE status NOT IN (
                        'resolved',
                        'abandoned',
                        'suppressed',
                        'dry_run_complete',
                        'deferred_to_proposal',
                        'indeterminate'
                    )
                    """
                )
            )
            return result.scalar() or 0

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
