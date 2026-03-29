# src/body/services/audit_findings_service.py
"""
AuditFindingsService - Data-access layer for core.audit_findings.

Covers:
  - AutonomousProposalWorker / _read_recent_findings
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 319e2a23-a77d-4592-8d56-d26372524844
class AuditFindingsService:
    """
    Body layer service. Exposes named methods for core.audit_findings
    queries used by AutonomousProposalWorker.
    """

    # ID: 454730ef-80db-47c7-9f4f-f5e1aedf108c
    async def fetch_recent_error_findings(
        self, lookback_minutes: int
    ) -> list[dict[str, Any]]:
        """
        Return recent ERROR-level audit findings grouped by check_id,
        ordered by hit count descending. Looks back *lookback_minutes*
        from now. Returns at most 20 groups.

        Covers:
          - AutonomousProposalWorker._read_recent_findings
        """
        from datetime import UTC, datetime, timedelta

        from body.services.service_registry import ServiceRegistry

        since = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        check_id,
                        COUNT(*)                        AS hit_count,
                        array_agg(DISTINCT file_path)   AS files,
                        array_agg(message ORDER BY created_at DESC) AS messages
                    FROM core.audit_findings
                    WHERE severity = 'error'
                      AND created_at >= :since
                    GROUP BY check_id
                    ORDER BY hit_count DESC
                    LIMIT 20
                    """
                ),
                {"since": since},
            )
            rows = result.fetchall()

        return [
            {
                "check_id": str(row[0]),
                "count": int(row[1]),
                "files": [f for f in (row[2] or []) if f],
                "sample_messages": list((row[3] or [])[:3]),
            }
            for row in rows
        ]
